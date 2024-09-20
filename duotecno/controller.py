"""Main interface to the duotecno bus."""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Final
from collections import deque
from duotecno.exceptions import LoadFailure, InvalidPassword
from duotecno.protocol import (
    Packet,
    EV_CLIENTCONNECTSET_3,
    EV_NODEDATABASEINFO_0,
    EV_NODEDATABASEINFO_1,
    EV_HEARTBEATSTATUS_1,
)
from duotecno.node import Node
from duotecno.unit import BaseUnit

PW_TIMEOUT: Final = 5
LOAD_NODE_TIMEOUT: Final = 60
LOAD_UNIT_TIMEOUT: Final = 120
HB_TIMEOUT: Final = 20
HB_BUSEMPTY: Final = 10
MAX_INFLIGHT: Final = 5
STATUS_RETRANSMIT: Final = 2


class PyDuotecno:
    """Class that will will do the bus management.

    - send packets
    - receive packets
    - open and close the connection
    """

    writer: asyncio.StreamWriter | None = None
    reader: asyncio.StreamReader | None = None
    readerTask: asyncio.Task[None]
    hbTask: asyncio.Task[None]
    workTask: asyncio.Task[None]
    writerTask: asyncio.Task[None]
    receiveQueue: asyncio.PriorityQueue
    sendSema: asyncio.Semaphore
    sendQueue: asyncio.PriorityQueue
    connectionOK: asyncio.Event
    heartbeatReceived: asyncio.Event
    nextHeartbeat: int
    packetToWaitFor: str | None = None
    packetWaiter: asyncio.Event
    nodes: dict[int, Node] = {}
    host: str
    port: int
    password: str
    numNodes: int = 0

    def get_units(self, unit_type: list[str] | str) -> list[BaseUnit]:
        res = []
        for node in self.nodes.values():
            for unit in node.get_unit_by_type(unit_type):
                res.append(unit)
        return res

    async def enableAllUnits(self) -> None:
        self._log.debug("Enable all Units on all nodes")
        for node in self.nodes.values():
            await node.enable()

    async def disableAllUnits(self) -> None:
        self._log.debug("Disable all Units on all nodes")
        for node in self.nodes.values():
            await node.disable()

    async def disconnect(self) -> None:
        self._log.debug("Disconnecting")
        self.connectionOK.clear()

        self.readerTask.cancel()
        self.hbTask.cancel()
        self.workTask.cancel()
        self.writerTask.cancel()
        if self.writer:
            self.writer.close()
        self._log.debug("Disconnecting Finished")

    async def connect(
        self, host: str, port: int, password: str, testOnly: bool = False
    ) -> None:
        """Initialize the connection."""
        self.host = host
        self.port = port
        self.password = password
        await self._do_connect(testOnly)

    async def _reconnect(self):
        await self.disconnect()
        await self.disableAllUnits()
        await self.continuously_check_connection()

    async def _do_connect(self, testOnly: bool = False, skipLoad: bool = False) -> None:
        if not skipLoad:
            self.nodes = {}
        self._log = logging.getLogger("pyduotecno")
        # Try to connect
        self._log.debug("Try to connect")
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
        except (ConnectionError, TimeoutError):
            raise
        # events
        self.connectionOK = asyncio.Event()
        self.heartbeatReceived = asyncio.Event()
        self.packetWaiter = asyncio.Event()
        # at this point the connection should be ok
        self._log.debug("Connection established")
        self.connectionOK.set()
        self.heartbeatReceived.clear()
        # start the bus reading task
        self.receiveQueue = asyncio.PriorityQueue()
        self.sendQueue = asyncio.PriorityQueue()
        self.sendSema = asyncio.Semaphore(MAX_INFLIGHT)
        self.readerTask = asyncio.Task(self._readTask())
        self.writerTask = asyncio.Task(self._writeTask())
        self.workTask = asyncio.Task(self._handleTask())
        # send login info
        passw = [str(ord(i)) for i in self.password]
        await self.write(f"[214,3,{len(passw)},{','.join(passw)}]")
        # wait for the login to be ok
        try:
            await asyncio.wait_for(self.waitForPacket("67,3,1"), timeout=PW_TIMEOUT)
        except TimeoutError:
            await self.disconnect()
            raise InvalidPassword()
        # if we are not testing the connection, start scanning
        if testOnly:
            return
        # do we need to reload the modules?
        if not skipLoad:
            await self.write("[209,5]")
            await self.write("[209,0]")
            try:
                await asyncio.wait_for(self._loadTaskNodes(), timeout=LOAD_NODE_TIMEOUT)
                self._log.info("Nodes discoverd")
                for n in self.nodes.values():
                    await n.load()
                    await asyncio.sleep(0.1)
                await asyncio.wait_for(self._loadTaskUnits(), timeout=LOAD_UNIT_TIMEOUT)
                self._log.info("Units discoverd")
            except TimeoutError:
                await self.disconnect()
                raise LoadFailure()
        # in case of skipload we do want to request the status again
        self._log.info("Requesting unit status")
        for node in self.nodes.values():
            for unit in node.get_units():
                self._log.debug(f"Unit: {unit}")
                await unit.requestStatus()
                await asyncio.sleep(0.1)
        self.hbTask = asyncio.Task(self.heartbeatTask())
        await self.enableAllUnits()

    async def write(self, msg: str) -> None:
        """Send a message."""
        if not self.writer:
            return
        if self.writer.transport.is_closing():
            await self._reconnect()
            return
        self._log.debug(f"TX: {msg}")
        await self.sendQueue.put(msg)
        return

    async def _writeTask(self) -> None:
        while True:
            try:
                await self.sendSema.acquire()
                msg = await self.sendQueue.get()
                msg = f"{msg}{chr(10)}"
                self.writer.write(msg.encode())
                await self.writer.drain()
                await asyncio.sleep(0.1)
            except ConnectionError:
                await self.reconnect()
                return

    async def _loadTaskNodes(self) -> None:
        while len(self.nodes) < 1:
            await asyncio.sleep(3)
        while True:
            if len(self.nodes) == self.numNodes:
                return
            await asyncio.sleep(1)

    async def _loadTaskUnits(self) -> None:
        while True:
            c = 0
            for n in self.nodes.values():
                if n.isLoaded.is_set():
                    c += 1
                if c == len(self.nodes):
                    return
            await asyncio.sleep(1)

    async def check_tcp_connection(self, timeout=3) -> bool:
        """Check if a TCP connection can be established to the given host and port."""
        self._log.debug("Checking connection...")
        conn = asyncio.open_connection(self.host, self.port)
        try:
            reader, writer = await asyncio.wait_for(conn, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, OSError):
            # Could not connect within the timeout period or there was a network error
            return False

    async def continuously_check_connection(self) -> None:
        """Continuously check for connection restoration and reconnect."""
        self._log.info("Waiting for connection...")
        while True:
            connection_restored = await self.check_tcp_connection()
            if connection_restored:
                self._log.info("Connection to host restored, reconnecting.")
                await self._do_connect(skipLoad=True)
                break
            else:
                self._log.debug("Connection to host not yet restored, retrying...")
                await asyncio.sleep(5)

    async def heartbeatTask(self) -> None:
        await asyncio.sleep(30)
        self._log.info("Starting HB task")
        while True:
            # wait until the timer expire of 5 seconds
            while self.nextHeartbeat > int(time.time()):
                self._log.debug(
                    f"Waiting until {self.nextHeartbeat} to send a HB ({time.time()})"
                )
                await asyncio.sleep(1)
            # send the heartbeat
            self.heartbeatReceived.clear()
            try:
                self._log.debug("Sending heartbeat message")
                await self.write("[215,1]")
                await asyncio.wait_for(
                    self.heartbeatReceived.wait(), timeout=HB_TIMEOUT
                )
                self._log.debug("Received heartbeat message")
            except TimeoutError:
                self._log.warning("Timeout on heartbeat, reconnecting")
                await self._reconnect()
                break
            except asyncio.exceptions.CancelledError:
                break
        self._log.info("Stopping HB task")

    async def _readTask(self) -> None:
        """Reader task."""
        while self.connectionOK.is_set() and self.reader:
            try:
                tmp2 = await self.reader.readline()
            except ConnectionError:
                await self._reconnect()
                return
            if tmp2 == "":
                return
            tmp3 = tmp2.decode()
            tmp = tmp3.rstrip()
            # self._log.debug(f'Raw Receive: "{tmp}"')
            if not tmp.startswith("["):
                tmp = tmp.lstrip("[")
            tmp = tmp.replace("\x00", "")
            # self._log.debug(f'Receive: "{tmp}"')
            tmp = tmp[1:-1]
            if tmp == "":
                return
            self._log.debug(f'RX: "{tmp}"')
            self.nextHeartbeat = int(time.time()) + HB_BUSEMPTY
            self.sendSema.release()
            if await self._comparePacket(tmp):
                p = tmp.split(",")
                try:
                    pc = Packet(int(p[0]), int(p[1]), deque([int(_i) for _i in p[2:]]))
                    await self.receiveQueue.put(pc)
                # self._log.debug(f'QUEUE: "{pc}" {self.receiveQueue.qsize()}')
                except Exception as e:
                    self._log.error(e)
                    self._log.error(tmp)
            await asyncio.sleep(0.1)

    async def _comparePacket(self, rpck: str) -> bool:
        if not self.packetToWaitFor:
            return True
        # self._log.debug(f"COMPARE received packet {rpck} with {self.packetToWaitFor}")
        if rpck.startswith(self.packetToWaitFor):
            self.packetWaiter.set()
            return True
        return False

    async def waitForPacket(self, pstr: str) -> None:
        """Wait for a certain packet.

        will clear an event and then wait for the event to be set again
        """
        self.packetWaiter.clear()
        self.packetToWaitFor = pstr
        await self.packetWaiter.wait()
        self.packetToWaitFor = None

    async def _handleTask(self) -> None:
        """handler task."""
        while self.connectionOK.is_set() and self.receiveQueue:
            try:
                pc = await self.receiveQueue.get()
                self._log.debug(f"WX: {pc}")
                await self._handlePacket(pc)
            except Exception as e:
                self._log.error(e)
            await asyncio.sleep(0.1)

    async def _handlePacket(self, packet: Packet) -> None:
        if packet.cls is None:
            self._log.debug(f"Ignoring packet: {packet}")
            return
        if isinstance(packet.cls, EV_CLIENTCONNECTSET_3):
            return
        if isinstance(packet.cls, EV_HEARTBEATSTATUS_1):
            self.heartbeatReceived.set()
            return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_0):
            self.numNodes = packet.cls.numNode
            for i in range(packet.cls.numNode):
                await self.write(f"[209,1,{i}]")
                await self.waitForPacket(f"64,1,{i}")
            return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_1):
            if packet.cls.address not in self.nodes:
                self.nodes[packet.cls.address] = Node(
                    name=packet.cls.nodeName,
                    address=packet.cls.address,
                    index=packet.cls.index,
                    nodeType=packet.cls.nodeType,
                    numUnits=packet.cls.numUnits,
                    writer=self.write,
                    pwaiter=self.waitForPacket,
                )
                # await self.nodes[packet.cls.address].load()
            return
        if hasattr(packet.cls, "address") and packet.cls.address in self.nodes:
            await self.nodes[packet.cls.address].handlePacket(packet.cls)
            return
        self._log.debug(f"Ignoring packet: {packet}")
