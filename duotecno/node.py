import logging

from duotecno.protocol import NodeType, EV_NODEDATABASEINFO_2
from duotecno.unit import (
    BaseUnit,
    SwitchUnit,
    SensUnit,
    DimUnit,
    DuoswitchUnit,
    VirtualUnit,
)


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
        self._log = logging.getLogger("pyduotecno-node")
        self.name = name
        self.address = address
        self.index = index
        self.numUnits = numUnits
        self.nodeType = nodeType
        self.writer = writer
        self.units = {}
        self._log.info(f"New node found: {self.name}")

    def __repr__(self) -> str:
        items = []
        for k, v in self.__dict__.items():
            if k not in ["_log", "writer"]:
                items.append(f"{k} = {v!r}")
        return "{}[{}]".format(type(self), ", ".join(items))

    async def requestUnits(self) -> None:
        self._log.debug(f"Node {self.name}: Requesting units")
        for i in range(self.numUnits - 1):
            await self.writer(f"[209,2,{self.address},{i}]")

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_NODEDATABASEINFO_2):
            if packet.unit not in self.units:
                u = BaseUnit
                if packet.unitTypeName == "SWITCH":
                    u = SwitchUnit
                elif packet.unitTypeName == "SENS":
                    u = SensUnit
                elif packet.unitTypeName == "DIM":
                    u = DimUnit
                elif packet.unitTypeName == "DUOSWITCH":
                    u = DuoswitchUnit
                elif packet.unitTypeName == "VIRTUAL":
                    u = VirtualUnit
                else:
                    self._log.warning(f"Unhandled unitType: {packet.unitTypeName}")
                self.units[packet.unit] = u(
                    self, name=packet.unitName, unit=packet.unit, writer=self.writer
                )
                await self.units[packet.unit].requestStatus()
            return
        if hasattr(packet, "unit") and packet.unit in self.units:
            await self.units[packet.unit].handlePacket(packet)
            print(self.units)
            return
