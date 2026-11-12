# Handoff 2026-11-09: LIFE > Map & traffic (Claude)

Status: source written and checked (tsc clean, core/maps/service_test.py 8/8). Not yet built or installed.

What it is: a "Map & traffic" sub-tab in LIFE showing an OpenStreetMap map (tinted dark), live WSDOT traffic
(flow sensors coloured clear/moderate/heavy/stop-and-go, highway alerts with markers and a "Traffic near home" list)
and named landmarks. No new dependency: a small slippy map in plain React.

Local first: the Core server proxies and saves everything under data/maps/ (tiles/, landmarks/, traffic_last.json).
Viewed tiles are reused for 30 days and served offline after that; landmarks are fetched from Overpass once per z12 cell
(about 10 km) and kept 90 days; the last good traffic reading is shown offline with its age. Nothing is bulk-downloaded
(OpenStreetMap tile policy). Live traffic needs the internet and WSDOT_API_KEY (already used by the drive brief).
No Google service. Optional data/maps/home.json {"lat","lon","zoom","place"} sets where the map opens.

Files: core/maps/service.py (+ _test), core/api/map_routes.py (GET /api/map/home, /tile/{z}/{x}/{y} as base64 JSON
for the Tauri bridge, /landmarks, /traffic; all status.read in ui_routes.OPERATION_PATTERNS), server.py registers the
router, desktop/src/components/map/MapPanel.tsx/.css, App.tsx adds the LIFE tab. Backups of the three edited files:
.tmp/claude-map-backup-20261109/.

Remaining: build desktop + dist-web, restart Core so the new routes load, install, live-verify tiles/traffic.
Ideas: voice "open the map", route ETA with a local OSRM/Valhalla, offline area packs from a legal extract (Geofabrik + local renderer).

## Update (same day): directions, weather, air, local routing
- core/maps/live.py (+ _test, 16 tests total with service_test): POST /api/map/route (2-12 stops, "bestOrder"), GET /api/map/search,
  /weather/alerts (NWS), /radar + /radar/tile (RainViewer, max z7, stretched past it), /aircraft (OpenSky anonymous, 20 s cache).
  All status.read in ui_routes.OPERATION_PATTERNS.
- Routing: local GraphHopper 11.1 first (127.0.0.1:8989, Washington OSM extract, data/maps/routing, ~2.6 GB RAM while running,
  start with scripts/start_routing.ps1, no autostart). Quickest order is solved locally (pairwise times, exact up to 8 middle stops).
  If the local engine is down, OSRM public demo answers and the UI says "Worked out online".
- Map tiles: "light" = OpenStreetMap standard, "dark" = CARTO Dark Matter @2x. Style toggle in the header; final default waits on
  Grey's two reference pictures.
- Ships (AIS) not built: needs a free aisstream.io key and a websocket client.
