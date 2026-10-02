"""Template-matching rank reader for the face-up corner index (prototype, single skin)."""
import numpy as np, cv2
from PIL import Image
from .layout import tableau_boxes, WASTE_BOX
RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
def corner_box(slot_box, waste=False):
    x0, y0 = slot_box[0], slot_box[1]
    return (x0 + 4, y0 + 3, x0 + 46, y0 + 40)
def glyph(rectified: Image.Image, box) -> np.ndarray:
    g = np.asarray(rectified.crop(box).convert("L")).astype(np.float32)
    ink = (g < 110).astype(np.uint8)
    # red glyphs are not dark in grayscale; use red-channel darkness of G channel too
    rgb = np.asarray(rectified.crop(box).convert("RGB")).astype(np.int16)
    ink |= ((rgb[..., 1] < 100) & (rgb[..., 0] > 100)).astype(np.uint8)
    ys, xs = np.nonzero(ink)
    if len(xs) < 15: return np.zeros((32, 24), np.float32)
    # keep the topmost connected blob group (rank sits above the suit pip)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink)
    comps = sorted([i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 8], key=lambda i: stats[i, cv2.CC_STAT_TOP])
    if not comps: return np.zeros((32, 24), np.float32)
    top = stats[comps[0], cv2.CC_STAT_TOP]
    keep = [i for i in comps if stats[i, cv2.CC_STAT_TOP] < top + 14 and stats[i, cv2.CC_STAT_HEIGHT] > 8]
    m = np.isin(lab, keep).astype(np.uint8)
    ys, xs = np.nonzero(m)
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    return cv2.resize(crop, (24, 32), interpolation=cv2.INTER_AREA)
def match(g, templates):
    """templates: list of (rank, glyph). Returns (rank, score, margin) or (None,0,0)."""
    if not templates or g.sum() == 0: return None, 0.0, 0.0
    best = {}
    for r, t in templates:
        a, b = g - g.mean(), t - t.mean(); s = float((a * b).sum() / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-6))
        best[r] = max(best.get(r, -1), s)
    order = sorted(best.items(), key=lambda kv: -kv[1])
    second = order[1][1] if len(order) > 1 else -1
    return order[0][0], order[0][1], order[0][1] - second

ACCEPT_SCORE, ACCEPT_MARGIN = 0.6, 0.2   # tuned on 33 samples from 5 photos: optimistic, re-tune on held-out data
def load_templates(path):
    import json
    return [(r, np.array(g, np.float32)) for r, g in json.load(open(path))]
def save_templates(path, templates):
    import json
    json.dump([(r, g.tolist()) for r, g in templates], open(path, "w"))
