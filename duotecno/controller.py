"""Main interface to the duotecno bus."""
from __future__ import annotations
import asyncio
import logging
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
    loginOK: asyncio.Event
    connectionOK: asyncio.Event
    heartbeatReceived: asyncio.Event
    nodes: dict[int, Node] = {}
    host: str
    port: int
    password: str

    def get_units(self, unit_type: list[str] | str) -> list[BaseUnit]:
        res = []
        for node in self.nodes.values():
            for unit in node.get_unit_by_type(unit_type):
                res.append(unit)
        return res

    async def disconnect(self) -> None:
        self._log.debug("Disconnecting")
        self.connectionOK.clear()
        self.loginOK.clear()
        if self.writer:
            self.writer.close()
            self._log.debug("Waiting to finish disconnecting")
            await self.writer.wait_closed()
        self._log.debug("Disconnecting Finished")

    async def connect(
        self, host: str, port: int, password: str, testOnly: bool = False
    ) -> None:
        """Initialize the connection."""
        self.host = host
        self.port = port
        self.password = password
        await self._do_connect(testOnly)

    async def _do_connect(self, testOnly: bool = False) -> None:
        self.nodes = {}
        self._log = logging.getLogger("pyduotecno")
        # try to connect
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
        except (ConnectionError, TimeoutError):
            raise
        # events
        self.connectionOK = asyncio.Event()
        self.loginOK = asyncio.Event()
        self.heartbeatReceived = asyncio.Event()
        # at this point the connection should be ok
        self.connectionOK.set()
        self.loginOK.clear()
        self.heartbeatReceived.clear()
        # start the bus reading task
        self.readerTask = asyncio.Task(self.readTask())
        # send login info
        passw = [str(ord(i)) for i in self.password]
        await self.write(f"[214,3,{len(passw)},{','.join(passw)}]")
        # wait for the login to be ok
        try:
            await asyncio.wait_for(self.loginOK.wait(), timeout=5.0)
            await self.loginOK.wait()
        except TimeoutError:
            await self.disconnect()
            raise InvalidPassword()
        # if we are not testing the connection, start scanning
        if not testOnly:
            await self.write("[209,5]")
            await self.write("[209,0]")
            try:
                await asyncio.wait_for(self._loadTask(), timeout=30.0)
            except TimeoutError:
                raise LoadFailure()
            self._log.info("Loading finished")
            self.hbTask = asyncio.Task(self.heartbeatTask())

    async def write(self, msg: str) -> None:
        """Send a message."""
        if not self.writer:
            return
        if self.writer.transport.is_closing():
            await self.disconnect()
            await self._do_connect()
            return
        self._log.debug(f"Send: {msg}")
        msg = f"{msg}{chr(10)}"
        try:
            self.writer.write(msg.encode())
            await self.writer.drain()
        except ConnectionError:
            await self.disconnect()
            await self._do_connect()

    async def _loadTask(self) -> None:
        while len(self.nodes) < 1:
            await asyncio.sleep(3)
        while True:
            c = 0
            for n in self.nodes.values():
                if n.isLoaded.is_set():
                    c += 1
            if c == len(self.nodes):
                return
            await asyncio.sleep(1)

    async def heartbeatTask(self) -> None:
        self._log.info("Starting HB task")
        while True:
            self.heartbeatReceived.clear()
            try:
                self._log.debug("Sending heartbeat message")
                await self.write("[215,1]")
                await asyncio.wait_for(self.heartbeatReceived.wait(), timeout=3.0)
                self._log.debug("Received heartbeat message")
            except TimeoutError:
                self._log.warning("Timeout on heartbeat, resconnecting")
                await self.disconnect()
                await self._do_connect()
                break
            except asyncio.exceptions.CancelledError:
                break
            await asyncio.sleep(5)
        self._log.info("Stopping HB task")

    async def readTask(self) -> None:
        """Reader task."""
        while self.connectionOK.is_set() and self.reader:
            try:
                tmp2 = await self.reader.readline()
            except ConnectionError:
                await self.disconnect()
                await self._do_connect()
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
            self._log.debug(f'Receive: "{tmp}"')
            p = tmp.split(",")
            try:
                pc = Packet(int(p[0]), int(p[1]), deque([int(_i) for _i in p[2:]]))
                await self._handlePacket(pc)
            except Exception as e:
                self._log.error(e)
                self._log.error(tmp)
            if not self.loginOK.is_set():
                self._log.error("Login failed")
                self.connectionOK.clear()

    async def _handlePacket(self, packet: Packet) -> None:
        if packet.cls is None:
            self._log.debug(f"Ignoring packet: {packet}")
            return
        if isinstance(packet.cls, EV_HEARTBEATSTATUS_1):
            self.heartbeatReceived.set()
            return
        if isinstance(packet.cls, EV_CLIENTCONNECTSET_3):
            if packet.cls.loginOK == 1:
                self.loginOK.set()
                return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_0):
            for i in range(packet.cls.numNode):
                await self.write(f"[209,1,{i}]")
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
                )
                await self.nodes[packet.cls.address].load()
            return
        if hasattr(packet.cls, "address") and packet.cls.address in self.nodes:
            await self.nodes[packet.cls.address].handlePacket(packet.cls)
            return
        self._log.debug(f"Ignoring packet: {packet}")
