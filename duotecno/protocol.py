from __future__ import annotations
from typing import final, Deque
from enum import Enum, unique
from dataclasses import dataclass, field
import collections
import sys
import json


@unique
class MsgType(Enum):
    EV_UNITCONTROLSTATUS = 4
    EV_UNITDIMSTATUS = 5
    EV_UNITSWITCHSTATUS = 6
    EV_UNITSENSSTATUS = 7
    EV_MESSAGEERROR = 17
    EV_NODERESET = 18
    EV_UNITAUDIOSTATUS = 23
    EV_UNITDUOSWITCHSTATUS = 38
    EV_UNITAVMATRIXSTATUS = 54
    EV_UNITDEFAULTSTATUS = 48
    EV_NODEDATABASEINFO = 64
    EV_APPLICATIONTASKSTATUS = 66
    EV_CLIENTCONNECTSET = 67
    EV_UNITMACROCOMMAND = 69
    EV_UNITAUDIOEXTSTATUS = 70
    EV_TIMEDATESTATUS = 71
    EV_HEARTBEATSTATUS = 72
    EV_SCHEDULESTATUS = 73
    EV_NODEMANAGEMENTINFO = 74
    EV_ACCESSLEVELSET = 75
    EV_VIDEOPHONESTATUS = 76
    EV_REGISTERMAP = 77
    FC_UNITDIMREQUESTSTATUS = 131
    FC_UNITSENSSET = 136
    FC_UNITREQUESTSENSSTATUS = 137
    FC_NODERESETSET = 155
    FC_UNITAUDIOBASICSET = 159
    FC_UNITDIMSET = 162
    FC_UNITSWITCHSET = 163
    FC_UNITCONTROLSET = 168
    FC_TIMEDATE = 170
    FC_UNITIRTXSET = 173
    FC_UNITDUOSWITCHSET = 182
    FC_CHECKIRRXCODE = 192
    FC_UNITVIDEOMUXSET = 193
    FC_UNITAVMATRIXSET = 202
    FC_UNITALARMSET = 204
    FC_UNITAUDIOEXTSET = 208
    FC_NODEDATABASEREQUESTSTATUS = 209
    FC_APPLICATIONTASKSET = 212
    FC_REQUESTAPPLICATIONTASKSTATUS = 213
    FC_CLIENTCONNECTSET = 214
    FC_HEARTBEATREQUESTSTATUS = 215
    FC_REQUESTTIMEDATE = 216
    FC_SCHEDULESET = 217
    FC_REQUESTSCHEDULE = 218
    FC_NODEMANAGEMENTSET = 219
    FC_REQUESTNODEMANAGEMENT = 220
    FC_NODEDATABASESET = 221
    FC_ACCESSLEVELSET = 222
    FC_VIDEOPHONESET = 223
    FC_REGISTERMAP = 224
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> MsgType:
        return cls.UNKNOWN


@dataclass
class Packet:
    """Basic structure for a packet."""

    cmdName: str = field(init=False)
    cmdCode: int = field(repr=False)
    method: int
    data: Deque[int]
    cls: BaseMessage | None = field(init=False)

    def __lt__(self, other: Packet) -> bool:
        if isinstance(other.cls, EV_HEARTBEATSTATUS_1):
            return True
        return False

    def __post_init__(self) -> None:
        """fill in the command name, make the subsclass."""
        try:
            self.cmdName = MsgType(self.cmdCode).name
        except ValueError:
            self.cmdName = "UNKNOWN"
        self.data = collections.deque(self.data)
        tmp = getattr(sys.modules[__name__], f"{self.cmdName}_{self.method}", None)
        if tmp:
            self.cls = tmp(self.data)
            # self.data should be empty once the message consumed it
            if len(self.data) != 0:
                print(f"ERROR!!! Not all data consumed: {self}")
        else:
            self.cls = None


def calc_value(msb: int, lsb: int) -> int:
    return (256 * msb) + lsb


