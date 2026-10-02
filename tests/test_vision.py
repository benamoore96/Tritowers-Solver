import io,json,unittest
import cv2,numpy as np
from PIL import Image
from tritowers_vision import CaptureMetadata,ImageInputError,RightsRecord,Skin,SlotObservation,SlotState,UIState,UnsupportedReason,extract_screen,normalize_image,order_corners,recognize
def png_bytes(image):
    output=io.BytesIO(); image.save(output,format="PNG",pnginfo=None); return output.getvalue()
class VisionTests(unittest.TestCase):
    def test_normalization_strips_metadata(self):
        image=Image.new("RGB",(320,240),"navy"); image.info["comment"]="private"; normalized=normalize_image(png_bytes(image)); self.assertEqual(normalized.info,{})
    def test_invalid_bytes(self):
        with self.assertRaises(ImageInputError):normalize_image(b"bad")
    def test_corner_order(self):np.testing.assert_array_equal(order_corners([(90,90),(10,10),(10,90),(90,10)]),[[10,10],[90,10],[90,90],[10,90]])
    def test_degenerate_quad(self):
        with self.assertRaises(ImageInputError):extract_screen(png_bytes(Image.new("RGB",(400,300))),[(1,1),(2,1),(3,1),(4,1)])
    def test_manual_rectification(self):
        result=extract_screen(png_bytes(Image.new("RGB",(400,300))),[(20,20),(380,20),(380,280),(20,280)]); self.assertTrue(result.manual); self.assertEqual(result.rectified.size,(1024,768))
    def test_generated_quad(self):
        array=np.zeros((600,800,3),dtype=np.uint8); points=np.array([[100,80],[720,120],[680,520],[140,500]],dtype=np.int32); cv2.fillConvexPoly(array,points,(230,230,230)); cv2.polylines(array,[points],True,(255,255,255),8); result=extract_screen(png_bytes(Image.fromarray(array))); self.assertIsNotNone(result.corners)
    def test_no_screen_unknown(self):
        result=recognize(None); self.assertEqual(result.skin,Skin.UNKNOWN); self.assertEqual(result.unsupported_reason,UnsupportedReason.SCREEN_NOT_RECTIFIED)
    def test_never_invents(self):
        result=recognize(Image.new("RGB",(1024,768),"gray")); self.assertEqual(result.slots,()); self.assertEqual(result.confidence,0.0)
    def test_geometry_separate(self):
        meta=CaptureMetadata(session_id="s1",rights=RightsRecord(permission_basis="permission")); result=recognize(Image.new("RGB",(1024,768),"white"),manual=True,metadata=meta); self.assertTrue(result.geometry.success); self.assertEqual(result.ui_state,UIState.UNKNOWN); json.dumps(result.to_dict())
    def test_hidden_slot_no_rank(self):
        with self.assertRaises(ValueError):SlotObservation("t1",((0,0),(1,0),(1,1),(0,1)),(0,0,1,1),SlotState.COVERED,rank="A")
if __name__=="__main__":unittest.main()
