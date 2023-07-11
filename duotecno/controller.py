"""Main interface to the duotecno bus."""

import asyncio
import logging
from duotecno.exceptions import InvallidPassword, LoadFailure
from duotecno.protocol import (
    Packet,
    EV_CLIENTCONNECTSET_3,
    EV_NODEDATABASEINFO_0,
    EV_NODEDATABASEINFO_1,
)
from duotecno.node import Node


class PyDuotecno:
    """Class that will will do the bus management.

    - send packets
    - receive packets
    - open and close the connection
    """

    writer: asyncio.StreamWriter = None
    reader: asyncio.StreamReader = None
    readerTask: asyncio.Task
    loginOK: asyncio.Event
    connectionOK: asyncio.Event
    loadOK: asyncio.Event
    nodes: dict = {}

    def get_units(self, unit_type) -> list:
        res = []
        for node in self.nodes.values():
            for unit in node.get_unit_by_type(unit_type):
                res.append(unit)
        return res

    async def connect(self, host, port, password, testOnly=False) -> None:
        """Initialize the connection."""
        self.nodes = {}
        self._log = logging.getLogger("pyduotecno")
        # try to connect
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
        except ConnectionError or TimeoutError:
            raise
        # events
        self.connectionOK = asyncio.Event()
        self.loginOK = asyncio.Event()
        self.loadOK = asyncio.Event()
        # at this point the connection should be ok
        self.connectionOK.set()
        self.loginOK.clear()
        self.loadOK.clear()
        # start the bus reading task
        self.readerTask = asyncio.Task(self.readTask())
        # start loading, this task will kill itself once finished
        passw = [str(ord(i)) for i in password]
        # send login info
        await self.write(f"[214,3,{len(passw)},{','.join(passw)}]")
        # wait for the login to be ok
        try:
            await asyncio.wait_for(self.loginOK.wait(), timeout=1.0)
            await self.loginOK.wait()
        except TimeoutError:
            raise InvallidPassword()
        # if we are not testing the connection, start scanning
        if not testOnly:
            await self.write("[209,0]")
            _loadTask = asyncio.Task(self._loadTask())
            try:
                await asyncio.wait_for(self.loadOK.wait(), timeout=15.0)
            except TimeoutError:
                raise LoadFailure()
            finally:
                _loadTask.cancel()

    async def write(self, msg) -> None:
        """Send a message."""
        if self.writer.transport._conn_lost:
            self.connectionOK.clear()
            self._log("ERROR CONNECTION LOST")
            return
        self._log.debug(f"Send: {msg}")
        msg = f"{msg}{chr(10)}"
        self.writer.write(msg.encode())
        await self.writer.drain()

    async def _loadTask(self):
        while len(self.nodes) < 1:
            await asyncio.sleep(1)
        while not self.loadOK.is_set():
            c = 0
            for n in self.nodes.values():
                if n.isLoaded.is_set():
                    c += 1
            if c == len(self.nodes):
                self.loadOK.set()
                self._log.info("Loading finished")
            else:
                await asyncio.sleep(1)

    async def readTask(self):
        """Reader task."""
        while self.connectionOK.is_set():
            tmp = await self.reader.readline()
            tmp = tmp.decode().rstrip()
            if not tmp.startswith("["):
                tmp = tmp.lstrip("[")
            tmp = tmp.replace("\x00", "")
            self._log.debug(f"Receive: {tmp}")
            tmp = tmp[1:-1]
            p = tmp.split(",")
            try:
                pc = Packet(int(p[0]), int(p[1]), [int(_i) for _i in p[2:]])
            except Exception as e:
                self._log.error(e)
                self._log.error(tmp)
            await self._handlePacket(pc)
            if not self.loginOK.is_set():
                self._log.error("Login failed")
                self.connectionOK.clear()
        self._log.error("ERROR CONNECTION LOST")

    async def _handlePacket(self, packet):
        if isinstance(packet.cls, EV_CLIENTCONNECTSET_3):
            if packet.cls.loginOK == 1:
                self.loginOK.set()
                return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_0):
            for i in range(packet.cls.numNode - 1):
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
