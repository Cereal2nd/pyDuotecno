"""Basic example to read the bus."""
import asyncio
from duotecno.controller import PyDuotecno


async def test():
    """Basic aio call."""
    tmp = PyDuotecno()
    await tmp.connect("host.duotecno-ip.be", 19001, "")
    await asyncio.sleep(6000000000)


asyncio.run(test())
