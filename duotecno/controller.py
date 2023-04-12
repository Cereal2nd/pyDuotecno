"""Main interface to the duotecno bus."""

import asyncio
import logging
import sys
from duotecno.protocol import Packet
from duotecno.handler import PacketHandler

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("asyncio").setLevel(logging.DEBUG)
log = logging.getLogger()


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
    handler: PacketHandler = None
    nodes: dict

    async def connect(self, host, port, password) -> None:
        """Initialize the connection."""
        self.reader, self.writer = await asyncio.open_connection(host, port)
        self.readerTask = asyncio.Task(self.readTask())
        self.loginOK = asyncio.Event()
        self.nodes = {}
        self.handler = PacketHandler(self.write, self.nodes, self.loginOK)
        # TODO encode password
        await self.write("[214,3,8,100,117,111,116,101,99,110,111]")
        await self.loginOK.wait()
        await self.write("[209,0]")

    async def write(self, msg) -> None:
        """Send a message."""
        log.debug(f"Send: {msg}")
        msg = f"{msg}{chr(10)}"
        self.writer.write(msg.encode())
        await self.writer.drain()

    async def readTask(self):
        """Reader task."""
        while True:
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
                log.error(e)
                log.error(tmp)
            log.debug(f"Receive: {pc}")
            await self.handler.handle(pc)
