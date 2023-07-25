from typing import final, Awaitable, Callable
import logging
from duotecno.protocol import (
    EV_UNITDUOSWITCHSTATUS_0,
    EV_UNITDIMSTATUS_0,
    EV_UNITSWITCHSTATUS_0,
    EV_UNITSENSSTATUS_0,
)


class BaseUnit:
    _unitType: final = None
    _on_status_update: list = []
    name: str
    unit: int

    def __init__(
        self,
        node,
        name: str,
        unit: int,
        writer,
    ) -> None:
        self._log = logging.getLogger("pyduotecno-unit")
        self.node = node
        self.name = name
        self.unit = unit
        self.writer = writer
        self._log.debug(
            f"New Unit: '{self.node.name}' => '{self.name}' = {type(self).__name__}"
        )

    def get_node_address(self) -> str:
        return self.node.get_address()

    def get_node_name(self) -> str:
        return self.node.get_name()

    def get_name(self) -> str:
        return self.name

    def get_number(self) -> int:
        return self.unit

    def on_status_update(self, meth: Callable[[], Awaitable[None]]) -> None:
        self._on_status_update.append(meth)

    def __repr__(self) -> str:
        items = []
        for k, v in self.__dict__.items():
            if k not in ["_log", "writer"]:
                items.append(f"{k} = {v!r}")
        return "{}[{}]".format(type(self), ", ".join(items))

    async def handlePacket(self, packet) -> None:
        self._log.debug(f"Unhandled unit packet: {packet}")

    async def requestStatus(self) -> None:
        if self._unitType:
            await self.writer(
                f"[209,3,{self.node.address},{self.unit},{self._unitType}]"
            )

    async def _update(self, data: dict) -> None:
        for key, new_val in data.items():
            cur_val = getattr(self, f"_{key}", None)
            if cur_val is None or cur_val != new_val:
                setattr(self, f"_{key}", new_val)
                for m in self._on_status_update:
                    await m()


class SensUnit(BaseUnit):
    _unitType: final = 4
    _state: int
    _value: int
    _preset: int

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_UNITSENSSTATUS_0):
            await self._update(
                {"state": packet.state, "value": packet.value, "preset": packet.preset}
            )
            return
        await super().handlePacket(packet)


class DimUnit(BaseUnit):
    _unitType: final = 1
    _state: int
    _value: int

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_UNITDIMSTATUS_0):
            await self._update({"state": packet.state, "value": packet.dimValue})
            return
        await super().handlePacket(packet)


class SwitchUnit(BaseUnit):
    _unitType: final = 2
    _state: int = None

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_UNITSWITCHSTATUS_0):
            await self._update({"state": packet.state})
            return
        await super().handlePacket(packet)

    def is_on(self):
        return self._state

    async def turn_on(self):
        """Switch on."""
        await self.writer(f"[163,3,{self.node.address},{self.unit}]")

    async def turn_off(self):
        """Switch off."""
        await self.writer(f"[163,2,{self.node.address},{self.unit}]")


class DuoswitchUnit(BaseUnit):
    _unitType: final = 8
    _state: int

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_UNITDUOSWITCHSTATUS_0):
            await self._update({"state": packet.state})
            return
        await super().handlePacket(packet)

    def is_opening(self):
        if self._state == 4:
            return True
        return False

    def is_closing(self):
        if self._state == 3:
            return True
        return False

    def is_closed(self):
        if self._state == 1:
            return True
        return False

    async def up(self):
        """Move up."""
        await self.stop()
        await self.writer(f"[182,0,{self.node.address},{self.unit},4]")

    async def down(self):
        """Move down."""
        await self.stop()
        await self.writer(f"[182,0,{self.node.address},{self.unit},5]")

    async def stop(self):
        """Stop the motor."""
        await self.writer(f"[182,0,{self.node.address},{self.unit},3]")


class VirtualUnit(BaseUnit):
    _unitType: final = 7
    pass
