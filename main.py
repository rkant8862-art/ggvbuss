"""
City Connect — Live Bus Tracker
================================
EK HI PYTHON FILE — frontend (HTML/CSS/JS) + backend (Flask API)
"""

from flask import Flask, request, jsonify, Response
from datetime import datetime, timezone
import threading
import socket

app = Flask(__name__)

GGU_LAT = 22.1293
GGU_LNG = 82.1360
DEFAULT_BUS_ID = "BUS_01"

# Fixed Campus Road array
GGU_CAMPUS_ROAD = [
    {"lat": 22.1382, "lng": 82.1427, "label": "Boys Hostel"},
    {"lat": 22.1334, "lng": 82.1428, "label": "ECE, CIVIL, MECHANICAL Department"},
    {"lat": 22.1311, "lng": 82.1429, "label": ""},
    {"lat": 22.1311, "lng": 82.1418, "label": "IT Department"},
    {"lat": 22.1311, "lng": 82.1400, "label": "Library"},
    {"lat": 22.1310, "lng": 82.1381, "label": ""},
    {"lat": 22.1288, "lng": 82.1381, "label": "Auditorium"},
    {"lat": 22.1261, "lng": 82.1381, "label": "Girls Hostel"},
    {"lat": 22.1262, "lng": 82.1370, "label": ""},
    {"lat": 22.1250, "lng": 82.1346, "label": "GGV Main Gate"},
]

buses_lock = threading.Lock()
buses = {}

MAX_STALE_SECONDS = 60
ARRIVAL_RADIUS_KM = 0.015

config_lock = threading.Lock()
bus_config = {}

DEFAULT_CONFIG = {
    "driver_name": "Alok Raj",
    "bus_number": "CG10TF8862",
    "bus_type": "Standard",
    "College_name": "Guru Ghasidas Vishwavidyalaya (Koni)",
    "origin": "City Bus Stand, Bilaspur",
    "destination": "Guru Ghasidas Vishwavidyalaya, Koni",
    "capacity": 45,
    "fallback_lat": GGU_LAT,
    "fallback_lng": GGU_LNG,
    "stops": [
        {"name": "GGV Main Gate", "time": "", "status": "done",
         "lat": 22.0797, "lng": 82.1409},
        {"name": "Library", "time": "", "status": "done",
         "lat": 22.0930, "lng": 82.1420},
        {"name": "ECE, CIVIL, MECHANICAL Department", "time": "", "status": "done",
         "lat": 22.1050, "lng": 82.1390},
        {"name": "Boys Hostel",
         "time": "", "status": "done", "lat": GGU_LAT, "lng": GGU_LNG},
    ],
}


def get_config(bus_id):
    with config_lock:
        return bus_config.get(bus_id, DEFAULT_CONFIG).copy()


def _is_online(entry):
    if not entry or not entry.get("updated_at"):
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(entry["updated_at"])).total_seconds()
    return age <= MAX_STALE_SECONDS


def _build_entry(bus_id):
    with buses_lock:
        live = buses.get(bus_id)
    cfg = get_config(bus_id)
    online = _is_online(live)

    if live:
        merged = dict(live)
    else:
        merged = {
            "bus_id": bus_id,
            "lat": cfg.get("fallback_lat", GGU_LAT),
            "lng": cfg.get("fallback_lng", GGU_LNG),
            "speed": 0,
            "sats": 0,
            "updated_at": None,
        }

    merged["online"] = online
    merged["config"] = cfg
    return merged


def _all_known_bus_ids():
    with buses_lock:
        live_ids = set(buses.keys())
    with config_lock:
        cfg_ids = set(bus_config.keys())
    ids = live_ids | cfg_ids
    if not ids:
        ids = {DEFAULT_BUS_ID}
    return sorted(ids)


