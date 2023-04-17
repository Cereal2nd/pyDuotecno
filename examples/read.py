"""Basic example to read the bus."""
import argparse
import asyncio
import logging
import sys
from duotecno.controller import PyDuotecno


async def test(host, port, passw):
    """Basic aio call."""
    tmp = PyDuotecno()
    await tmp.connect(host, port, passw)
    await asyncio.sleep(6000000000)


parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--host", help="The host to connect to")
parser.add_argument("--port", help="The port to connect to")
parser.add_argument("--password", help="The password")
args = parser.parse_args()

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("asyncio").setLevel(logging.DEBUG)

asyncio.run(test(args.host, args.port, args.password))
