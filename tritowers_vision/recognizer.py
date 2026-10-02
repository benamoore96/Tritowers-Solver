from PIL import Image,ImageStat
from .schema import CaptureMetadata,GeometryResult,QualityFlags,RecognitionResult,Skin,UIState,UnsupportedReason
def recognize(rectified:Image.Image|None,corners=None,manual=False,metadata=None)->RecognitionResult:
    metadata=metadata or CaptureMetadata()
    if rectified is None:
        reason=UnsupportedReason.SCREEN_NOT_RECTIFIED
        return RecognitionResult(Skin.UNKNOWN,UIState.UNKNOWN,GeometryResult(False,corners,0.0,manual,reason),confidence=0.0,quality=QualityFlags(screen_not_found=True,manual_corners_used=manual),readable=False,unsupported_reason=reason,metadata=metadata)
    low_contrast=ImageStat.Stat(rectified.convert("L")).stddev[0]<12; reason=UnsupportedReason.LOW_READABILITY if low_contrast else UnsupportedReason.ANCHORS_NOT_CALIBRATED
    return RecognitionResult(Skin.UNKNOWN,UIState.UNKNOWN,GeometryResult(True,corners,1.0 if manual else .5,manual),confidence=0.0,quality=QualityFlags(low_contrast=low_contrast,manual_corners_used=manual),readable=not low_contrast,unsupported_reason=reason,metadata=metadata)
