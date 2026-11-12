import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.maps import live


class Reply:
    def __init__(self, data=None, content=b""):
        self._data, self.content = data, content

    def json(self):
        return self._data


OSRM = {"code": "Ok", "routes": [{"distance": 12345.6, "duration": 900.4,
        "geometry": {"coordinates": [[-122.82, 47.03], [-122.8, 47.04], [-122.76, 47.06]]},
        "legs": [{"distance": 12345.6, "duration": 900.4, "steps": [
            {"name": "Pacific Avenue", "distance": 400, "duration": 60, "maneuver": {"type": "depart", "bearing_after": 90, "location": [-122.82, 47.03]}},
            {"name": "Martin Way", "distance": 9000, "duration": 700, "maneuver": {"type": "turn", "modifier": "left", "location": [-122.8, 47.04]}},
            {"name": "", "ref": "I 5", "distance": 2000, "duration": 120, "maneuver": {"type": "on ramp", "modifier": "right", "location": [-122.79, 47.05]}},
            {"name": "", "distance": 0, "duration": 0, "maneuver": {"type": "arrive", "modifier": "right", "location": [-122.76, 47.06]}}]}]}]}


class LiveTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patches = [patch.object(live, "DATA_DIR", root), patch.object(live, "PLACES_FILE", root / "places.json"),
                        patch.object(live, "LANDMARK_DIR", root / "landmarks")]
        for item in self.patches:
            item.start()
        live._cache.clear()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.folder.cleanup()

    @staticmethod
    def online(reply):
        """The local engine is off: its call fails, the online one answers."""
        def fetch(url, **kwargs):
            if url.startswith(live.LOCAL_ROUTING_URL):
                raise OSError("connection refused")
            return reply
        return fetch

    def test_route_reads_osrm_into_plain_directions(self):
        stops = [{"lat": 47.03, "lon": -122.82}, {"lat": 47.06, "lon": -122.76}]
        with patch.object(live, "_http_get", side_effect=self.online(Reply(OSRM))) as fetch:
            result = live.route(stops)
        self.assertEqual(result["engine"], "online")
        self.assertIn("/route/v1/driving/-122.820000,47.030000;-122.760000,47.060000", fetch.call_args.args[0])
        self.assertEqual((result["distance"], result["duration"]), (12346, 900))
        self.assertEqual(result["line"][0], [47.03, -122.82])
        self.assertEqual([s["text"] for s in result["legs"][0]["steps"]],
                         ["Head east on Pacific Avenue", "Turn left onto Martin Way", "Take the ramp right onto I 5", "Arrive at your stop on the right"])

    def test_best_order_uses_trip_and_returns_visit_order(self):
        trip = {"code": "Ok", "trips": OSRM["routes"], "waypoints": [{"waypoint_index": 0}, {"waypoint_index": 2}, {"waypoint_index": 1}]}
        stops = [{"lat": 47.0, "lon": -122.8}, {"lat": 47.1, "lon": -122.7}, {"lat": 47.05, "lon": -122.75}]
        with patch.object(live, "_http_get", side_effect=self.online(Reply(trip))) as fetch:
            result = live.route(stops, best_order=True)
        self.assertIn("/trip/v1/driving/", fetch.call_args.args[0])
        self.assertEqual(fetch.call_args.kwargs["params"]["roundtrip"], "false")
        self.assertEqual(result["order"], [0, 2, 1])

    def test_local_engine_is_used_first_with_legs_and_best_order(self):
        # Three stops on a line: 0 -> far(1) -> near(2) -> end is slower than 0 -> near -> far.
        stops = [{"lat": 47.0, "lon": -122.8}, {"lat": 47.3, "lon": -122.8}, {"lat": 47.1, "lon": -122.8}, {"lat": 47.4, "lon": -122.8}]
        def fetch(url, params=None, **kwargs):
            self.assertTrue(url.startswith(live.LOCAL_ROUTING_URL))
            points = [float(v.split(",")[0]) for k, v in params if k == "point"]
            seconds = sum(abs(b - a) for a, b in zip(points, points[1:])) * 1000
            instructions = [{"text": "Continue onto Pacific Ave", "distance": 100, "time": 1000, "interval": [0, 1], "sign": 0}]
            for _ in points[1:-1]:
                instructions.append({"text": "Waypoint 1", "distance": 0, "time": 0, "interval": [1, 1], "sign": 5})
            instructions.append({"text": "Arrive at destination", "distance": 0, "time": 0, "interval": [1, 1], "sign": 4})
            return Reply({"paths": [{"distance": 5000, "time": seconds * 1000, "instructions": instructions,
                                     "points": {"coordinates": [[-122.8, 47.0], [-122.8, 47.4]]}}]})
        with patch.object(live, "_http_get", side_effect=fetch):
            result = live.route(stops, best_order=True)
        self.assertEqual(result["engine"], "local")
        self.assertEqual(result["order"], [0, 2, 1, 3])
        self.assertEqual(len(result["legs"]), 3)
        self.assertEqual(result["legs"][0]["steps"][-1]["text"], "Arrive at your stop")
        self.assertEqual(result["line"], [[47.0, -122.8], [47.4, -122.8]])

    def test_route_checks_stops_and_reports_offline(self):
        with self.assertRaises(ValueError):
            live.route([{"lat": 47, "lon": -122}])
        with self.assertRaises(ValueError):
            live.route([{"lat": 147, "lon": -122}, {"lat": 47, "lon": -122}])
        with patch.object(live, "_http_get", side_effect=OSError("offline")), self.assertRaises(ConnectionError):
            live.route([{"lat": 47, "lon": -122}, {"lat": 47.1, "lon": -122}])

    def test_place_search_saves_answers_for_offline(self):
        found = [{"name": "Costco", "display_name": "Costco, Lacey, WA", "lat": "47.05", "lon": "-122.78"}]
        with patch.object(live, "_http_get", return_value=Reply(found)), patch.object(live.time, "sleep"):
            first = live.search_places("Costco", 47.03, -122.82)
        with patch.object(live, "_http_get", side_effect=OSError("offline")):
            second = live.search_places("costco", 47.03, -122.82)
        self.assertEqual(first["source"], "online")
        self.assertEqual(second["source"], "saved")
        self.assertEqual(second["places"][0]["lat"], 47.05)

    def test_place_search_cache_is_scoped_to_the_nearby_town(self):
        west = [{"name": "Library", "display_name": "West Library", "lat": "47.05", "lon": "-122.78"}]
        east = [{"name": "Library", "display_name": "East Library", "lat": "40.71", "lon": "-74.00"}]
        with patch.object(live, "_http_get", side_effect=[Reply(west), Reply(east)]) as fetch, \
             patch.object(live.time, "sleep"):
            first = live.search_places("Library", 47.03, -122.82)
            second = live.search_places("library", 40.71, -74.00)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(first["places"][0]["detail"], "West Library")
        self.assertEqual(second["places"][0]["detail"], "East Library")
        with patch.object(live, "_http_get", side_effect=AssertionError("cached search must stay local")):
            saved = live.search_places("LIBRARY", 40.71, -74.00)
        self.assertEqual(saved["source"], "saved")
        self.assertEqual(saved["places"], second["places"])

    def test_failed_geocoding_attempts_still_obey_the_rate_limit(self):
        with patch.object(live, "_nominatim_last", [0.0]), \
             patch.object(live.time, "monotonic", return_value=100.0), \
             patch.object(live.time, "sleep") as sleep, \
             patch.object(live, "_http_get", side_effect=OSError("offline")) as fetch:
            live.search_places("Library", 47, -122)
            live.search_places("Museum", 47, -122)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 1.05)

    def test_geocoder_can_be_replaced_or_disabled_without_a_code_change(self):
        with patch.object(live, "NOMINATIM_URL", "http://127.0.0.1:9090/search"), \
             patch.object(live.time, "sleep"), \
             patch.object(live, "_http_get", return_value=Reply([])) as fetch:
            result = live.search_places("Museum", 47, -122)
        self.assertEqual(result["source"], "online")
        self.assertEqual(fetch.call_args.args[0], "http://127.0.0.1:9090/search")
        for endpoint in ("", "http://example.com/search", "https://name:secret@example.com/search"):
            with self.subTest(endpoint=endpoint), patch.object(live, "NOMINATIM_URL", endpoint), \
                 patch.object(live, "_http_get") as fetch:
                result = live.search_places("Different place", 48, -123)
                self.assertEqual(result["source"], "offline")
                fetch.assert_not_called()

    def test_live_cache_evicts_old_entries_and_limits_payload_bytes(self):
        clock = {"now": 100.0}
        with patch.object(live, "CACHE_MAX_ENTRIES", 2), patch.object(live, "CACHE_MAX_BYTES", 10), \
             patch.object(live.time, "monotonic", side_effect=lambda: clock["now"]):
            live._cached("a", 10, lambda: b"aaaa")
            live._cached("b", 10, lambda: b"bbbb")
            live._cached("c", 10, lambda: b"cccc")
            self.assertNotIn("a", live._cache)
            self.assertEqual(live._cached("b", 10, lambda: self.fail("fresh cache was not reused")), b"bbbb")
            live._cached("d", 10, lambda: b"dddd")
            self.assertEqual(set(live._cache), {"b", "d"})
            live._cached("oversized", 10, lambda: b"x" * 11)
            self.assertNotIn("oversized", live._cache)
            clock["now"] = 111
            live._cached("new", 10, lambda: b"new")
            self.assertEqual(set(live._cache), {"new"})

    def test_local_extract_without_a_route_uses_the_existing_online_fallback(self):
        def fetch(url, **kwargs):
            if url.startswith(live.LOCAL_ROUTING_URL):
                return Reply({"paths": [], "message": "Point is outside the local extract"})
            return Reply(OSRM)
        with patch.object(live, "_http_get", side_effect=fetch):
            result = live.route([{"lat": 47, "lon": -122}, {"lat": 40, "lon": -74}])
        self.assertEqual(result["engine"], "online")

    def test_stop_optimization_budget_returns_an_honest_ordered_route(self):
        clock = {"now": 100.0}
        calls = []
        stops = [{"lat": 47 + i / 10, "lon": -122} for i in range(4)]
        def path(points, **kwargs):
            calls.append(list(points))
            clock["now"] += 4.1
            return {"time": 1000, "distance": 100,
                    "points": {"coordinates": [[p["lon"], p["lat"]] for p in points]}, "instructions": []}
        with patch.object(live.time, "monotonic", side_effect=lambda: clock["now"]), \
             patch.object(live, "_gh_path", side_effect=path):
            result = live.route(stops, best_order=True)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], stops)
        self.assertEqual(result["order"], [0, 1, 2, 3])
        self.assertFalse(result["optimized"])
        self.assertIn("entered stop order", result["optimizationNote"])

    def test_expired_route_budget_does_not_start_another_online_request(self):
        clock = {"now": 100.0}
        def failed_local(*args, **kwargs):
            clock["now"] = 140.0
            raise OSError("timed out")
        with patch.object(live.time, "monotonic", side_effect=lambda: clock["now"]), \
             patch.object(live, "_gh_path", side_effect=failed_local), \
             patch.object(live, "_http_get") as online:
            with self.assertRaises(ConnectionError):
                live.route([{"lat": 47, "lon": -122}, {"lat": 48, "lon": -123}])
        online.assert_not_called()

    def test_engine_provenance_uses_the_hostname_not_a_url_substring(self):
        for endpoint in ("http://127.0.0.1:8989", "http://localhost:5000", "http://[::1]:5000"):
            self.assertTrue(live._routing_is_local(endpoint))
        for endpoint in ("https://localhost.example.com", "https://example.com/127.0.0.1", "https://example.com?q=localhost"):
            self.assertFalse(live._routing_is_local(endpoint))

    def test_aircraft_parses_opensky_and_limits_area(self):
        state = ["a1b2c3", "ASA123  ", "United States", 0, 0, -122.3, 47.45, 3000.0, False, 120.0, 180.0, 5.0, None, 3050.0, "1200", False, 0]
        with patch.object(live, "_http_get", return_value=Reply({"states": [state, ["bad"]]})):
            result = live.aircraft(47.0, -123.0, 47.6, -122.0)
        plane = result["planes"][0]
        self.assertEqual((plane["callsign"], plane["altitudeFt"], plane["speedKt"], plane["heading"]), ("ASA123", 10007, 233, 180))
        self.assertTrue(live.aircraft(40, -130, 50, -110)["tooWide"])

    def test_weather_alerts_fall_back_to_saved(self):
        feature = {"properties": {"id": "x", "event": "Wind Advisory", "severity": "Moderate", "headline": "Wind Advisory until 6 PM"},
                   "geometry": {"type": "Polygon", "coordinates": [[[-122.9, 47.0], [-122.7, 47.0], [-122.7, 47.1]]]}}
        with patch.object(live, "_http_get", return_value=Reply({"features": [feature]})):
            first = live.weather_alerts(47.03, -122.82)
        live._cache.clear()
        with patch.object(live, "_http_get", side_effect=OSError("offline")):
            second = live.weather_alerts(47.03, -122.82)
        self.assertEqual(first["alerts"][0]["polygon"][0], [47.0, -122.9])
        self.assertEqual(second["source"], "saved")
        self.assertEqual(second["alerts"], first["alerts"])

    def test_radar_tile_rejects_bad_paths(self):
        for path in ("/etc/passwd", "/v2/radar/../../x", "/v2/radar/1?x=1"):
            with self.assertRaises(ValueError):
                live.radar_tile(path, 5, 1, 1)
        with self.assertRaises(ValueError):
            live.radar_tile("/v2/radar/1700000000", 9, 1, 1)

    def test_radar_manifest_cannot_choose_an_internal_or_other_tile_host(self):
        manifest = {"host": "http://127.0.0.1:8766", "radar": {"past": [{"time": 1700000000, "path": "/v2/radar/1700000000"}]}}
        with patch.object(live, "_http_get", return_value=Reply(manifest)):
            self.assertEqual(live.radar_frames()["host"], live.RADAR_TILE_HOST)
        live._cache.clear()
        with patch.object(live, "radar_frames", return_value={"host": "http://169.254.169.254"}), \
             patch.object(live, "_http_get", return_value=Reply(content=b"\x89PNG\r\n\x1a\n")) as fetch:
            live.radar_tile("/v2/radar/1700000000", 5, 1, 1)
        self.assertTrue(fetch.call_args.args[0].startswith("https://tilecache.rainviewer.com/v2/radar/"))


