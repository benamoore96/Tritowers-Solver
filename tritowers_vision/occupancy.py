import numpy as np
from PIL import Image
from .layout import tableau_boxes, WASTE_BOX, STOCK_BOX
from .schema import SlotState

def classify_patch(patch: Image.Image) -> tuple[SlotState, float]:
    """Covered (red card back), face-up (cream card face) or empty/unknown. Heuristic."""
    a = np.asarray(patch.convert("RGB")).astype(float)
    if a.size == 0: return SlotState.UNKNOWN, 0.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cream = float(np.mean((r > 190) & (g > 180) & (b > 150) & (r - b < 70)))
    red = float(np.mean((r > 140) & (g < 90) & (b < 100)))
    if cream > .55: return SlotState.FACE_UP, min(1.0, cream)
    if red > .25: return SlotState.COVERED, min(1.0, red * 2)
    if cream < .1 and red < .08: return SlotState.EMPTY, .6
    return SlotState.UNKNOWN, 0.3

def occupancy(rectified: Image.Image) -> dict[str, tuple[SlotState, float]]:
    out = {}
    for slot, (x0, y0, x1, y1) in tableau_boxes().items():
        out[slot] = classify_patch(rectified.crop((x0 + 8, y0 + 4, x1 - 8, y1 - 4)))
    out["waste"] = classify_patch(rectified.crop(WASTE_BOX))
    out["stock"] = classify_patch(rectified.crop(STOCK_BOX))
    return out
