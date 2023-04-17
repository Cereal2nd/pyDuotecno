from duotecno.protocol import NodeType, EV_NODEDATABASEINFO_2
from duotecno.unit import BaseUnit


class Node:
    name: str
    index: int
    nodeType: NodeType
    address: int
    numUnits: int
    units: dict

    def __init__(
        self,
        name: str,
        address: int,
        index: int,
        nodeType: NodeType,
        numUnits: int,
        writer,
    ) -> None:
        self.name = name
        self.address = address
        self.index = index
        self.numUnits = numUnits
        self.nodeType = nodeType
        self.write = writer
        self.units = {}

    async def requestUnits(self) -> None:
        for i in range(self.numUnits - 1):
            await self.write(f"[209,2,{self.address},{i}]")

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_NODEDATABASEINFO_2):
            if packet.unit not in self.units:
                print(f"new unit: {packet.unitType}")
                self.units[packet.unit] = BaseUnit(
                    self, name=packet.unitName, unit=packet.unit, writer=self.write
                )
                # await self.units[packet.cls.unit].requestStatus()
            return
        if hasattr(packet, "unit") and packet.unit in self.units:
            await self.units[packet.unit].handlePacket(packet)
            return
