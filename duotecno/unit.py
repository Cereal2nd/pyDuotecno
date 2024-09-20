from __future__ import annotations
from typing import Awaitable, Callable, TYPE_CHECKING
import logging
from duotecno.protocol import (
    EV_UNITDUOSWITCHSTATUS_0,
    EV_UNITDIMSTATUS_0,
    EV_UNITSWITCHSTATUS_0,
    EV_UNITSENSSTATUS_0,
    EV_UNITSENSSTATUS_1,
    EV_UNITCONTROLSTATUS_0,
    EV_UNITMACROCOMMAND_0,
    calc_value,
)

if TYPE_CHECKING:
    from duotecno.node import Node
    from duotecno.protocol import BaseMessage


class BaseUnit:
    _unitType: int = 0
    _available: bool = True
    _on_status_update: list[Callable[[], Awaitable[None]]] = []
    name: str = ""
    unit: int = 0
    available: bool = True

    def __init__(
        self,
        node: Node,
        name: str,
        unit: int,
        writer: Callable[[str], Awaitable[None]],
    ) -> None:
        self._log = logging.getLogger("pyduotecno-unit")
        self.node = node
        self.name = name
        self.unit = unit
        self.writer = writer
        self._log.info(
            f"New Unit: '{self.node.name}' => '{self.name}' = {type(self).__name__}"
        )

    async def enable(self) -> None:
        await self._update({"available": True})

    async def disable(self) -> None:
        await self._update({"available": False})

    def is_available(self) -> bool:
        return self._available

    def get_node_address(self) -> int:
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
            if k not in ["_log", "writer", "node"]:
                items.append(f"{k} = {v!r}")
        return "{}[{}]".format(type(self), ", ".join(items))

    async def handlePacket(self, packet: BaseMessage) -> None:
        self._log.debug(f"Unhandled unit packet: {packet}")

    async def requestStatus(self) -> None:
        if self._unitType:
            await self.writer(
                f"[209,3,{self.node.address},{self.unit},{self._unitType}]"
            )

    async def _update(self, data: dict[str, str | int | float | bool]) -> None:
        for key, new_val in data.items():
            cur_val = getattr(self, f"_{key}", None)
            if cur_val is None or cur_val != new_val:
                setattr(self, f"_{key}", new_val)
                for m in self._on_status_update:
                    await m()


class SensUnit(BaseUnit):
    _unitType: int = 4
    _state: int = 0
    _preset: int = 0
    _cur_temp: float = 0.0
    _setp_sun: float = 0.0
    _setp_hsun: float = 0.0
    _setp_moon: float = 0.0
    _setp_hmoon: float = 0.0
    _offset: float = 0.0
    _swing_angle: float = 0.0
    _woking_mode: float = 0.0
    _fan_speed: float = 0.0
    _swing_mode: float = 0.0

    async def handlePacket(self, packet: BaseMessage) -> None:
        if isinstance(packet, EV_UNITSENSSTATUS_0) or isinstance(
            packet, EV_UNITSENSSTATUS_1
        ):
            tmp: dict[str, str | int | float] = {}
            if packet.controlState == 0:
                tmp["state"] = 0
            else:
                tmp["state"] = packet.state
            tmp["preset"] = packet.preset
            tmp["cur_temp"] = packet.value
            tmp["setp_sun"] = packet.sun
            tmp["setp_hsun"] = packet.halfsun
            tmp["setp_moon"] = packet.moon
            tmp["setp_hmoon"] = packet.halfmoon
            if isinstance(packet, EV_UNITSENSSTATUS_1):
                tmp["offset"] = packet.offset
                tmp["swing_angle"] = packet.swingMode
                tmp["working_mode"] = packet.workingMode
                tmp["fan_speed"] = packet.fanSpeed
                tmp["swing_mode"] = packet.swingMode
            await self._update(tmp)
            return
        if isinstance(packet, EV_UNITMACROCOMMAND_0):
            if packet.event == 9:
                await self._update({"state": packet.state})
            elif packet.event == 10:
                await self._update({"mode": packet.state})
            # TODO event 11
            elif packet.event == 12:
                await self._update({"working_mode": packet.state})
            elif packet.event == 13:
                await self._update({"fan_speed": packet.state})
            # TODO event 14
            elif packet.event == 15:
                await self._update({"Swing_mode": packet.state})
            return
        await super().handlePacket(packet)

    async def requestStatus(self) -> None:
        await self.writer(f"[137,16,{self.node.address},{self.unit}]")
        await self.writer(f"[137,17,{self.node.address},{self.unit}]")
        await self.writer(f"[137,18,{self.node.address},{self.unit}]")
        await self.writer(f"[137,19,{self.node.address},{self.unit}]")
        await super().requestStatus()

    async def set_preset(self, preset: int) -> None:
        await self.writer(f"[136,13,{self.node.address},{self.unit},{preset}]")

    async def turn_off(self) -> None:
        await self.writer(f"[136,3,{self.node.address},{self.unit},0]")

    async def turn_on(self) -> None:
        await self.writer(f"[136,3,{self.node.address},{self.unit},1]")

    async def set_temp(self, temp: float) -> None:
        msb, lsb = divmod(temp * 10, 256)
        msb = int(msb)
        lsb = int(lsb)
        await self.writer(
            f"[136,1,{self.node.address},{self.unit},{self._preset},{msb},{lsb}]"
        )

    def get_state(self) -> int:
        return self._state

    def get_cur_temp(self) -> float:
        return self._cur_temp

    def get_target_temp(self) -> float:
        if self._preset == 0:
            return self._setp_sun
        elif self._preset == 1:
            return self._setp_hsun
        elif self._preset == 2:
            return self._setp_moon
        else:
            return self._setp_hmoon

    def get_preset(self) -> int:
        return self._preset


