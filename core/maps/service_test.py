import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core.maps import service

PNG = b"\x89PNG\r\n\x1a\nfake"


class Reply:
    def __init__(self, content=b"", data=None):
        self.content, self._data = content, data

    def json(self):
        return self._data


class MapServiceTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patches = [patch.object(service, "TILE_DIR", root / "tiles"), patch.object(service, "LANDMARK_DIR", root / "landmarks"),
                        patch.object(service, "TRAFFIC_FILE", root / "traffic_last.json"), patch.object(service, "HOME_FILE", root / "home.json")]
        for item in self.patches:
            item.start()
        service._traffic_cache.update(at=0.0, data=None)

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.folder.cleanup()

    # tiles
    def test_tile_is_fetched_once_then_served_from_disk(self):
        with patch.object(service, "_http_get", return_value=Reply(PNG)) as fetch:
            self.assertEqual(service.tile(12, 650, 1440), (PNG, "online"))
            self.assertEqual(service.tile(12, 650, 1440), (PNG, "saved"))
            self.assertEqual(service.tile(12, 650, 1440, style="dark"), (PNG, "saved"))
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args[0], "https://tile.openstreetmap.org/12/650/1440.png")

    def test_offline_uses_old_tile_and_reports_missing_one(self):
        path = service.TILE_DIR / service.TILE_CACHE_VERSION / "standard" / "12" / "650" / "1440.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(PNG)
        old = time.time() - service.TILE_REFRESH_SECONDS - 10
        os.utime(path, (old, old))
        with patch.object(service, "_http_get", side_effect=OSError("offline")):
            self.assertEqual(service.tile(12, 650, 1440), (PNG, "saved-old"))
            with self.assertRaises(service.MapUnavailable):
                service.tile(12, 651, 1440)

    def test_tile_rejects_out_of_range_and_non_png(self):
        with self.assertRaises(ValueError):
            service.tile(12, 4096, 0)
        with self.assertRaises(ValueError):
            service.tile(19, 0, 0)
        with self.assertRaises(ValueError):
            service.tile(5, 1, 1, style="../secret")
        with patch.object(service, "_http_get", return_value=Reply(b"<html>blocked</html>")):
            with self.assertRaises(service.MapUnavailable):
                service.tile(5, 1, 1)

    def test_old_provider_warning_tiles_are_not_reused(self):
        legacy = service.TILE_DIR / "clear" / "12" / "650" / "1440.png"
        legacy.parent.mkdir(parents=True)
        warning = PNG + b"API KEY REQUIRED"
        legacy.write_bytes(warning)
        with patch.object(service, "_http_get", side_effect=OSError("offline")):
            with self.assertRaises(service.MapUnavailable):
                service.tile(12, 650, 1440)
        with patch.object(service, "_http_get", return_value=Reply(PNG)):
            self.assertEqual(service.tile(12, 650, 1440), (PNG, "online"))
        self.assertEqual(legacy.read_bytes(), warning)  # preserve old files, but never serve them

    def test_satellite_uses_labelled_usgs_imagery_without_carto(self):
        with patch.object(service, "_http_get", return_value=Reply(PNG)) as fetch:
            service.tile(12, 650, 1440, style="satellite")
        self.assertIn("USGSImageryTopo/MapServer/tile/12/1440/650", fetch.call_args.args[0])
        self.assertTrue(all("carto" not in url for url in service.TILE_STYLES.values()))

    # landmarks
    def test_landmarks_parse_named_places_and_cache_per_cell(self):
        data = {"elements": [
            {"type": "node", "id": 1, "lat": 47.04, "lon": -122.82, "tags": {"name": "Capitol Lake", "leisure": "park"}},
            {"type": "way", "id": 2, "center": {"lat": 47.035, "lon": -122.9}, "tags": {"name": "Olympia Airport", "aeroway": "aerodrome"}},
            {"type": "node", "id": 3, "lat": 47.03, "lon": -122.8, "tags": {"tourism": "viewpoint"}},
        ]}
        with patch.object(service, "_http_post", return_value=Reply(data=data)) as fetch:
            first = service.landmarks(47.02, -122.85, 47.05, -122.80)
            second = service.landmarks(47.02, -122.85, 47.05, -122.80)
        self.assertEqual([item["name"] for item in first["landmarks"]], ["Capitol Lake"])
        self.assertEqual(first["landmarks"][0]["kind"], "park")
        self.assertEqual(second, first)
        self.assertEqual(fetch.call_count, len(service.landmark_cells(47.02, -122.85, 47.05, -122.80)))
        self.assertEqual(service.parse_overpass(data)[1]["kind"], "airport")

    def test_landmarks_wide_view_and_offline(self):
        self.assertTrue(service.landmarks(46.0, -124.0, 48.0, -121.0)["tooWide"])
        cells = service.landmark_cells(47.0, -122.95, 47.12, -122.7)
        self.assertGreater(len(cells), service.LANDMARK_FETCHES_PER_CALL)
        with patch.object(service, "_http_post", return_value=Reply(data={"elements": []})) as fetch:
            partial = service.landmarks(47.0, -122.95, 47.12, -122.7)
        self.assertEqual(fetch.call_count, service.LANDMARK_FETCHES_PER_CALL)
        self.assertEqual(partial["pending"], len(cells) - service.LANDMARK_FETCHES_PER_CALL)
        with patch.object(service, "_http_post", side_effect=OSError("offline")):
            result = service.landmarks(47.02, -122.85, 47.05, -122.80)
        self.assertEqual(result["landmarks"], [])
        self.assertEqual(result["pending"], 0)
        self.assertGreater(result["missing"], 0)
        with self.assertRaises(ValueError):
            service.landmarks(48, -122, 47, -121)

    def test_world_landmark_view_is_rejected_before_cell_allocation(self):
        with patch.object(service, "landmark_cells", side_effect=AssertionError("must not allocate")), \
             patch.object(service, "_fetch_cell") as fetch:
            result = service.landmarks(-90, -180, 90, 180)
        self.assertTrue(result["tooWide"])
        fetch.assert_not_called()
        with self.assertRaises(ValueError):
            service.landmark_cells(-90, -180, 90, 180)

    def test_world_edges_do_not_create_nonexistent_tile_indexes(self):
        self.assertEqual(service._lon_to_tile(180, 12), 4095)
        self.assertEqual(service._lon_to_tile(-180, 12), 0)
        self.assertEqual(service._lat_to_tile(-90, 12), 4095)
        self.assertEqual(service._lat_to_tile(90, 12), 0)

    # traffic
    FLOWS = [{"FlowDataID": 7, "FlowReadingValue": 4, "Time": "/Date(1794200000000-0800)/",
              "FlowStationLocation": {"Latitude": 47.05, "Longitude": -122.76, "RoadName": "005", "Direction": "NB", "Description": "Marvin Rd"}},
             {"FlowDataID": 8, "FlowReadingValue": 5, "FlowStationLocation": {"Latitude": 47.0, "Longitude": -122.7}},
             {"FlowDataID": 9, "FlowReadingValue": 1, "FlowStationLocation": {"Latitude": 0, "Longitude": 0}}]
    ALERTS = [{"AlertID": 42, "HeadlineDescription": "Collision blocking right lane", "EventCategory": "Collision", "Priority": "High",
               "StartRoadwayLocation": {"Latitude": 47.06, "Longitude": -122.7, "RoadName": "005"},
               "EndRoadwayLocation": {"Latitude": 0, "Longitude": 0}, "StartTime": "/Date(1794200000000-0800)/"}]

    def test_traffic_live_then_saved_when_offline(self):
        replies = iter([Reply(data=self.FLOWS), Reply(data=self.ALERTS)])
        with patch.dict(os.environ, {"WSDOT_API_KEY": "k"}), patch.object(service, "_http_get", side_effect=lambda *a, **k: next(replies)):
            live = service.traffic()
        self.assertEqual(live["source"], "live")
        self.assertEqual([(f["id"], f["label"]) for f in live["flows"]], [("7", "stop-and-go")])
        self.assertEqual(live["alerts"][0]["headline"], "Collision blocking right lane")
        self.assertIsNone(live["alerts"][0]["endLat"])
        self.assertTrue(live["alerts"][0]["start"].startswith("2026-11-"))
        service._traffic_cache.update(at=0.0, data=None)
        with patch.dict(os.environ, {"WSDOT_API_KEY": "k"}), patch.object(service, "_http_get", side_effect=OSError("offline")):
            saved = service.traffic()
        self.assertEqual(saved["source"], "saved")
        self.assertEqual(saved["flows"], live["flows"])
        self.assertIn("can't be reached", saved["error"])

    def test_traffic_without_key_says_so(self):
        with patch.dict(os.environ, {"WSDOT_API_KEY": ""}):
            result = service.traffic()
        self.assertEqual(result["source"], "none")
        self.assertIn("WSDOT_API_KEY", result["error"])

    def test_satellite_is_jpeg_and_capped_at_its_zoom(self):
        jpeg = b"\xff\xd8\xff\xe0fake"
        with patch.object(service, "_http_get", return_value=Reply(jpeg)) as fetch:
            body, _ = service.tile(12, 650, 1440, style="satellite")
        self.assertEqual(service.tile_mime(body), "image/jpeg")
        self.assertIn("USGSImageryTopo/MapServer/tile/12/1440/650", fetch.call_args.args[0])
        with self.assertRaises(ValueError):
            service.tile(17, 0, 0, style="satellite")

    def test_segments_join_neighbouring_sensors_along_the_road(self):
        def flow(i, mp, lat, direction="NB", road="005"):
            return {"id": str(i), "lat": lat, "lon": -122.8, "level": 1, "road": road, "direction": direction, "milepost": mp}
        flows = [flow(1, 110.0, 47.00), flow(2, 111.0, 47.015), flow(3, 140.0, 47.4),
                 flow(4, 111.0, 47.015, "SB"), flow(5, 110.0, 47.0, "SB")]
        pairs = [(a["id"], b["id"]) for a, b in service.segment_pairs(flows)]
        self.assertEqual(sorted(pairs), [("1", "2"), ("4", "5")])   # 2->3 is too far apart; southbound runs down the mileposts
        service._segment_state.update(running=False, data=None)
        path = {"distance": 1800, "points": {"coordinates": [[-122.8, 47.0], [-122.801, 47.007], [-122.8, 47.015]]}}
        with patch.object(service, "SEGMENTS_FILE", Path(self.folder.name) / "segments.json"), \
             patch("core.maps.live._gh_path", return_value=path):
            service._build_segments(service.segment_pairs(flows))
            service._segment_state["data"] = None
            with patch.object(service, "traffic", return_value={"flows": flows}):
                result = service.traffic_segments()
        self.assertEqual(result["pending"], 0)
        self.assertEqual({s["id"] for s in result["segments"]}, {"1>2", "4>5"})
        self.assertEqual(len(result["segments"][0]["line"]), 3)

    def test_home_prefers_saved_home_and_counts_cache(self):
        service.HOME_FILE.parent.mkdir(parents=True, exist_ok=True)
        service.HOME_FILE.write_text(json.dumps({"lat": 47.1, "lon": -122.9, "place": "Home"}), encoding="utf-8")
        result = service.home()
        self.assertEqual((result["lat"], result["lon"], result["place"]), (47.1, -122.9, "Home"))
        self.assertEqual(result["saved"]["tiles"], 0)


if __name__ == "__main__":
    unittest.main()
