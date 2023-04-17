class BaseUnit:
    name: str
    unit: int

    def __init__(
        self,
        node,
        name: str,
        unit: int,
        writer,
    ) -> None:
        self.node = node
        self.name = name
        self.unit = unit
        self.write = writer

    async def handlePacket(self, packet) -> None:
        print("unit message")


class SensUnit(BaseUnit):
    pass


class DimUnit(BaseUnit):
    pass


class SwitchUnit(BaseUnit):
    pass


class DuoswitchUnit(BaseUnit):
    pass
