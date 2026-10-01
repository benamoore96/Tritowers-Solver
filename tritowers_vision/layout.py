"""Calibrated slot layout for the one skin seen so far (1024x768 rectified frame).

Calibrated by eye on five owner-supplied crops of a single visible skin. It is NOT
validated across machines, skins or camera angles.
"""
CARD_W = 98
# (row, centres of card x, visible band top, visible band bottom)
_ROWS = (
    ((211, 515, 817), 145, 225),
    ((161, 261, 461, 561, 761, 861), 225, 305),
    (tuple(111 + 100 * i for i in range(9)), 305, 385),
    (tuple(61 + 100 * i for i in range(10)), 385, 535),
)
def tableau_boxes():
    """28 boxes keyed tableau-01..tableau-28 (visible band of each card)."""
    boxes, n = {}, 1
    for centres, top, bottom in _ROWS:
        for cx in centres:
            boxes[f"tableau-{n:02d}"] = (cx - CARD_W // 2, top, cx + CARD_W // 2, bottom); n += 1
    return boxes
WASTE_BOX = (600, 585, 720, 765)
STOCK_BOX = (402, 572, 520, 750)
STOCK_COUNTER_BOX = (432, 640, 492, 690)
# Rank/suit index glyph in the top-left of a face-up card, as an offset box inside the slot.
CORNER = (2, 2, 40, 62)