@app.route("/update", methods=["POST"])
def update_location():
    # Force json parsing even if ESP32 doesn't send correct headers
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "invalid or missing JSON body"}), 400

    bus_id = data.get("bus_id")
    lat = data.get("lat")
    lng = data.get("lng")

    if not bus_id or lat is None or lng is None:
        return jsonify({"error": "bus_id, lat and lng are required"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat/lng must be numeric"}), 400

    entry = {
        "bus_id": str(bus_id),
        "lat": lat,
        "lng": lng,
        "speed": float(data.get("speed", 0) or 0),
        "sats": int(data.get("sats", 0) or 0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if "passengers" in data:
        try:
            entry["passengers"] = int(data["passengers"])
        except (TypeError, ValueError):
            pass
    if "fuel" in data:
        try:
            entry["fuel"] = float(data["fuel"])
        except (TypeError, ValueError):
            pass
    if "alerts" in data and isinstance(data["alerts"], list):
        entry["alerts"] = data["alerts"]

    with buses_lock:
        buses[bus_id] = entry

    print(f"[POST RECEIVE SUCCESS] {bus_id}: Lat={lat:.6f}, Lng={lng:.6f} | Speed={entry['speed']} km/h | Sats={entry['sats']}")
    return jsonify({"status": "ok", "received": entry}), 200


@app.route("/location", methods=["GET"])
def get_all_locations():
    return jsonify([_build_entry(bid) for bid in _all_known_bus_ids()])


@app.route("/location/<bus_id>", methods=["GET"])
def get_bus_location(bus_id):
    return jsonify(_build_entry(bus_id))


@app.route("/campus-road", methods=["GET"])
def get_campus_road():
    return jsonify({
        "label": "Guru Ghasidas Vishwavidyalaya (GGU), Koni, Bilaspur",
        "center": {"lat": GGU_LAT, "lng": GGU_LNG},
        "road": GGU_CAMPUS_ROAD,
    })


@app.route("/config/<bus_id>", methods=["GET"])
def get_bus_config(bus_id):
    return jsonify(get_config(bus_id))


@app.route("/config/<bus_id>", methods=["POST"])
def set_bus_config(bus_id):
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "invalid or missing JSON body"}), 400

    with config_lock:
        current = bus_config.get(bus_id, DEFAULT_CONFIG).copy()
        current.update(data)
        bus_config[bus_id] = current

    return jsonify({"status": "ok", "config": bus_config[bus_id]}), 200


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>City Connect — Live Bus Tracker</title>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>

<style>
  :root {
    --bg: #0a0f1e;
    --panel: #10182c;
    --panel-2: #141d33;
    --border: #202b45;
    --accent: #2f6feb;
    --accent-2: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --text: #e8ecf5;
    --muted: #8b93a8;
    --muted-2: #5c6478;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  a { color: inherit; text-decoration: none; }

  .shell { display: flex; min-height: 100vh; }

  .sidebar {
    width: 230px;
    flex-shrink: 0;
    background: var(--panel);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 18px 14px;
  }
  .brand { display: flex; align-items: center; gap: 10px; padding: 6px 8px 20px; }
  .brand .logo {
    width: 38px; height: 38px; border-radius: 10px;
    background: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
  }
  .brand .name { font-weight: 700; font-size: 15px; line-height: 1.2; }
  .brand .sub { font-size: 11px; color: var(--muted); }

  .nav { display: flex; flex-direction: column; gap: 2px; flex: 1; }
  .nav a {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; border-radius: 8px;
    color: var(--muted); font-size: 14px;
  }
  .nav a i { width: 18px; text-align: center; }
  .nav a:hover { background: var(--panel-2); color: var(--text); }
  .nav a.active { background: var(--accent); color: #fff; }

  .track-box {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px; margin-top: 16px;
  }
  .track-box .lbl { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
  .track-box .row { display: flex; gap: 6px; }
  .track-box input {
    flex: 1; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); padding: 6px 8px; font-size: 13px; min-width: 0;
  }
  .track-box button {
    background: var(--accent); border: none; color: #fff;
    border-radius: 6px; padding: 6px 12px; font-size: 13px; cursor: pointer;
  }

  .status-pill {
    margin-top: 14px; display: flex; align-items: center; gap: 8px;
    background: rgba(34,197,94,.1); border: 1px solid rgba(34,197,94,.3);
    border-radius: 10px; padding: 10px 12px; font-size: 12px;
  }
  .status-pill.offline { background: rgba(239,68,68,.1); border-color: rgba(239,68,68,.3); }
  .status-pill .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-2); }
  .status-pill.offline .dot { background: var(--red); }
  .status-pill .t1 { color: var(--accent-2); font-weight: 600; display: block; }
  .status-pill.offline .t1 { color: var(--red); }
  .status-pill .t2 { color: var(--muted); }

  .main { flex: 1; min-width: 0; padding: 18px 22px; }

  .topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
  .topbar h1 { font-size: 19px; margin: 0; display: flex; align-items: center; gap: 8px; }
  .live-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--accent-2); box-shadow: 0 0 8px var(--accent-2); animation: pulse 1.6s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
  .topbar .sub { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .top-chips { display: flex; gap: 8px; }
  .chip {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; padding: 8px 12px; font-size: 12px;
    display: flex; align-items: center; gap: 8px; color: var(--muted);
  }
  .chip b { color: var(--text); font-size: 13px; }

  .stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 16px; }
  .stat-card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 14px; min-width: 0;
  }
  .stat-card .k { font-size: 11px; color: var(--muted); margin-bottom: 6px; }
  .stat-card .v { font-size: 18px; font-weight: 700; }
  .stat-card .v small { font-size: 11px; font-weight: 400; color: var(--muted); }
  .stat-card .v.blue { color: #6fa4ff; }
  .stat-card .v.amber { color: var(--amber); }
  .stat-card .foot { font-size: 11px; color: var(--muted-2); margin-top: 4px; }

  .grid2 { display: grid; grid-template-columns: 1.5fr 0.9fr 0.9fr; gap: 14px; margin-bottom: 14px; align-items: start; }

  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
  }
  .card .card-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 14px; font-weight: 600;
  }
  .card .card-head .live-tag { font-size: 11px; color: var(--accent-2); display: flex; align-items: center; gap: 5px; font-weight: 500; }
  .card .card-head .live-tag.offline { color: var(--red); }
  .card-body { padding: 14px 16px; }

  #map { height: 400px; width: 100%; }

  .map-toggle { display: flex; background: var(--panel-2); border: 1px solid var(--border); border-radius: 8px; padding: 2px; }
  .map-toggle-btn {
    background: transparent; border: none; color: var(--muted); cursor: pointer;
    font-size: 11px; padding: 5px 10px; border-radius: 6px; font-weight: 600;
  }
  .map-toggle-btn.active { background: var(--accent); color: #fff; }
  .map-toggle-btn:hover:not(.active) { color: var(--text); }

  .info-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px;
  }
  .info-row:last-child { border-bottom: none; }
  .info-row .k { color: var(--muted); display: flex; align-items: center; gap: 8px; }
  .info-row .v { font-weight: 600; }
  .info-row .v.dim { color: var(--muted); font-weight: 400; }

  .fuel-bar { width: 90px; height: 6px; background: var(--border); border-radius: 999px; overflow: hidden; }
  .fuel-bar > div { height: 100%; background: var(--accent-2); }

  .stop-list { padding: 14px 16px; }
  .stop { display: flex; gap: 10px; position: relative; padding-bottom: 18px; }
  .stop:last-child { padding-bottom: 0; }
  .stop .line { position: absolute; left: 5px; top: 14px; bottom: -4px; width: 1px; background: var(--border); }
  .stop:last-child .line { display: none; }
  .stop .node { width: 11px; height: 11px; border-radius: 50%; background: var(--muted-2); margin-top: 2px; flex-shrink: 0; z-index: 1; }
  .stop.done .node { background: var(--accent-2); }
  .stop.current .node { background: var(--accent); box-shadow: 0 0 0 3px rgba(47,111,235,.25); }
  .stop .name { font-size: 13px; font-weight: 600; }
  .stop.current .name { color: #6fa4ff; }
  .stop .time { font-size: 11px; color: var(--muted); }
  .stop-row { display: flex; justify-content: space-between; align-items: center; flex: 1; }

  .stop.arrived .node {
    background: var(--amber);
    box-shadow: 0 0 0 4px rgba(245,158,11,.3);
    animation: stopBlink 1s infinite;
  }
  .stop.arrived .name { color: var(--amber); animation: stopBlink 1s infinite; }
  @keyframes stopBlink { 0%,100% { opacity: 1; } 50% { opacity: .25; } }

  .grid3 { display: grid; grid-template-columns: 1.6fr 1fr 1fr; gap: 14px; }

  .trip-stat { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); }
  .trip-stat:last-child { border-bottom: none; }
  .trip-stat .k { font-size: 12.5px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
  .trip-stat .v { font-size: 16px; font-weight: 700; }

  .qa-btn {
    display: flex; align-items: center; gap: 10px; width: 100%;
    background: var(--panel-2); border: 1px solid var(--border); color: var(--text);
    border-radius: 8px; padding: 9px 12px; font-size: 13px; margin-bottom: 8px; cursor: pointer;
  }
  .qa-btn:last-child { margin-bottom: 0; }
  .qa-btn:hover { border-color: var(--accent); }

  .foot-tip {
    margin-top: 14px; background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 16px; font-size: 12px; color: var(--muted); display: flex; align-items: center; justify-content: space-between;
  }

  .badge-live { font-size: 9px; background: rgba(34,197,94,.15); color: var(--accent-2); border: 1px solid rgba(34,197,94,.4); border-radius: 999px; padding: 1px 6px; margin-left: 6px; vertical-align: middle; }
  .badge-off { font-size: 9px; background: rgba(239,68,68,.12); color: var(--red); border: 1px solid rgba(239,68,68,.35); border-radius: 999px; padding: 1px 6px; margin-left: 6px; vertical-align: middle; }

  .custom-stop-label {
    background: rgba(16, 24, 44, 0.85) !important;
    border: 1px solid var(--amber) !important;
    border-radius: 6px !important;
    color: var(--text) !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    padding: 3px 8px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
  }
  .custom-stop-label::before {
    border-top-color: var(--amber) !important;
  }

  @media (max-width: 1300px) {
    .grid2 { grid-template-columns: 1fr 1fr; }
    .grid2 .card:nth-child(1) { grid-column: 1 / -1; }
  }
  @media (max-width: 1100px) {
    .stats { grid-template-columns: repeat(3, 1fr); }
    .grid2 { grid-template-columns: 1fr; }
    .grid2 .card:nth-child(1) { grid-column: auto; }
    .grid3 { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 700px) {
    .sidebar { display: none; }
    .stats { grid-template-columns: repeat(2, 1fr); }
    .grid3 { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<div class="shell">

  <aside class="sidebar">
    <div class="brand">
      <div class="logo"><i class="fa-solid fa-bus"></i></div>
      <div>
        <div class="name">City Connect</div>
        <div class="sub">Public Bus Tracker</div>
      </div>
    </div>

    <nav class="nav">
      <a href="#" class="active"><i class="fa-solid fa-table-cells"></i> Dashboard</a>
      <a href="#"><i class="fa-solid fa-location-dot"></i> Live Tracking</a>
      <a href="#"><i class="fa-solid fa-square-parking"></i> Bus Stops</a>
      <a href="#"><i class="fa-solid fa-route"></i> Routes</a>
      <a href="#"><i class="fa-solid fa-calendar"></i> Schedule</a>
      <a href="#"><i class="fa-solid fa-ticket"></i> Fares</a>
      <a href="#"><i class="fa-solid fa-comment"></i> Feedback</a>
      <a href="#"><i class="fa-solid fa-circle-question"></i> Help &amp; Support</a>
      <a href="#"><i class="fa-solid fa-circle-info"></i> About</a>
    </nav>

    <div class="track-box">
      <div class="lbl">Track another bus</div>
      <div class="row">
        <input id="busIdInput" placeholder="Enter Bus ID" />
        <button onclick="trackBusId()">Track</button>
      </div>
    </div>

    <div class="status-pill" id="sysStatusPill">
      <span class="dot"></span>
      <div>
        <span class="t1" id="sysStatus">Waiting for data…</span>
        <span class="t2" id="sysStatusTime">—</span>
      </div>
    </div>
  </aside>

  <main class="main">

    <div class="topbar">
      <div>
        <h1><span class="live-dot"></span> Live Bus Tracking</h1>
        <div class="sub">Real-time updates every 3 sec</div>
      </div>
      <div class="top-chips">
        <div class="chip"><i class="fa-regular fa-clock"></i> <b id="clockChip">--:--</b></div>
        <div class="chip"><i class="fa-solid fa-users"></i> Public View</div>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card">
        <div class="k">Bus ID</div>
        <div class="v blue" id="statBusId">—</div>
        <div class="foot">City Connect</div>
      </div>
      <div class="stat-card">
        <div class="k">Route <span id="routeBadge" class="badge-live">live</span></div>
        <div class="v" id="statRoute">—</div>
        <div class="foot" id="statRouteFoot">—</div>
      </div>
      <div class="stat-card">
        <div class="k">Current Speed <span id="speedBadge" class="badge-live">live</span></div>
        <div class="v" id="statSpeed">0 <small>km/h</small></div>
        <div class="foot" id="statSpeedFoot">waiting for GPS…</div>
      </div>
      <div class="stat-card">
        <div class="k">GPS Satellites <span id="satsBadge" class="badge-live">live</span></div>
        <div class="v" id="statSats">0</div>
        <div class="foot" id="statSatsFoot">fix quality</div>
      </div>
      <div class="stat-card">
        <div class="k">Distance Today <span id="distBadge" class="badge-live">live</span></div>
        <div class="v" id="statDistance">0.0 <small>km</small></div>
        <div class="foot" id="statDistanceFoot">since midnight, this session</div>
      </div>
      <div class="stat-card">
        <div class="k">Last Update <span id="updBadge" class="badge-live">live</span></div>
        <div class="v" id="statLastUpdate" style="font-size:14px;">—</div>
        <div class="foot" id="statAge">—</div>
      </div>
    </div>

    <div class="grid2">
      <div class="card">
        <div class="card-head">
          Live Bus Location
          <div style="display:flex;align-items:center;gap:10px;">
            <div class="map-toggle">
              <button id="btnStreet" class="map-toggle-btn" onclick="setMapView('street')">Street</button>
              <button id="btnSat" class="map-toggle-btn active" onclick="setMapView('satellite')">Satellite</button>
            </div>
            <span class="live-tag" id="mapLiveTag"><span class="live-dot" style="width:6px;height:6px;"></span> Live</span>
          </div>
        </div>
        <div id="map"></div>
      </div>

      <div class="card">
        <div class="card-head">Bus Information</div>
        <div class="card-body">
          <div class="info-row"><span class="k"><i class="fa-regular fa-id-badge"></i> Driver name</span><span class="v dim" id="infoDriver">—</span></div>
          <div class="info-row"><span class="k"><i class="fa-solid fa-hashtag"></i> Bus number</span><span class="v dim" id="infoBusNumber">—</span></div>
          <div class="info-row"><span class="k"><i class="fa-solid fa-bus-simple"></i> Bus type</span><span class="v dim" id="infoBusType">—</span></div>
          <div class="info-row"><span class="k"><i class="fa-solid fa-gas-pump"></i> Fuel level</span><span class="v" style="display:flex;align-items:center;gap:8px;"><span id="infoFuelPct">—</span><div class="fuel-bar"><div id="infoFuelBar" style="width:0%"></div></div></span></div>
          <div class="info-row"><span class="k"><i class="fa-solid fa-satellite-dish"></i> GPS signal</span><span class="v" id="infoGps">—</span></div>
          <div class="info-row"><span class="k"><i class="fa-solid fa-gauge-high"></i> Speed</span><span class="v" id="infoSpeed">—</span></div>
          <div class="info-row"><span class="k"><i class="fa-regular fa-clock"></i> Last updated</span><span class="v" id="infoUpdated">—</span></div>
          <div class="info-row"><span class="k"><i class="fa-solid fa-location-crosshairs"></i> Coordinates</span><span class="v" id="infoCoords" style="font-size:12px;">—</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">Upcoming Stops <span id="stopsBadge" class="badge-live">live</span></div>
        <div class="stop-list" id="stopList">
          <div class="stop"><div class="node"></div><div class="stop-row"><span class="name" style="color:var(--muted);">Loading route…</span></div></div>
        </div>
      </div>
    </div>

    <div class="grid3">
      <div class="card">
        <div class="card-head">
          Live Speed Chart
          <span class="live-tag" id="chartLiveTag"><span class="live-dot" style="width:6px;height:6px;"></span> Live</span>
        </div>
        <div class="card-body" style="height:220px;">
          <canvas id="speedChart"></canvas>
        </div>
      </div>

      <div class="card">
        <div class="card-head">Trip Summary (Today) <span class="badge-live">live</span></div>
        <div class="card-body">
          <div class="trip-stat"><span class="k"><i class="fa-solid fa-road"></i> Distance travelled</span><span class="v" id="tripDistance">0.0 km</span></div>
          <div class="trip-stat"><span class="k"><i class="fa-solid fa-gauge"></i> Average speed</span><span class="v" id="tripAvgSpeed">0.0 km/h</span></div>
          <div class="trip-stat"><span class="k"><i class="fa-solid fa-gauge-high"></i> Top speed</span><span class="v" id="tripMaxSpeed">0.0 km/h</span></div>
          <div class="trip-stat"><span class="k"><i class="fa-regular fa-clock"></i> Tracking since</span><span class="v" id="tripSince" style="font-size:12px;">—</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">Quick Actions</div>
        <div class="card-body">
          <button class="qa-btn"><i class="fa-regular fa-eye"></i> View route</button>
          <button class="qa-btn"><i class="fa-solid fa-triangle-exclamation"></i> Report issue</button>
          <button class="qa-btn" onclick="shareLocation()"><i class="fa-solid fa-share-nodes"></i> Share location</button>
        </div>
      </div>
    </div>

    <div class="foot-tip">
      <span><i class="fa-regular fa-lightbulb"></i> Tip: bookmark this page for quick access to real-time bus tracking.</span>
      <span>Need help? <a href="#" style="color:#6fa4ff;">Contact support</a></span>
    </div>

  </main>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const POLL_INTERVAL_MS = 3000;
  const MAX_CHART_POINTS = 20;
  const ARRIVAL_RADIUS_KM = 0.15;

  const MIN_JUMP_KM = 0.0005; 
  const MAX_JUMP_KM = 5;      

  let selectedBusId = null;
  let hasCentered = false;
  const markers = {};
  const speedHistory = { labels: [], values: [] };
  const busTrip = {};

  const GGU_LAT = 22.1293;
  const GGU_LNG = 82.1360;

  const map = L.map('map', { zoomControl: true }).setView([GGU_LAT, GGU_LNG], 13);

  const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  });
  const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics',
    maxZoom: 19
  });

  satelliteLayer.addTo(map);

  function setMapView(type) {
    if (type === 'street') {
      if (map.hasLayer(satelliteLayer)) map.removeLayer(satelliteLayer);
      streetLayer.addTo(map);
      document.getElementById('btnStreet').classList.add('active');
      document.getElementById('btnSat').classList.remove('active');
    } else {
      if (map.hasLayer(streetLayer)) map.removeLayer(streetLayer);
      satelliteLayer.addTo(map);
      document.getElementById('btnSat').classList.add('active');
      document.getElementById('btnStreet').classList.remove('active');
    }
  }

  const busIcon = L.divIcon({
    className: '',
    html: `
      <div style="
        width: 36px;
        height: 36px;
        background: #2f6feb;
        border: 2px solid #ffffff;
        border-radius: 50%;
        box-shadow: 0 0 12px rgba(47, 111, 235, 0.8), 0 2px 6px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-size: 18px;
      ">
        <i class="fa-solid fa-bus"></i>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18]
  });

  async function loadCampusRoad() {
    try {
      const res = await fetch('/campus-road');
      if (!res.ok) return;
      const data = await res.json();
      const latlngs = data.road.map(p => [p.lat, p.lng]);

      L.polyline(latlngs, {
        color: '#f59e0b',
        weight: 6,
        opacity: 0.9,
        dashArray: '1,8',
        lineCap: 'round'
      }).addTo(map).bindPopup(`<b>${data.label}</b><br>Highlighted campus road`);

      data.road.forEach((point) => {
        if (!point.label) return;
        const marker = L.marker([point.lat, point.lng], {
          icon: L.divIcon({
            className: '',
            html: `<div style="width:14px;height:14px;border-radius:50%;background:#f59e0b;border:2px solid #fff;box-shadow:0 0 8px rgba(0,0,0,.6);"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7]
          })
        }).addTo(map);

        marker.bindTooltip(point.label, {
          permanent: true,
          direction: 'top',
          className: 'custom-stop-label',
          offset: [0, -8]
        });
      });

    } catch (err) {
      console.warn('Could not load campus road overlay:', err);
    }
  }
  loadCampusRoad();

  const chartLibAvailable = typeof Chart !== 'undefined';
  let speedChart = null;

  if (chartLibAvailable) {
    const ctx = document.getElementById('speedChart').getContext('2d');
    speedChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: speedHistory.labels,
        datasets: [{
          label: 'Speed (km/h)',
          data: speedHistory.values,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.12)',
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#5c6478', font: { size: 10 } }, grid: { color: '#202b45' } },
          y: { beginAtZero: true, ticks: { color: '#5c6478', font: { size: 10 } }, grid: { color: '#202b45' } }
        }
      }
    });
  }

  function secondsSince(iso) { return (Date.now() - new Date(iso).getTime()) / 1000; }
  function fmtTime(iso) { return iso ? new Date(iso).toLocaleTimeString() : '—'; }
  function todayStr() { return new Date().toISOString().slice(0, 10); }

  function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function updateTripOdometer(bus) {
    const today = todayStr();
    let rec = busTrip[bus.bus_id];

    if (!rec || rec.date !== today) {
      rec = {
        date: today,
        km: 0,
        lastLat: bus.lat,
        lastLng: bus.lng,
        maxSpeed: bus.speed || 0,
        speedSum: 0,
        speedCount: 0,
        since: new Date().toISOString()
      };
      busTrip[bus.bus_id] = rec;
    } else if (bus.online) {
      const jump = haversineKm(rec.lastLat, rec.lastLng, bus.lat, bus.lng);
      if (jump >= MIN_JUMP_KM && jump <= MAX_JUMP_KM) {
        rec.km += jump;
      }
      rec.lastLat = bus.lat;
      rec.lastLng = bus.lng;
    }

    if (bus.online) {
      rec.maxSpeed = Math.max(rec.maxSpeed, bus.speed || 0);
      rec.speedSum += (bus.speed || 0);
      rec.speedCount += 1;
    }

    return rec;
  }

  function trackBusId() {
    const val = document.getElementById('busIdInput').value.trim();
    if (val) { selectedBusId = val; hasCentered = false; }
  }

  function shareLocation() {
    const bus = window.__lastSelectedBus;
    if (!bus) { alert('No location yet.'); return; }
    const url = `https://www.google.com/maps?q=${bus.lat},${bus.lng}`;
    if (navigator.share) {
      navigator.share({ title: `${bus.bus_id} location`, url });
    } else {
      navigator.clipboard.writeText(url);
      alert('Location link copied: ' + url);
    }
  }

  function updateClock() {
    document.getElementById('clockChip').textContent = new Date().toLocaleTimeString();
  }
  setInterval(updateClock, 1000);
  updateClock();

  function setLiveBadges(online) {
    const liveIds = ['routeBadge', 'speedBadge', 'satsBadge', 'distBadge', 'updBadge', 'stopsBadge'];
    liveIds.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const isGpsBadge = ['speedBadge', 'satsBadge', 'distBadge', 'updBadge'].includes(id);
      if (isGpsBadge) {
        el.className = online ? 'badge-live' : 'badge-off';
        el.textContent = online ? 'live' : 'offline';
      }
    });

    document.getElementById('mapLiveTag').className = 'live-tag' + (online ? '' : ' offline');
    document.getElementById('chartLiveTag').className = 'live-tag' + (online ? '' : ' offline');
  }

  async function poll() {
    try {
      const res = await fetch('/location');
      if (!res.ok) throw new Error('bad response');
      const buses = await res.json();

      if (!buses.length) {
        document.getElementById('sysStatus').textContent = 'No buses configured';
        document.getElementById('sysStatusTime').textContent = 'Waiting for setup';
        return;
      }

      buses.forEach(bus => {
        const pos = [bus.lat, bus.lng];
        if (markers[bus.bus_id]) {
          markers[bus.bus_id].setLatLng(pos);
        } else {
          markers[bus.bus_id] = L.marker(pos, { icon: busIcon }).addTo(map).bindPopup(bus.bus_id);
        }
        const statusTxt = bus.online ? `${(bus.speed || 0).toFixed(1)} km/h` : 'Offline — showing ';
        markers[bus.bus_id].setPopupContent(`<b>${bus.bus_id}</b><br>${statusTxt}`);
        updateTripOdometer(bus);
      });

      let bus = selectedBusId ? buses.find(b => b.bus_id === selectedBusId) : buses[0];
      if (!bus) bus = buses[0];
      window.__lastSelectedBus = bus;

      if (!hasCentered) {
        map.setView([bus.lat, bus.lng], 13);
        hasCentered = true;
      }

      const online = !!bus.online;
      const cfg = bus.config || {};

      setLiveBadges(online);

      document.getElementById('statBusId').textContent = bus.bus_id;
      document.getElementById('statRoute').textContent = cfg.route_name || 'No route assigned';
      document.getElementById('statRouteFoot').textContent = cfg.origin && cfg.destination ? `${cfg.origin} → ${cfg.destination}` : '—';

      document.getElementById('statSpeed').innerHTML = `${(bus.speed || 0).toFixed(1)} <small>km/h</small>`;
      document.getElementById('statSpeedFoot').textContent = online ? 'updating live' : 'ESP32 offline — last known speed 0';
      document.getElementById('statSats').textContent = bus.sats ?? 0;
      document.getElementById('statSatsFoot').textContent = online ? ((bus.sats || 0) >= 6 ? 'strong fix' : (bus.sats || 0) > 0 ? 'weak fix' : 'no fix') : 'no fix (offline)';
      document.getElementById('statLastUpdate').textContent = bus.updated_at ? fmtTime(bus.updated_at) : 'Not connected';
      document.getElementById('statAge').textContent = online ? Math.round(secondsSince(bus.updated_at)) + 's ago' : 'offline';

      const trip = busTrip[bus.bus_id];
      if (trip) {
        document.getElementById('statDistance').innerHTML = `${trip.km.toFixed(2)} <small>km</small>`;
        document.getElementById('tripDistance').textContent = `${trip.km.toFixed(2)} km`;
        const avgSpeed = trip.speedCount ? (trip.speedSum / trip.speedCount) : 0;
        document.getElementById('tripAvgSpeed').textContent = `${avgSpeed.toFixed(1)} km/h`;
        document.getElementById('tripMaxSpeed').textContent = `${trip.maxSpeed.toFixed(1)} km/h`;
        document.getElementById('tripSince').textContent = new Date(trip.since).toLocaleString();
      }

      document.getElementById('infoDriver').textContent = cfg.driver_name || '—';
      document.getElementById('infoBusNumber').textContent = cfg.bus_number || '—';
      document.getElementById('infoBusType').textContent = cfg.bus_type || '—';
      const hasFuel = typeof bus.fuel === 'number';
      document.getElementById('infoFuelPct').textContent = hasFuel ? bus.fuel + '%' : (online ? '—' : '');
      document.getElementById('infoFuelBar').style.width = (hasFuel ? bus.fuel : 0) + '%';
      document.getElementById('infoGps').textContent = online ? `${bus.sats ?? 0} satellites` : 'No GPS signal (offline)';
      document.getElementById('infoSpeed').textContent = `${(bus.speed || 0).toFixed(1)} km/h`;
      document.getElementById('infoUpdated').textContent = bus.updated_at ? fmtTime(bus.updated_at) : 'Not connected';
      document.getElementById('infoCoords').textContent = `${bus.lat.toFixed(5)}, ${bus.lng.toFixed(5)}`;

      const stopList = document.getElementById('stopList');
      if (cfg.stops && cfg.stops.length) {
        stopList.innerHTML = cfg.stops.map(s => {
          let arrived = false;
          if (online && typeof s.lat === 'number' && typeof s.lng === 'number') {
            arrived = haversineKm(bus.lat, bus.lng, s.lat, s.lng) <= ARRIVAL_RADIUS_KM;
          }
          const cls = arrived ? 'arrived' : (s.status === 'done' ? 'done' : (s.status === 'current' ? 'current' : ''));
          return `
          <div class="stop ${cls}">
            <div class="line"></div>
            <div class="node"></div>
            <div class="stop-row">
              <span class="name">${s.name}${arrived ? ' <span style=\'font-size:10px;\'>● bus here now</span>' : (s.status === 'current' ? ' <span style=\'font-size:10px;color:var(--accent-2);\'>●</span>' : '')}</span>
              <span class="time">${s.time || ''}</span>
            </div>
          </div>`;
        }).join('');
      }

      const pill = document.getElementById('sysStatusPill');
      if (online) {
        pill.classList.remove('offline');
        document.getElementById('sysStatus').textContent = 'All systems operational';
        document.getElementById('sysStatusTime').textContent = `${buses.length} bus${buses.length === 1 ? '' : 'es'} reporting · last check ${new Date().toLocaleTimeString()}`;
      } else {
        pill.classList.add('offline');
        document.getElementById('sysStatus').textContent = bus.updated_at ? 'ESP32 offline / signal lost' : 'ESP32 not connected';
        document.getElementById('sysStatusTime').textContent = 'Showing driver, route & default location';
      }

      if (chartLibAvailable && speedChart && online) {
        speedHistory.labels.push(new Date(bus.updated_at).toLocaleTimeString().slice(0, 5));
        speedHistory.values.push(bus.speed || 0);
        if (speedHistory.labels.length > MAX_CHART_POINTS) {
          speedHistory.labels.shift();
          speedHistory.values.shift();
        }
        speedChart.update();
      }

    } catch (err) {
      document.getElementById('sysStatus').textContent = 'Connection error';
      document.getElementById('sysStatusTime').textContent = 'Retrying…';
    }
  }

  poll();
  setInterval(poll, POLL_INTERVAL_MS);
</script>

</body>
</html>"""


@app.route("/")
def index():
    return Response(DASHBOARD_HTML, mimetype="text/html")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# if __name__ == "__main__":
#     local_ip = get_local_ip()
#     print("\n" + "=" * 55)
#     print(f"  City Connect Server Running!")
#     print(f"  Dashboard: http://localhost:5000")
#     print(f"  ESP32 Target Endpoint: http://{local_ip}:5000/update")
#     print("=" * 55 + "\n")
#
#     app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
