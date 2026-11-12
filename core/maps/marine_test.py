import json
import threading
import unittest
from datetime import datetime, timezone

from core.maps import marine


BOUNDS = (47.0, -123.0, 48.0, -122.0)


def report(kind="PositionReport", identifier=123456789, **fields):
    data = {"Valid": True, "Latitude": 47.5, "Longitude": -122.5,
            "Sog": 8.5, "TrueHeading": 90, **fields}
    return json.dumps({"MessageType": kind, "MetaData": {"MMSI": identifier, "ShipName": "SAMPLE VESSEL@@"},
                       "Message": {kind: data}}).encode()


class MarineTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.tracker = marine.MarineTracker(key_provider=lambda: "", clock=lambda: self.now,
            utcnow=lambda: datetime(2026, 11, 8, tzinfo=timezone.utc), start_workers=False)

    def test_unconfigured_is_honest_and_never_connects(self):
        calls = []
        tracker = marine.MarineTracker(key_provider=lambda: "", connector=lambda *a, **k: calls.append(a))
        result = tracker.snapshot(*BOUNDS)
        self.assertEqual((result["source"], result["configured"], result["ships"]), ("none", False, []))
        self.assertIn("AISSTREAM_API_KEY", result["error"])
        self.assertEqual(calls, [])
        self.assertIsNone(tracker._thread)

    def test_invalid_and_overwide_bounds_do_not_open_worker(self):
        for bounds in [(float("nan"), 0, 1, 1), (0, 170, 1, -170), (1, 1, 0, 2), (True, 0, 2, 2)]:
            with self.assertRaises(ValueError):
                self.tracker.snapshot(*bounds)
        tracker = marine.MarineTracker(key_provider=lambda: "synthetic-test-key")
        result = tracker.snapshot(0, 0, 11, 1)
        self.assertTrue(result["tooWide"])
        self.assertEqual(result["ships"], [])
        self.assertIsNone(tracker._thread)
        self.assertNotIn("synthetic-test-key", json.dumps(result))

    def test_position_report_binary_frames_are_normalized(self):
        self.assertTrue(self.tracker._ingest(report()))
        result = self.tracker.snapshot(*BOUNDS)
        ship = result["ships"][0]
        self.assertEqual(ship["id"], "123456789")
        self.assertEqual(ship["name"], "SAMPLE VESSEL")
        self.assertEqual((ship["lat"], ship["lon"], ship["speedKt"], ship["heading"]), (47.5, -122.5, 8.5, 90))
        self.assertEqual(result["source"], "saved")

    def test_class_b_metadata_coordinates_and_unavailable_values(self):
        for kind in marine.MESSAGE_TYPES[1:3]:
            packet = json.loads(report(kind, Sog=102.3, TrueHeading=511, Cog=271.5))
            del packet["Message"][kind]["Latitude"]
            del packet["Message"][kind]["Longitude"]
            packet["MetaData"].update(latitude=47.3, longitude=-122.7)
            self.assertTrue(self.tracker._ingest(json.dumps(packet)))
        ship = self.tracker.snapshot(*BOUNDS)["ships"][0]
        self.assertEqual(ship["heading"], 271.5)
        self.assertIsNone(ship["speedKt"])

    def test_invalid_positions_and_malformed_messages_never_create_fake_ships(self):
        for frame in [b"not json", b"[]", report(Latitude=91), report(Longitude=181), report(Valid=False),
                      report(Sog=float("nan"), Latitude=float("nan")), report(identifier="not-a-mmsi"),
                      b"x" * 131073]:
            self.assertFalse(self.tracker._ingest(frame))
        self.assertEqual(self.tracker.snapshot(*BOUNDS)["ships"], [])

    def test_static_metadata_merges_without_creating_or_refreshing_positions(self):
        static = {"MessageType": "ShipStaticData", "MetaData": {"MMSI": 123456789},
                  "Message": {"ShipStaticData": {"Name": "TEST BOAT", "Destination": "SAMPLE PORT"}}}
        self.tracker._ingest(json.dumps(static))
        self.assertEqual(self.tracker.snapshot(*BOUNDS)["ships"], [])
        self.tracker._ingest(report())
        ship = self.tracker.snapshot(*BOUNDS)["ships"][0]
        self.assertEqual(ship["destination"], "SAMPLE PORT")
        self.now += 301
        self.tracker._ingest(json.dumps(static))
        self.assertEqual(self.tracker.snapshot(*BOUNDS)["ships"], [])

    def test_ttl_and_viewport_filter_only_return_recent_matching_positions(self):
        self.tracker._ingest(report())
        self.tracker._ingest(report(identifier=223456789, Latitude=60))
        self.assertEqual(len(self.tracker.snapshot(*BOUNDS)["ships"]), 1)
        self.now += 301
        self.assertEqual(self.tracker.snapshot(*BOUNDS)["ships"], [])

    def test_cache_size_is_bounded(self):
        for index in range(marine.MAX_SHIPS + 10):
            self.tracker._ingest(report(identifier=100000000 + index))
            self.now += 0.01
        result = self.tracker.snapshot(*BOUNDS)
        self.assertEqual(len(result["ships"]), marine.MAX_SHIPS)
        self.assertNotIn("100000000", {s["id"] for s in result["ships"]})

    def test_fixed_endpoint_subscription_keeps_key_on_backend(self):
        class Socket:
            def send(self, data):
                self.packet = json.loads(data)
        socket = Socket()
        self.tracker._send(socket, "synthetic-secret", BOUNDS)
        self.assertEqual(socket.packet["APIKey"], "synthetic-secret")
        self.assertEqual(socket.packet["BoundingBoxes"], [[[47.0, -123.0], [48.0, -122.0]]])
        self.assertEqual(socket.packet["FilterMessageTypes"], list(marine.MESSAGE_TYPES))
        self.assertEqual(marine.STREAM_URL, "wss://stream.aisstream.io/v0/stream")
        self.assertNotIn("synthetic-secret", json.dumps(self.tracker.snapshot(*BOUNDS)))

    def test_provider_error_text_is_not_exposed(self):
        with self.assertRaisesRegex(ConnectionError, "Public AIS rejected") as raised:
            self.tracker._ingest(json.dumps({"error": "bad credential synthetic-secret"}))
        self.assertNotIn("synthetic-secret", str(raised.exception))

    def test_worker_expires_lease_and_closes_mock_socket(self):
        tracker = self.tracker
        tracker._key = "synthetic-test-key"
        tracker._desired = BOUNDS
        tracker._lease = self.now + 90
        calls = []
        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            def send(self, value): calls.append(json.loads(value))
            def recv(self, timeout):
                self.timeout = timeout
                tracker._clock = lambda: 1200.0
                raise TimeoutError
        socket = Socket()
        def connect(url, **options):
            self.assertEqual(url, marine.STREAM_URL)
            self.assertEqual(options["compression"], "deflate")
            return socket
        tracker._connector = connect
        tracker._run()
        self.assertEqual(len(calls), 1)
        self.assertEqual(socket.timeout, 2)
        self.assertTrue(socket.closed)
        self.assertFalse(tracker._connected)

    def test_stop_closes_socket_without_network(self):
        class Socket:
            closed = False
            def close(self): self.closed = True
        socket = Socket()
        self.tracker._socket = socket
        self.tracker.stop()
        self.assertTrue(socket.closed)
        self.assertTrue(self.tracker._stop.is_set())


if __name__ == "__main__":
    unittest.main()