class BaseMessage:
    def __init__(self, data: Deque[int]) -> None:
        pass

    def to_json(self) -> str:
        return json.dumps(self.to_json_basic())

    def to_json_basic(self) -> dict[str, str]:
        """
        Create JSON structure with generic attributes
        """
        me = {}
        me["name"] = str(self.__class__.__name__)
        me.update(self.__dict__.copy())
        for key in me.copy():
            if key == "name":
                continue
            if isinstance(me[key], str):
                continue
            if callable(getattr(self, key)) or key.startswith("__"):
                del me[key]
            if isinstance(me[key], Enum):
                me[key] = me[key].name
            if isinstance(me[key], (bytes, bytearray)):
                me[key] = str(me[key], "utf-8")
        return me

    def __repr__(self) -> str:
        return self.to_json()


class BaseNodeUnitMessage(BaseMessage):
    address: int
    unit: int

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        self.address = data.popleft()
        self.unit = data.popleft()


class BaseNodeUnitTypeMessage(BaseNodeUnitMessage):
    unitType: int

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        self.unitType = data.popleft()


class EV_HEARTBEATSTATUS_1(BaseMessage):
    pass


class EV_CLIENTCONNECTSET_3(BaseMessage):
    loginOk: bool

    def __init__(self, data: Deque[int]) -> None:
        self.loginOK = data.popleft()


@unique
class DbState(Enum):
    Empty = 0
    Busy = 1
    Ready = 2


class EV_NODEDATABASEINFO_5(BaseMessage):
    state: DbState

    def __init__(self, data: Deque[int]) -> None:
        self.state = data.popleft()


class EV_NODEDATABASEINFO_0(BaseMessage):
    numNode: int

    def __init__(self, data: Deque[int]) -> None:
        self.numNode = data.popleft()


class EV_UNITMACROCOMMAND_0(BaseNodeUnitMessage):
    event: int
    state: int
    code1: int
    code2: int

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        self.event = data.popleft()
        self.state = data.popleft()
        self.code1 = data.popleft()
        self.code2 = data.popleft()


@unique
class NodeType(Enum):
    Standard = 1
    Gateway = 4
    Modem = 8
    Gui = 32
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> NodeType:
        return cls.UNKNOWN


class EV_NODEDATABASEINFO_1(BaseMessage):
    index: int
    address: int
    nodeName: str
    numUnits: int
    nodeType: NodeType
    nodeTypeName: str
    flags: int

    def __init__(self, data: Deque[int]) -> None:
        self.index = data.popleft()
        self.address = data.popleft()
        # next 4 are no needed
        [data.popleft() for _i in range(4)]
        self.nodeName = "".join([chr(data.popleft()) for _i in range(data.popleft())])
        self.numUnits = data.popleft()
        self.nodeType = NodeType(data.popleft())
        self.nodeTypeName = NodeType(self.nodeType).name
        self.flags = data.popleft()


@unique
class UnitType(Enum):
    DIM = 1
    SWITCH = 2
    CONTROL = 3
    SENS = 4
    AUDIO_EXT = 5
    VIRTUAL = 7
    DUOSWITCH = 8
    AUDIO_BASIC = 10
    AVMATRIC = 11
    IRTX = 12
    VIDEOMUX = 14
    UNKNOWN = 255

    @classmethod
    def _missing_(cls, value: object) -> UnitType:
        return cls.UNKNOWN


class EV_NODEDATABASEINFO_2(BaseMessage):
    address: int
    unit: int
    laddress: int
    lunit: int
    unitName: str
    unitType: int
    unitTypeName: str
    unitFlags: int

    def __init__(self, data: Deque[int]) -> None:
        self.address = data.popleft()
        self.unit = data.popleft()
        self.laddress = data.popleft()
        self.lunit = data.popleft()
        self.unitName = "".join([chr(data.popleft()) for _i in range(data.popleft())])
        self.unitType = data.popleft()
        self.unitTypeName = UnitType(self.unitType).name
        self.unitFlags = data.popleft()


@final
@unique
class SwitchStatus(Enum):
    OFF = 0
    ON = 1
    PIRTIMED = 2


class EV_UNITSWITCHSTATUS_0(BaseNodeUnitTypeMessage):
    state: int
    stateName: str

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        # config, reserved
        data.popleft()
        self.state = data.popleft()
        self.stateName = SwitchStatus(self.state).name


