import unittest

from SED_1_Multi_Camera.scripts.geofence import detection_in_geofence, filter_detections_for_camera
from SED_1_Multi_Camera.scripts.models import CameraConfig, GeofenceConfig


class GeofenceTests(unittest.TestCase):
    def test_polygon_filter_accepts_center_inside(self):
        geofence = GeofenceConfig(
            id="zone",
            polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
            classes={"fire"},
        )
        det = {"class_name": "fire", "confidence": 0.8, "coordinates": {"x1": 40, "y1": 40, "x2": 60, "y2": 60}}
        self.assertTrue(detection_in_geofence(det, geofence, frame={"width": 100, "height": 100}))

    def test_polygon_filter_rejects_center_outside(self):
        geofence = GeofenceConfig(
            id="zone",
            polygon=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)],
            classes={"fire"},
        )
        det = {"class_name": "fire", "confidence": 0.8, "coordinates": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}}
        self.assertFalse(detection_in_geofence(det, geofence, frame={"width": 100, "height": 100}))

    def test_camera_geofence_isolation(self):
        cam1 = CameraConfig(
            camera_id="camera_01",
            name="A",
            source="synthetic",
            monitored_classes={"fire"},
            geofences=[
                GeofenceConfig(
                    id="left",
                    polygon=[(0.0, 0.0), (0.4, 0.0), (0.4, 1.0), (0.0, 1.0)],
                    classes={"fire"},
                )
            ],
        )
        cam2 = CameraConfig(
            camera_id="camera_02",
            name="B",
            source="synthetic",
            monitored_classes={"fire"},
            geofences=[
                GeofenceConfig(
                    id="right",
                    polygon=[(0.6, 0.0), (1.0, 0.0), (1.0, 1.0), (0.6, 1.0)],
                    classes={"fire"},
                )
            ],
        )
        det = {"class_name": "fire", "confidence": 0.8, "coordinates": {"x1": 10, "y1": 40, "x2": 20, "y2": 60}}
        accepted1, _ = filter_detections_for_camera([det], cam1, frame={"width": 100, "height": 100})
        accepted2, _ = filter_detections_for_camera([det], cam2, frame={"width": 100, "height": 100})
        self.assertEqual(len(accepted1), 1)
        self.assertEqual(len(accepted2), 0)


if __name__ == "__main__":
    unittest.main()


