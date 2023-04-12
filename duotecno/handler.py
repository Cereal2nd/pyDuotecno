from duotecno.protocol import (
    Packet,
    EV_CLIENTCONNECTSET_3,
    EV_NODEDATABASEINFO_0,
    EV_NODEDATABASEINFO_1,
    EV_NODEDATABASEINFO_2,
)


class PacketHandler:
    def __init__(self, write, nodes, loginOK):
        self.write = write
        self.loginOK = loginOK
        self.nodes = nodes

    async def handle(self, packet: Packet):
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
                self.nodes[packet.cls.address] = {
                    "name": packet.cls.nodeName,
                    "index": packet.cls.index,
                    "numUnits": packet.cls.numUnits,
                    "nodeType": packet.cls.nodeType,
                    "units": {},
                }
                for i in range(packet.cls.numUnits - 1):
                    await self.write(f"[209,2,{packet.cls.address},{i}]")
            return
        if isinstance(packet.cls, EV_NODEDATABASEINFO_2):
            pass
            return
        print("TODO handle")