class EV_UNITDIMSTATUS_0(BaseNodeUnitTypeMessage):
    state: int
    stateName: str
    dimValue: int

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        # config, reserved
        data.popleft()
        self.state = data.popleft()
        self.stateName = SwitchStatus(self.state).name
        self.dimValue = data.popleft()


@final
@unique
class DuoswitchStatus(Enum):
    IDLE = 0
    IDLE_DOWN = 1
    IDLE_UP = 2
    BUSY_DOWN = 3
    BUSY_UP = 4


class EV_UNITDUOSWITCHSTATUS_0(BaseNodeUnitTypeMessage):
    state: int
    stateName: str

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        # config, reserved
        data.popleft()
        self.state = data.popleft()
        self.stateName = DuoswitchStatus(self.state).name


@final
@unique
class SensType(Enum):
    TEMPERATURE = 0
    PH = 1
    LUX = 2
    AMPERE = 3


@final
@unique
class SensControl(Enum):
    OFF = 0
    ON = 1


@final
@unique
class SensState(Enum):
    IDLE = 0
    HEATING = 1
    COOLING = 2


@final
@unique
class SensPreset(Enum):
    SUN = 0
    HALF_SUN = 1
    MOON = 2
    HALF_MOON = 3


@final
@unique
class SensWorkingmode(Enum):
    AUTO = 0
    HEATING = 1
    COOLING = 2
    DRY = 3
    FAN = 4
    UNKNOWN = 255


@final
@unique
class SensFanspeed(Enum):
    SPEED1 = 0
    SPEED2 = 1
    SPEED3 = 2
    SPEED4 = 3
    SPEED5 = 4
    AUTO = 255


def sens_calc_value(msb: int, lsb: int) -> float:
    val = calc_value(msb, lsb)
    if (val & (1 << 15)) != 0:
        val = val - (1 << 16)
    return val / 10


class EV_UNITSENSSTATUS_0(BaseNodeUnitTypeMessage):
    config: int
    configName: str
    controlState: int
    controlStateName: str
    state: int
    stateName: str
    preset: int
    presetName: str
    value: float
    sun: float
    halfsun: float
    moon: float
    halfmoon: float

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        self.config = data.popleft()
        self.configName = SensType(self.config).name
        self.controlState = data.popleft()
        self.controlStateName = SensControl(self.controlState).name
        self.state = data.popleft()
        self.stateName = SensState(self.state).name
        self.preset = data.popleft()
        self.presetName = SensPreset(self.preset).name
        self.value = sens_calc_value(data.popleft(), data.popleft())
        self.sun = sens_calc_value(data.popleft(), data.popleft())
        self.halfsun = sens_calc_value(data.popleft(), data.popleft())
        self.moon = sens_calc_value(data.popleft(), data.popleft())
        self.halfmoon = sens_calc_value(data.popleft(), data.popleft())


class EV_UNITSENSSTATUS_1(EV_UNITSENSSTATUS_0):
    offset: float
    swing: float
    workingMode: int
    workingModeName: str
    fanSpeed: int
    fanSpeedName: str
    swingMode: int
    swingModeName: str

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        self.offset = sens_calc_value(data.popleft(), data.popleft())
        self.swing = sens_calc_value(data.popleft(), data.popleft())
        self.workingMode = data.popleft()
        self.workingModeName = SensWorkingmode(self.workingMode).name
        self.fanSpeed = data.popleft()
        self.fanSpeedName = SensFanspeed(self.fanSpeed).name
        self.swingMode = data.popleft()
        self.swingModeName = SensControl(self.swingMode).name


@final
@unique
class ControLStatus(Enum):
    OFF = 0
    ON = 1


class EV_UNITCONTROLSTATUS_0(BaseNodeUnitTypeMessage):
    status: int
    statusName: str

    def __init__(self, data: Deque[int]) -> None:
        super().__init__(data)
        # config ignore
        data.popleft()
        self.status = data.popleft()
        self.statusName = ControLStatus(self.status).name
