from typing import final
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
        self._log.info(
            f"New Unit: '{self.node.name}' => '{self.name}' = {type(self).__name__}"
        )

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
    _state: int

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_UNITSWITCHSTATUS_0):
            await self._update({"state": packet.state})
            return
        await super().handlePacket(packet)


class DuoswitchUnit(BaseUnit):
    _unitType: final = 8
    _state: int

    async def handlePacket(self, packet) -> None:
        if isinstance(packet, EV_UNITDUOSWITCHSTATUS_0):
            await self._update({"state": packet.state})
            return
        await super().handlePacket(packet)


class VirtualUnit(BaseUnit):
    _unitType: final = 7
    pass