if __name__ == "__main__":
    unittest.main()


class SuggestionsTest(unittest.TestCase):
    def setUp(self):
        live._cache.clear()
        live._photon_last[0] = 0

    def test_suggestions_use_photon_deduplicate_and_cache_without_disk_or_nominatim(self):
        feature = {"geometry": {"coordinates": [-122.3, 47.6]}, "properties": {"name": "Sample Cafe", "city": "Seattle"}}
        invalid = {"geometry": {"coordinates": [999, 47]}, "properties": {}}
        with patch.object(live, "_http_get", return_value=Reply({"features": [feature, feature, invalid]})) as fetch, patch.object(live, "_write_atomic") as write:
            result = live.suggest_places("Sample", 47.606, -122.332)
            self.assertEqual(len(result["places"]), 1)
            self.assertEqual(result["source"], "photon")
            self.assertEqual(live.suggest_places("Sample", 47.606, -122.332), result)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(fetch.call_args.args[0], live.PHOTON_URL)
            self.assertEqual(fetch.call_args.kwargs["params"]["lat"], 47.61)
            write.assert_not_called()

    def test_short_queries_no_requests_and_provider_failure_is_explicit(self):
        with patch.object(live, "_http_get", side_effect=OSError("offline")) as fetch:
            self.assertEqual(live.suggest_places("ab", 47, -122)["source"], "none")
            fetch.assert_not_called()
            self.assertEqual(live.suggest_places("Sample", 47, -122)["source"], "offline")

    def test_inflight_and_rapid_requests_do_not_queue_or_hit_provider(self):
        with patch.object(live, "_http_get") as fetch:
            live._photon_lock.acquire()
            try:
                self.assertEqual(live.suggest_places("Sample", 47, -122)["source"], "busy")
            finally:
                live._photon_lock.release()
            live._photon_last[0] = live.time.monotonic()
            self.assertEqual(live.suggest_places("Other", 47, -122)["source"], "busy")
            fetch.assert_not_called()

    def test_expired_cache_and_unencrypted_remote_endpoint_rejected(self):
        key = "photon:47.00,-122.00:sample"
        live._cache[key] = (live.time.monotonic() - 1, {"places": ["expired"]}, 0)
        with patch.object(live, "PHOTON_URL", "http://example.com/api"), patch.object(live, "_http_get") as fetch:
            self.assertEqual(live.suggest_places("Sample", 47, -122)["source"], "offline")
            fetch.assert_not_called()


