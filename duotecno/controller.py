"""Main interface to the duotecno bus."""

import asyncio
import logging
import sys
from duotecno.protocol import (
    Packet,
    EV_CLIENTCONNECTSET_3,
    EV_NODEDATABASEINFO_0,
    EV_NODEDATABASEINFO_1,
    EV_NODEDATABASEINFO_2,
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
    nodes: dict

    async def connect(self, host, port, password) -> None:
        """Initialize the connection."""
        self._log = logging.getLogger("pyduotecno")
        self.reader, self.writer = await asyncio.open_connection(host, port)
        self.connectionOK = asyncio.Event()
        self.connectionOK.set()
        self.readerTask = asyncio.Task(self.readTask())
        self.loginOK = asyncio.Event()
        self.nodes = {}
        passw = [str(ord(i)) for i in password]
        await self.write(f"[214,3,{len(passw)},{','.join(passw)}]")
        await self.loginOK.wait()
        await self.write("[209,0]")

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

    async def readTask(self):
        """Reader task."""
        while self.connectionOK.is_set():
            tmp = await self.reader.readline()
            tmp = tmp.decode().rstrip()
            if not tmp.startswith("["):
                tmp = tmp.lstrip("[")
            tmp = tmp.replace("\x00", "")
            # log.debug(f"Receive: {tmp}")
            tmp = tmp[1:-1]
            p = tmp.split(",")
            try:
                pc = Packet(int(p[0]), int(p[1]), [int(_i) for _i in p[2:]])
            except Exception as e:
                self._log.error(e)
                self._log.error(tmp)
            await self._handlePacket(pc)
        self._log("ERROR CONNECTION LOST")

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
                await self.nodes[packet.cls.address].requestUnits()
            return
        if hasattr(packet.cls, "address") and packet.cls.address in self.nodes:
            await self.nodes[packet.cls.address].handlePacket(packet.cls)
            return
        self._log.debug(f"Ignoring packet: {packet}")
