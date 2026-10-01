import numpy as np
from PIL import Image
from tritowers_vision.layout import tableau_boxes
from tritowers_vision.occupancy import classify_patch
from tritowers_vision.rank import match
from tritowers_vision.schema import SlotState
def test_layout_has_28_slots():
    b=tableau_boxes(); assert len(b)==28 and b["tableau-28"][0]>800
def test_patch_states():
    assert classify_patch(Image.new("RGB",(40,40),(235,225,200)))[0] is SlotState.FACE_UP
    assert classify_patch(Image.new("RGB",(40,40),(170,40,60)))[0] is SlotState.COVERED
def test_match_abstains_without_templates():
    assert match(np.ones((32,24),np.float32),[])[0] is None
