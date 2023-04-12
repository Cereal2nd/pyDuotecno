from enum import Enum, unique
from dataclasses import dataclass, field
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
    EV_UNKNOWN = 77
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


@dataclass
class Packet:
    """Basic structure for a packet."""

    cmdName: str = field(init=False)
    cmdCode: int = field(repr=False)
    method: str
    data: list
    cls: type = field(init=False)

    def __post_init__(self):
        """fill in the command nae, make the subsclass."""
        self.cmdName = MsgType(self.cmdCode)
        try:
            tmp = getattr(sys.modules[__name__], MsgType(self.cmdCode).name)
            self.cls = tmp(self.data)
        except Exception as e:
            print(e)
            self.cls = None


class BaseMessage:
    def to_json(self) -> str:
        return json.dumps(self.to_json_basic())

    def to_json_basic(self) -> dict:
        """
        Create JSON structure with generic attributes
        """
        me = {}
        me["name"] = str(self.__class__.__name__)
        me.update(self.__dict__.copy())
        for key in me.copy():
            if key == "name":
                continue
            if callable(getattr(self, key)) or key.startswith("__"):
                del me[key]
            if isinstance(me[key], (bytes, bytearray)):
                me[key] = str(me[key], "utf-8")
        return me

    def __repr__(self) -> str:
        return self.to_json()


class EV_CLIENTCONNECTSET(BaseMessage):
    loginOk: bool

    def __init__(self, data):
        self.loginOK = data[0]
