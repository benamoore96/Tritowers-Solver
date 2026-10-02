"""Calibrated single-skin pass: occupancy + gated rank reading -> solver-input draft.

Rank/suit output is only for face-up cards read above the acceptance gate. Everything else is
None (unknown). Hidden cards are never inferred. Stock counter is NOT read yet.
"""
from PIL import Image
from .layout import tableau_boxes, WASTE_BOX
from .occupancy import occupancy
from .rank import corner_box, glyph, match, ACCEPT_SCORE, ACCEPT_MARGIN
from .schema import SlotState

def read(rectified: Image.Image, templates):
    occ, boxes = occupancy(rectified), tableau_boxes(); cards = {}
    for slot in [*boxes, "waste"]:
        state, conf = occ[slot]; rank = None; score = margin = 0.0
        if state is SlotState.FACE_UP:
            box = (WASTE_BOX[0]+4, WASTE_BOX[1]+3, WASTE_BOX[0]+46, WASTE_BOX[1]+40) if slot == "waste" else corner_box(boxes[slot])
            p, score, margin = match(glyph(rectified, box), templates)
            if p is not None and score >= ACCEPT_SCORE and margin >= ACCEPT_MARGIN: rank = p
        cards[slot] = {"state": state.value, "rank": rank, "score": round(score, 2), "margin": round(margin, 2)}
    unresolved = [s for s, c in cards.items() if c["state"] in ("unknown",) or (c["state"] == "face_up" and c["rank"] is None)]
    return {"cards": cards, "needs_human_review": unresolved, "complete": not unresolved and occ["stock"][0] is not SlotState.UNKNOWN,
            "stock_counter": None, "note": "Draft only. Suit not read. Stock counter not read. Human must confirm before solving."}
