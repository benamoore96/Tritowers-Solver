from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

class Skin(str, Enum):
    CASH_POT="cashpot_tritowers"; TOURNAMENT="tritowers_tournament"; UNKNOWN="unknown"
class UIState(str, Enum):
    PLAY="play"; MENU="menu"; RESULT="result"; TRANSITION="transition"; UNKNOWN="unknown"
class SlotState(str, Enum):
    EMPTY="empty"; COVERED="covered"; FACE_UP="face_up"; UNKNOWN="unknown"
class UnsupportedReason(str, Enum):
    NO_IMAGE="no_image"; SCREEN_NOT_FOUND="screen_quadrilateral_not_found"; SCREEN_NOT_RECTIFIED="screen_not_rectified"; IMAGE_TOO_SMALL="image_too_small"; DEGENERATE_QUADRILATERAL="degenerate_quadrilateral"; UNSUPPORTED_UI="unsupported_ui_state_or_variant"; ANCHORS_NOT_CALIBRATED="supported_skin_anchors_not_yet_calibrated"; LOW_READABILITY="low_readability"

@dataclass(frozen=True)
class RightsRecord:
    source_url:str|None=None; permission_basis:str|None=None; private_research_only:bool=True; captured_by:str|None=None
@dataclass(frozen=True)
class CaptureMetadata:
    session_id:str|None=None; machine_id:str|None=None; venue_id:str|None=None; variant:str|None=None; build:str|None=None; theme:str|None=None; device:str|None=None; orientation:str|None=None; angle:str|None=None; glare:str|None=None; blur:str|None=None; occlusion:str|None=None; exposure:str|None=None; moire:str|None=None; width:int|None=None; height:int|None=None; schema_version:str="0.2.0"; rights:RightsRecord=RightsRecord()
@dataclass(frozen=True)
class QualityFlags:
    too_small:bool=False; low_contrast:bool=False; manual_corners_used:bool=False; screen_not_found:bool=False; degenerate_corners:bool=False
@dataclass(frozen=True)
class SlotObservation:
    slot_id:str; polygon:tuple[tuple[float,float],...]; box:tuple[int,int,int,int]; state:SlotState=SlotState.UNKNOWN; rank:str|None=None; suit:str|None=None; confidence:float=0.0; adjudication:str|None=None
    def __post_init__(self):
        if self.state is not SlotState.FACE_UP and (self.rank is not None or self.suit is not None): raise ValueError("Rank and suit may only be recorded for visible face-up cards.")
@dataclass(frozen=True)
class GeometryResult:
    success:bool; screen_corners:tuple[tuple[float,float],...]|None; confidence:float; manual:bool=False; unsupported_reason:UnsupportedReason|None=None
@dataclass(frozen=True)
class RecognitionResult:
    skin:Skin; ui_state:UIState; geometry:GeometryResult; regions:dict[str,tuple[int,int,int,int]]=field(default_factory=dict); slots:tuple[SlotObservation,...]=(); confidence:float=0.0; quality:QualityFlags=QualityFlags(); readable:bool=False; unsupported_reason:UnsupportedReason|None=None; metadata:CaptureMetadata=CaptureMetadata()
    def to_dict(self)->dict[str,Any]:
        value=asdict(self); value["skin"]=self.skin.value; value["ui_state"]=self.ui_state.value
        value["unsupported_reason"]=self.unsupported_reason.value if self.unsupported_reason else None
        value["geometry"]["unsupported_reason"]=self.geometry.unsupported_reason.value if self.geometry.unsupported_reason else None
        for index,slot in enumerate(self.slots): value["slots"][index]["state"]=slot.state.value
        return value
