from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO,Iterable
import cv2,numpy as np
from PIL import Image,ImageOps,UnidentifiedImageError
MAX_BYTES=12*1024*1024; MAX_PIXELS=20_000_000; MIN_SIDE=160; MIN_QUAD_AREA=1000.0; MIN_EDGE=20.0; OUTPUT_SIZE=(1024,768); ALLOWED_FORMATS={"JPEG","PNG","WEBP","HEIF","HEIC"}
class ImageInputError(ValueError): pass
@dataclass(frozen=True)
class ScreenExtraction:
    normalized:Image.Image; rectified:Image.Image|None; overlay:Image.Image; corners:tuple[tuple[float,float],...]|None; confidence:float; manual:bool; unsupported_reason:str|None=None

def _read_bounded(source:str|Path|BinaryIO|bytes)->bytes:
    if isinstance(source,bytes): data=source
    elif isinstance(source,(str,Path)):
        path=Path(source)
        if path.stat().st_size>MAX_BYTES: raise ImageInputError("Image exceeds the 12 MB upload limit.")
        data=path.read_bytes()
    else: data=source.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise ImageInputError("Image exceeds the 12 MB upload limit.")
    return data

def normalize_image(source)->Image.Image:
    try:
        with Image.open(BytesIO(_read_bounded(source))) as image:
            if image.format not in ALLOWED_FORMATS: raise ImageInputError(f"Unsupported image format: {image.format}")
            if image.width*image.height>MAX_PIXELS: raise ImageInputError("Image exceeds the 20 megapixel limit.")
            return ImageOps.exif_transpose(image).convert("RGB").copy()
    except (UnidentifiedImageError,OSError) as error: raise ImageInputError("Could not decode this image.") from error

def order_corners(points)->np.ndarray:
    points=np.asarray(list(points),dtype=np.float32)
    if points.shape!=(4,2) or not np.isfinite(points).all(): raise ImageInputError("Exactly four finite corner points are required.")
    sums=points.sum(axis=1); differences=np.diff(points,axis=1).ravel()
    ordered=np.array([points[np.argmin(sums)],points[np.argmin(differences)],points[np.argmax(sums)],points[np.argmax(differences)]],dtype=np.float32)
    contour=ordered.reshape((-1,1,2)); edges=[np.linalg.norm(ordered[(i+1)%4]-ordered[i]) for i in range(4)]
    if len({tuple(p) for p in ordered.tolist()})!=4 or abs(cv2.contourArea(contour))<MIN_QUAD_AREA or min(edges)<MIN_EDGE or not cv2.isContourConvex(contour): raise ImageInputError("Screen quadrilateral is degenerate or too small.")
    return ordered

def rectify(image,corners):
    source=order_corners(corners); width,height=OUTPUT_SIZE; destination=np.array([[0,0],[width-1,0],[width-1,height-1],[0,height-1]],dtype=np.float32)
    return Image.fromarray(cv2.warpPerspective(np.asarray(image),cv2.getPerspectiveTransform(source,destination),(width,height)),"RGB")
def _overlay(image,corners):
    array=np.asarray(image).copy()
    if corners is not None: cv2.polylines(array,[corners.astype(np.int32)],True,(66,245,170),4,cv2.LINE_AA)
    return Image.fromarray(array,"RGB")
def detect_screen(image):
    gray=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2GRAY); edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),50,150); contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE); total=image.width*image.height; candidates=[]
    for contour in contours:
        polygon=cv2.approxPolyDP(contour,0.02*cv2.arcLength(contour,True),True); area=abs(cv2.contourArea(polygon))
        if len(polygon)==4 and cv2.isContourConvex(polygon) and .18*total<=area<=.98*total: candidates.append((area,polygon.reshape(4,2).astype(np.float32)))
    if not candidates:return None,0.0
    area,points=max(candidates,key=lambda item:item[0]); return order_corners(points),min(.85,.35+.5*area/total)
def extract_screen(source,manual_corners=None):
    image=normalize_image(source)
    if manual_corners is not None:
        corners=order_corners(manual_corners); return ScreenExtraction(image,rectify(image,corners),_overlay(image,corners),tuple(map(tuple,corners)),1.0,True)
    corners,confidence=detect_screen(image)
    if corners is None:return ScreenExtraction(image,None,_overlay(image,None),None,0.0,False,"image_too_small" if min(image.size)<MIN_SIDE else "screen_quadrilateral_not_found")
    return ScreenExtraction(image,rectify(image,corners),_overlay(image,corners),tuple(map(tuple,corners)),confidence,False)