class AlternativesTest(unittest.TestCase):
    def test_online_alternatives_share_one_request_and_keep_directions(self):
        import copy
        data = copy.deepcopy(OSRM)
        option = copy.deepcopy(data["routes"][0]); option["duration"] = 1000
        data["routes"].append(option)
        stops = [{"lat": 47.03, "lon": -122.82}, {"lat": 47.06, "lon": -122.76}]
        with patch.object(live, "_http_get", side_effect=LiveTest.online(Reply(data))) as fetch:
            result = live.route(stops, alternatives=True)
        self.assertEqual(result["alternatives"][0]["duration"], 1000)
        self.assertEqual(result["alternatives"][0]["order"], [0, 1])
        self.assertEqual(fetch.call_args.kwargs["params"]["alternatives"], "true")

    def test_local_alternative_conversion_does_not_lose_stop_order(self):
        path = {"distance": 500, "time": 60000, "points": {"coordinates": [[-122, 47], [-122.01, 47.01]]}, "instructions": [{"sign": 4, "interval": [1, 1], "distance": 500, "time": 60000}]}
        with patch.object(live, "_gh_path", return_value={**path, "_alternatives": [path]}):
            reply = live._local_route([{"lat": 47, "lon": -122}, {"lat": 47.01, "lon": -122.01}], alternatives=True)
        self.assertEqual(reply["alternatives"][0]["engine"], "local")
        self.assertEqual(reply["alternatives"][0]["order"], [0, 1])