class DimUnit(BaseUnit):
    _unitType: int = 1
    _state: int = 0
    _value: int = 0

    async def handlePacket(self, packet: BaseMessage) -> None:
        if isinstance(packet, EV_UNITDIMSTATUS_0):
            await self._update({"state": packet.state, "value": packet.dimValue})
            return
        if isinstance(packet, EV_UNITMACROCOMMAND_0):
            if packet.event == 6:
                await self._update({"state": packet.state})
            elif packet.state == 8:
                await self._update({"value": calc_value(packet.code1, packet.code2)})
            return
        await super().handlePacket(packet)

    def is_on(self) -> bool:
        if self._state == 0:
            return False
        return True

    def get_dimmer_state(self) -> int:
        return self._value

    async def set_dimmer_state(self, value: int | None = None) -> None:
        # val > 0 => turn on
        # val 0 but not None => turn off
        # val = None => restore
        if value and value > 0:
            # set state and turn on
            await self.writer(f"[162,10,{self.node.address},{self.unit}]")
            await self.writer(f"[162,3,{self.node.address},{self.unit},{value}]")
        elif value is not None:
            # turn off
            await self.writer(f"[162,9,{self.node.address},{self.unit}]")
        else:
            # send turn on (restore state)
            await self.writer(f"[162,10,{self.node.address},{self.unit}]")


class SwitchUnit(BaseUnit):
    _unitType: int = 2
    _state: int = 0

    async def handlePacket(self, packet: BaseMessage) -> None:
        if isinstance(packet, EV_UNITSWITCHSTATUS_0):
            await self._update({"state": packet.state})
            return
        if isinstance(packet, EV_UNITMACROCOMMAND_0):
            if packet.event == 5:
                # pir timed
                await self._update({"state": 2})
            else:
                await self._update({"state": packet.state})
            return
        await super().handlePacket(packet)

    def is_on(self) -> bool:
        if self._state == 0:
            return False
        return True

    async def turn_on(self) -> None:
        """Switch on."""
        await self.writer(f"[163,3,{self.node.address},{self.unit}]")

    async def turn_off(self) -> None:
        """Switch off."""
        await self.writer(f"[163,2,{self.node.address},{self.unit}]")


class DuoswitchUnit(BaseUnit):
    _unitType: int = 8
    _state: int = 1

    async def handlePacket(self, packet: BaseMessage) -> None:
        if isinstance(packet, EV_UNITDUOSWITCHSTATUS_0):
            await self._update({"state": packet.state})
            return
        await super().handlePacket(packet)

    def is_opening(self) -> bool:
        if self._state == 4:
            return True
        return False

    def is_closing(self) -> bool:
        if self._state == 3:
            return True
        return False

    def is_closed(self) -> bool:
        if self._state == 1:
            return True
        return False

    async def open(self) -> None:
        """Move up."""
        await self.stop()
        await self.writer(f"[182,4,{self.node.address},{self.unit}]")

    async def close(self) -> None:
        """Move down."""
        await self.stop()
        await self.writer(f"[182,5,{self.node.address},{self.unit}]")

    async def stop(self) -> None:
        """Stop the motor."""
        await self.writer(f"[182,3,{self.node.address},{self.unit}]")


class VirtualUnit(BaseUnit):
    _unitType: int = 7
    _status: int = 0

    async def handlePacket(self, packet: BaseMessage) -> None:
        if isinstance(packet, EV_UNITCONTROLSTATUS_0):
            await self._update({"status": packet.status})
            return
        if isinstance(packet, EV_UNITMACROCOMMAND_0):
            await self._update({"status": packet.state})
            return
        await super().handlePacket(packet)

    def is_on(self) -> bool:
        if self._status == 0:
            return False
        return True


class ControlUnit(VirtualUnit):
    _unitType: int = 3
    pass
