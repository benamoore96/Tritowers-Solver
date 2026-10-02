import hashlib
import json
import unittest

from tritowers_vision import (
    AnnotationDocument, AnnotationError, CaptureMetadata, QualityFlags,
    REQUIRED_SLOT_IDS, RightsRecord, Skin, SlotObservation, SlotState, UIState,
    blank_slot_config,
)


def slots():
    result=[]
    for index,slot_id in enumerate(REQUIRED_SLOT_IDS):
        x=(index%10)/10; y=(index//10)/4
        result.append(SlotObservation(slot_id,((x,y),(min(x+.05,1),y),(min(x+.05,1),min(y+.1,1)),(x,min(y+.1,1))),(index*2,index,20,30),SlotState.FACE_UP if index==0 else SlotState.UNKNOWN,rank="A" if index==0 else None,suit="S" if index==0 else None,confidence=.95 if index==0 else 0.0,adjudication="double-labelled" if index==0 else None))
    return tuple(result)

def document():
    return AnnotationDocument("ann-001",hashlib.sha256(b"synthetic fixture").hexdigest(),Skin.UNKNOWN,UIState.PLAY,((.1,.1),(.9,.1),(.9,.9),(.1,.9)),slots(),CaptureMetadata(session_id="session-a",machine_id="machine-a",venue_id="venue-a",variant="unknown",width=800,height=600,rights=RightsRecord(permission_basis="synthetic fixture",private_research_only=True)),QualityFlags(manual_corners_used=True),readable=True,adjudication="reviewed")

class AnnotationTests(unittest.TestCase):
    def test_complete_round_trip_is_stable(self):
        original=document(); payload=original.to_json(); restored=AnnotationDocument.from_json(payload)
        self.assertEqual(restored,original); self.assertEqual(json.loads(restored.to_json()),json.loads(payload))
    def test_round_trip_preserves_rights_quality_and_adjudication(self):
        restored=AnnotationDocument.from_dict(document().to_dict())
        self.assertEqual(restored.metadata.rights.permission_basis,"synthetic fixture")
        self.assertTrue(restored.quality.manual_corners_used); self.assertEqual(restored.slots[0].adjudication,"double-labelled")
    def test_all_28_tableau_plus_waste_stock_required(self):
        value=document().to_dict(); value["slots"]=value["slots"][:-1]
        with self.assertRaisesRegex(AnnotationError,"Missing required slots"):AnnotationDocument.from_dict(value)
    def test_duplicate_slot_rejected(self):
        value=document().to_dict(); value["slots"][-1]["slot_id"]=value["slots"][0]["slot_id"]
        with self.assertRaisesRegex(AnnotationError,"unique"):AnnotationDocument.from_dict(value)
    def test_hidden_card_inference_rejected(self):
        value=document().to_dict(); value["slots"][0]["state"]="covered"
        with self.assertRaises((AnnotationError,ValueError)):AnnotationDocument.from_dict(value)
    def test_rights_basis_required(self):
        value=document().to_dict(); value["metadata"]["rights"]["permission_basis"]=None
        with self.assertRaisesRegex(AnnotationError,"permission_basis"):AnnotationDocument.from_dict(value)
    def test_pseudonymous_session_and_machine_required(self):
        value=document().to_dict(); value["metadata"]["session_id"]=None
        with self.assertRaisesRegex(AnnotationError,"session_id"):AnnotationDocument.from_dict(value)
    def test_readable_and_rejected_conflict(self):
        value=document().to_dict(); value["rejection_reason"]="blur"
        with self.assertRaisesRegex(AnnotationError,"readable"):AnnotationDocument.from_dict(value)
    def test_invalid_manual_corners_rejected(self):
        value=document().to_dict(); value["manual_screen_corners"]=[[0,0],[.1,.1],[.2,.2],[.3,.3]]
        with self.assertRaisesRegex(AnnotationError,"degenerate"):AnnotationDocument.from_dict(value)
    def test_out_of_bounds_polygon_rejected(self):
        value=document().to_dict(); value["slots"][0]["polygon"]=([-.1,0],)+tuple(value["slots"][0]["polygon"][1:])
        with self.assertRaisesRegex(AnnotationError,"normalized"):AnnotationDocument.from_dict(value)
    def test_blank_config_has_canonical_slot_ids(self):
        config=blank_slot_config(); self.assertEqual([item["slot_id"] for item in config],list(REQUIRED_SLOT_IDS)); self.assertEqual(len(config),30)
    def test_non_object_json_rejected(self):
        with self.assertRaisesRegex(AnnotationError,"object"):AnnotationDocument.from_json("[]")

if __name__=="__main__":unittest.main()