class AircraftObservationTests(unittest.TestCase):
    def setUp(self):
        live._cache.clear()

    def test_provider_observation_times_are_preserved_and_cache_does_not_refresh_them(self):
        now=int(live.time.time())
        state=["a1", "SAMPLE", "US", now-8, now-2, -122.3, 47.5, 1000, False, 100, 90, 0, None, 1000, "1200", False, 0]
        with patch.object(live, "_http_get", return_value=Reply({"time":now-1,"states":[state]})) as fetch:
            first=live.aircraft(47,-123,48,-122)
            second=live.aircraft(47,-123,48,-122)
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(first,second)
        self.assertEqual(first["planes"][0]["positionAt"],live.datetime.fromtimestamp(now-8,live.timezone.utc).isoformat())
        self.assertEqual(first["updatedAt"],live.datetime.fromtimestamp(now-1,live.timezone.utc).isoformat())
        self.assertNotEqual(first["updatedAt"],first["fetchedAt"])

    def test_missing_position_time_and_bad_values_never_become_fresh_positions(self):
        now=int(live.time.time())
        good=["a", "SAMPLE", "US", None, now, -122.3, 47.5, 1000, False, float('nan'), float('inf'), 0, None, 1000, None, False, 0]
        invalid=list(good);invalid[6]=float('nan')
        with patch.object(live,"_http_get",return_value=Reply({"time":now,"states":[good,invalid,{"bad":True}]})):
            reply=live.aircraft(47,-123,48,-122)
        self.assertEqual(len(reply["planes"]),1)
        self.assertIsNone(reply["planes"][0]["positionAt"])
        self.assertIsNone(reply["planes"][0]["speedKt"])
        self.assertIsNone(reply["planes"][0]["heading"])
