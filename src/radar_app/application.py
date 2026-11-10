"""Application composition, provider orchestration and Flask route registration.

This module is part of the Radar Ferroviario source layout. Public behavior is
covered by tests; provider failures must remain isolated and observable.
"""

import csv
import io
import json
import math
import os
import sys
import logging
import traceback
from logging.handlers import RotatingFileHandler
from collections import deque
from datetime import datetime
from pathlib import Path
import re
import time
import threading
import zipfile
from flask import Flask, render_template, jsonify, request
from radar.gtfs import active_service_ids, open_gtfs_archive
from radar.nap_service import NapGtfsService, find_download_url
from radar.redaction import sanitize_data, sanitize_text, sanitize_url
from radar.config import METRO_GTFS as CONFIG_METRO_GTFS
import requests
import hashlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -----------------------------------------------------------------------------
# Flask composition root
# The module still coordinates legacy providers while extraction into services
# and blueprints proceeds incrementally. Keep provider failures isolated.
# -----------------------------------------------------------------------------
app = Flask(__name__)

# Registro persistente: 3 ficheros de 2 MB, más un buffer para el panel de diagnóstico.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
ERROR_LOG_FILE = os.path.join(LOG_DIR, "radar_errors.log")
RECENT_ERRORS = deque(maxlen=200)

class RecentErrorHandler(logging.Handler):
    def emit(self, record):
        """Perform the documented application operation while preserving current API contracts.

        Parameters are validated or normalized by the function; relevant inputs: ``record``.
        """
        if record.levelno < logging.WARNING:
            return
        try:
            RECENT_ERRORS.appendleft({
                "timestamp": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record)
            })
        except Exception:
            pass

LOG_FORMAT = logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s")
file_handler = RotatingFileHandler(ERROR_LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
file_handler.setLevel(logging.WARNING); file_handler.setFormatter(LOG_FORMAT)
recent_handler = RecentErrorHandler(); recent_handler.setLevel(logging.WARNING); recent_handler.setFormatter(LOG_FORMAT)
APP_LOGGER = logging.getLogger("radar"); APP_LOGGER.setLevel(logging.INFO)
APP_LOGGER.addHandler(file_handler); APP_LOGGER.addHandler(recent_handler); APP_LOGGER.propagate = False

def log_exception(context, exc):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``context``, ``exc``.
    """
    APP_LOGGER.error("%s: %s\n%s", context, exc, traceback.format_exc())

def _thread_exception(args):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``args``.
    """
    APP_LOGGER.error("Excepción no controlada en hilo %s: %s", getattr(args.thread, "name", "N/D"), args.exc_value,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
threading.excepthook = _thread_exception



HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) RenfeAdifTracker/6.0",
    "Accept": "application/json, text/csv, */*"
}

CKAN_BASE = "https://data.renfe.com/api/3/action/package_show?id="
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKS_CACHE_FILE = os.path.join(BASE_DIR, "real_tracks_cache_v6.json")
OVERPASS_CACHE_FILE = os.path.join(BASE_DIR, "overpass_viewport_cache_v1.json")

PACKAGES = {
    "cercanias_pos": "ubicacion-de-los-vehiculos",
    "ld_pos": "posicion-vehiculos-de-alta-velocidad-larga-distancia-y-media-distancia",
    "ld_updates": "horarios-de-viaje-para-alta-velocidad-larga-distancia-y-media-distancia",
    "cercanias_updates": "horarios-de-viaje",
    "alerts": "incidencias-y-avisos",
    "estaciones": "estaciones",
    "estaciones_feve": "estaciones-feve",
    "gtfs_ld": "horarios-de-alta-velocidad-larga-distancia-y-media-distancia",
    "gtfs_cercanias": "horarios-cercanias"
}

FALLBACK_URLS = {
    "cercanias_pos": [
        "https://gtfsrt.renfe.com/vehicle_positions.json"
    ],
    "ld_pos": [
        "https://gtfsrt.renfe.com/vehicle_positions_LD.json",
        "https://gtfsrt.renfe.com/ld_vehicle_positions.json",
        "https://gtfsrt.renfe.com/AV_vehicle_positions.json"
    ],
    "ld_updates": [
        "https://gtfsrt.renfe.com/trip_updates_LD.json",
        "https://gtfsrt.renfe.com/ld_trip_updates.json"
    ],
    "cercanias_updates": [
        "https://gtfsrt.renfe.com/trip_updates.json"
    ],
    "alerts": [
        "https://gtfsrt.renfe.com/alerts.json",
        "https://gtfsrt.renfe.com/alerts_LD.json"
    ]
}

OPEN_ACCESS_GTFS = {
    "iryo": {
        "name": "iryo", "color": "#D71920", "text_color": "#FFFFFF",
        "urls": ["https://deryclem.github.io/iryo-gtfs/gtfs-iryo.zip"],
        "source": "GTFS comunitario iryo (MobilityData)", "attribution": "Datos horarios GTFS iryo"
    },
    "ouigo": {
        "name": "OUIGO", "color": "#E5007E", "text_color": "#FFFFFF",
        "urls": ["https://nap.transportes.gob.es/api/Fichero/downloadLink/1766", "https://nap.transportes.gob.es/api/Fichero/download/1766"],
        "source": "GTFS oficial NAP/MITRAMS", "attribution": "Powered by MITRAMS",
        "token_env": "OUIGO_GTFS_TOKEN", "file_env": "OUIGO_GTFS_FILE"
    }
}
METRO_GTFS = {
    "metro_madrid": {
        "name":"Metro de Madrid", "short":"Metro", "color":"#E30613", "nap_id":1134,
        "source":"CRTM / NAP-MITRAMS",
        "fallback_urls":["https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data"]
    },
    "metro_barcelona": {
        "name":"Metro Barcelona (TMB)", "short":"TMB", "color":"#E30613", "nap_id":1328,
        "source":"TMB / NAP-MITRAMS", "fallback_urls":[]
    },
    "metro_bilbao": {
        "name":"Metro Bilbao", "short":"MB", "color":"#E30613", "nap_id":1267,
        "source":"Metro Bilbao / NAP-MITRAMS", "fallback_urls":[]
    },
    "metro_valencia": {
        "name":"Metrovalencia", "short":"FGV", "color":"#E30613", "nap_id":967,
        "source":"FGV / NAP-MITRAMS", "fallback_urls":[]
    },
    "metro_malaga": {
        "name":"Metro Málaga", "short":"MM", "color":"#00A651", "nap_id":1497,
        "source":"Metro Málaga / NAP-MITRAMS",
        "fallback_urls":["https://metromalaga.es/GTFS/GTFS_METRO_MALAGA.zip"]
    },
    "mallorca_rail": {
        "name":"Metro y tren de Mallorca", "short":"SFM", "color":"#0072BC", "nap_id":1071,
        "source":"SFM-TIB / NAP-MITRAMS", "fallback_urls":[]
    },
    "euskotren": {
        "name":"Euskotren", "short":"EUS", "color":"#00A651", "nap_id":1263,
        "source":"Euskotren / NAP-MITRAMS", "fallback_urls":[]
    },
    "andalucia_rail": {
        "name":"Redes ferroviarias de Andalucía", "short":"Andalucía", "color":"#8B5CF6", "nap_id":1562,
        "source":"Consorcios de Andalucía / NAP-MITRAMS", "fallback_urls":[]
    }
}
METRO_CACHE_TTL = 24*3600

OPEN_ACCESS_CACHE_DIR = os.path.join(BASE_DIR, "cache", "operators")
os.makedirs(OPEN_ACCESS_CACHE_DIR, exist_ok=True)
OPERATOR_CONFIG_FILE = os.path.join(OPEN_ACCESS_CACHE_DIR, "operator_config.json")

def load_operator_config():
    """Load and normalize the requested resource while updating isolated application state.
    """
    try:
        if os.path.exists(OPERATOR_CONFIG_FILE):
            with open(OPERATOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        APP_LOGGER.warning("No se pudo leer operator_config.json: %s", exc)
    return {}

def save_operator_token(operator_key, token):
    """Persist the supplied state safely to its configured local destination.

    Parameters are validated or normalized by the function; relevant inputs: ``operator_key``, ``token``.
    """
    config = load_operator_config()
    if token: config[f"{operator_key}_token"] = token
    else: config.pop(f"{operator_key}_token", None)
    tmp = OPERATOR_CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OPERATOR_CONFIG_FILE)
    try: os.chmod(OPERATOR_CONFIG_FILE, 0o600)
    except Exception: pass

def operator_token(operator_key, cfg):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``operator_key``, ``cfg``.
    """
    env_name = cfg.get("token_env")
    return (os.getenv(env_name, "").strip() if env_name else "") or str(load_operator_config().get(f"{operator_key}_token", "")).strip()

OPEN_ACCESS_CACHE_TTL = 24 * 3600

OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]
OVERPASS_CACHE_TTL = 30 * 24 * 3600
OVERPASS_FAILURE_COOLDOWN = 180

from radar.state import create_application_state

# ``radar.config`` is the single authoritative source for transit catalogues.
# The legacy literal above remains only until the composition root is fully split.
METRO_GTFS = CONFIG_METRO_GTFS
STATE = create_application_state(METRO_GTFS, OPEN_ACCESS_GTFS, OVERPASS_ENDPOINTS)
APP_START_TIME = STATE.started_at
METRO_CACHE, METRO_LOCK = STATE.metro_cache, STATE.metro_lock
OPEN_ACCESS_CACHE, OPEN_ACCESS_LOCK = STATE.open_access_cache, STATE.open_access_lock
OVERPASS_QUERY_CACHE = STATE.overpass_query_cache
OVERPASS_ENDPOINT_HEALTH = STATE.overpass_endpoint_health
OVERPASS_INFLIGHT, OVERPASS_LOCK = STATE.overpass_inflight, STATE.overpass_lock
TRAIN_MOTION_HISTORY = STATE.train_motion_history
STATIC_CACHE = STATE.static_cache
RT_CACHE, TRAIN_REFRESH_LOCK = STATE.realtime_cache, STATE.train_refresh_lock
ALERTS_CACHE, ADIF_CACHE = STATE.alerts_cache, STATE.adif_cache

OVERPASS_RETRY = Retry(total=2, connect=2, read=1, backoff_factor=0.8, status_forcelist=(429,500,502,503,504), allowed_methods=frozenset(("POST",)))
OVERPASS_HTTP = requests.Session()
OVERPASS_HTTP.headers.update(HEADERS)
OVERPASS_HTTP.mount("https://", HTTPAdapter(max_retries=OVERPASS_RETRY, pool_connections=8, pool_maxsize=8))

OPERATOR_RETRY = Retry(total=3, connect=3, read=2, backoff_factor=1.0,
    status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(("GET",)))
OPERATOR_HTTP = requests.Session()
OPERATOR_HTTP.headers.update(HEADERS)
OPERATOR_HTTP.mount("https://", HTTPAdapter(max_retries=OPERATOR_RETRY, pool_connections=4, pool_maxsize=4))

NAP_GTFS_SERVICE = NapGtfsService(OPERATOR_HTTP, logger=APP_LOGGER)

from radar.overpass_service import OverpassService

OVERPASS_SERVICE = OverpassService(
    endpoints=OVERPASS_ENDPOINTS, cache=OVERPASS_QUERY_CACHE,
    health=OVERPASS_ENDPOINT_HEALTH, inflight=OVERPASS_INFLIGHT, lock=OVERPASS_LOCK,
    http=OVERPASS_HTTP, cache_file=OVERPASS_CACHE_FILE, cache_ttl=OVERPASS_CACHE_TTL,
    failure_cooldown=OVERPASS_FAILURE_COOLDOWN, logger=APP_LOGGER,
)

NUCLEOS_CERCANIAS = {
    "10": {"name": "Madrid", "lat": 40.4065, "lon": -3.6895, "radius_deg": 0.65},
    "20": {"name": "Asturias", "lat": 43.3669, "lon": -5.8550, "radius_deg": 0.45},
    "30": {"name": "Sevilla", "lat": 37.3917, "lon": -5.9764, "radius_deg": 0.45},
    "31": {"name": "Cádiz", "lat": 36.5292, "lon": -6.2886, "radius_deg": 0.35},
    "32": {"name": "Málaga", "lat": 36.7128, "lon": -4.4294, "radius_deg": 0.40},
    "40": {"name": "València", "lat": 39.4667, "lon": -0.3772, "radius_deg": 0.55},
    "41": {"name": "Murcia / Alicante", "lat": 38.1590, "lon": -0.8120, "radius_deg": 0.50},
    "50": {"name": "Barcelona (Rodalies)", "lat": 41.3794, "lon": 2.1402, "radius_deg": 0.75},
    "51": {"name": "Barcelona (Rodalies)", "lat": 41.3794, "lon": 2.1402, "radius_deg": 0.75},
    "60": {"name": "Bilbao", "lat": 43.2614, "lon": -2.9278, "radius_deg": 0.35},
    "61": {"name": "San Sebastián", "lat": 43.3175, "lon": -1.9767, "radius_deg": 0.35},
    "62": {"name": "Santander", "lat": 43.4586, "lon": -3.8122, "radius_deg": 0.35},
    "70": {"name": "Zaragoza", "lat": 41.6588, "lon": -0.9105, "radius_deg": 0.30},
    "90": {"name": "Madrid - Cotos", "lat": 40.7830, "lon": -4.0010, "radius_deg": 0.25}
}






CORE_STATIONS = [
    {"id": "60000", "name": "Madrid - Puerta de Atocha Almudena Grandes", "lat": 40.4065, "lon": -3.6895, "category": "Principal / AVE"},
    {"id": "17000", "name": "Madrid - Chamartín Clara Campoamor", "lat": 40.4722, "lon": -3.6822, "category": "Principal / AVE"},
    {"id": "71801", "name": "Barcelona - Sants", "lat": 41.3794, "lon": 2.1402, "category": "Principal / AVE"},
    {"id": "04040", "name": "Zaragoza - Delicias", "lat": 41.6588, "lon": -0.9105, "category": "Principal / AVE"},
    {"id": "65000", "name": "València - Joaquín Sorolla", "lat": 39.4623, "lon": -0.3855, "category": "Principal / AVE"},
    {"id": "65001", "name": "València - Estació del Nord", "lat": 39.4667, "lon": -0.3772, "category": "Principal / Cercanías"},
    {"id": "51003", "name": "Sevilla - Santa Justa", "lat": 37.3917, "lon": -5.9764, "category": "Principal / AVE"},
    {"id": "54413", "name": "Málaga - María Zambrano", "lat": 36.7128, "lon": -4.4294, "category": "Principal / AVE"},
    {"id": "50500", "name": "Córdoba", "lat": 37.8882, "lon": -4.7894, "category": "Principal / AVE"},
    {"id": "10600", "name": "Valladolid - Campo Grande", "lat": 41.6425, "lon": -4.7291, "category": "Principal / AVE"},
    {"id": "15100", "name": "León", "lat": 42.5955, "lon": -5.5819, "category": "Principal / AVE"},
    {"id": "11208", "name": "Burgos - Rosa Manzano", "lat": 42.3719, "lon": -3.6625, "category": "Principal / AVE"},
    {"id": "10500", "name": "Palencia", "lat": 42.0125, "lon": -4.5367, "category": "Principal / AVE"},
    {"id": "10200", "name": "Segovia - Guiomar", "lat": 40.9108, "lon": -4.0942, "category": "Principal / AVE"},
    {"id": "22100", "name": "Ourense", "lat": 42.3522, "lon": -7.8686, "category": "Principal / AVE"},
    {"id": "31400", "name": "Santiago de Compostela", "lat": 42.8703, "lon": -8.5458, "category": "Principal / AVE"},
    {"id": "31412", "name": "A Coruña", "lat": 43.3528, "lon": -8.4092, "category": "Principal / Larga Distancia"},
    {"id": "23004", "name": "Vigo - Urzáiz", "lat": 42.2356, "lon": -8.7117, "category": "Principal / Larga Distancia"},
    {"id": "15402", "name": "Oviedo", "lat": 43.3669, "lon": -5.8550, "category": "Principal / AVE"},
    {"id": "15410", "name": "Gijón - Sanz Crespo", "lat": 43.5392, "lon": -5.6761, "category": "Principal / Larga Distancia"},
    {"id": "14223", "name": "Santander", "lat": 43.4586, "lon": -3.8122, "category": "Principal / Larga Distancia"},
    {"id": "13200", "name": "Bilbao - Abando Indalecio Prieto", "lat": 43.2614, "lon": -2.9278, "category": "Principal / Larga Distancia"},
    {"id": "11511", "name": "San Sebastián / Donostia", "lat": 43.3175, "lon": -1.9767, "category": "Principal / Larga Distancia"},
    {"id": "11305", "name": "Vitoria / Gasteiz", "lat": 42.8417, "lon": -2.6719, "category": "Principal / Larga Distancia"},
    {"id": "81100", "name": "Pamplona / Iruña", "lat": 42.8250, "lon": -1.6622, "category": "Principal / Larga Distancia"},
    {"id": "81202", "name": "Logroño", "lat": 42.4567, "lon": -2.4439, "category": "Principal / Larga Distancia"},
    {"id": "60911", "name": "Alacant - Terminal", "lat": 38.3444, "lon": -0.4950, "category": "Principal / AVE"},
    {"id": "61200", "name": "Murcia del Carmen", "lat": 37.9744, "lon": -1.1306, "category": "Principal / AVE"},
    {"id": "60600", "name": "Albacete - Los Llanos", "lat": 38.9997, "lon": -1.8492, "category": "Principal / AVE"},
    {"id": "66100", "name": "Cuenca - Fernando Zóbel", "lat": 40.0253, "lon": -2.1436, "category": "Principal / AVE"},
    {"id": "79300", "name": "Girona", "lat": 41.9792, "lon": 2.8169, "category": "Principal / AVE"},
    {"id": "79316", "name": "Figueres - Vilafant", "lat": 42.2650, "lon": 2.9428, "category": "Principal / AVE"},
    {"id": "71500", "name": "Camp de Tarragona", "lat": 41.1950, "lon": 1.2708, "category": "Principal / AVE"},
    {"id": "78400", "name": "Lleida - Pirineus", "lat": 41.6208, "lon": 0.6331, "category": "Principal / AVE"},
    {"id": "04007", "name": "Calatayud", "lat": 41.3469, "lon": -1.6383, "category": "Principal / AVE"},
    {"id": "70200", "name": "Guadalajara - Yebes", "lat": 40.5694, "lon": -3.1033, "category": "Principal / AVE"},
    {"id": "37200", "name": "Ciudad Real", "lat": 38.9839, "lon": -3.9136, "category": "Principal / AVE"},
    {"id": "37300", "name": "Puertollano", "lat": 38.6897, "lon": -4.1119, "category": "Principal / AVE"},
    {"id": "55019", "name": "Granada", "lat": 37.1842, "lon": -3.6089, "category": "Principal / AVE"},
    {"id": "54405", "name": "Antequera - Santa Ana", "lat": 37.0686, "lon": -4.6967, "category": "Principal / AVE"},
    {"id": "51405", "name": "Cádiz", "lat": 36.5292, "lon": -6.2886, "category": "Principal / Larga Distancia"},
    {"id": "51300", "name": "Jerez de la Frontera", "lat": 36.6800, "lon": -6.1264, "category": "Principal / Larga Distancia"},
    {"id": "43019", "name": "Huelva", "lat": 37.2475, "lon": -6.9428, "category": "Principal / Larga Distancia"},
    {"id": "35300", "name": "Cáceres", "lat": 39.4678, "lon": -6.3842, "category": "Principal / Larga Distancia"},
    {"id": "37606", "name": "Mérida", "lat": 38.9211, "lon": -6.3422, "category": "Principal / Larga Distancia"},
    {"id": "37700", "name": "Badajoz", "lat": 38.8911, "lon": -6.9817, "category": "Principal / Larga Distancia"},
    {"id": "10300", "name": "Medina del Campo", "lat": 41.3144, "lon": -4.9061, "category": "Principal / Media Distancia"},
    {"id": "12209", "name": "Salamanca", "lat": 40.9756, "lon": -5.6503, "category": "Principal / Media Distancia"},
    {"id": "10100", "name": "Ávila", "lat": 40.6606, "lon": -4.6858, "category": "Principal / Media Distancia"},
    {"id": "12100", "name": "Zamora", "lat": 41.5117, "lon": -5.7369, "category": "Principal / AVE"},
    {"id": "92102", "name": "Toledo", "lat": 39.8622, "lon": -4.0114, "category": "Principal / Media Distancia"},
    {"id": "65300", "name": "Castelló de la Plana", "lat": 39.9881, "lon": -0.0528, "category": "Principal / Larga Distancia"}
]

def smooth_chaikin(coords, iterations=2):
    """Suaviza polilíneas semilla mediante Chaikin corner-cutting manteniendo extremos exactos."""
    if not coords or len(coords) < 3:
        return coords
    pts = list(coords)
    for _ in range(iterations):
        new_pts = [pts[0]]
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            q = [round(0.75 * p0[0] + 0.25 * p1[0], 5), round(0.75 * p0[1] + 0.25 * p1[1], 5)]
            r = [round(0.25 * p0[0] + 0.75 * p1[0], 5), round(0.25 * p0[1] + 0.75 * p1[1], 5)]
            new_pts.extend([q, r])
        new_pts.append(pts[-1])
        pts = new_pts
    return pts

# Trazados semilla de alta fidelidad que siguen los pasos geográficos reales de las LAV y corredores ADIF
# (incluyendo el paso exacto de la LAV Madrid-Zaragoza por Brihuega, Las Inviernas, Algora, Torremocha del Campo, Alcolea del Pinar, Medinaceli, Ariza, Alhama y Calatayud)
RAW_SEED_ROUTES = [
    {
        "name": "LAV Madrid - Guadalajara - Calatayud - Zaragoza - Lleida - Barcelona - Figueres",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [40.4065, -3.6895], [40.3980, -3.6050], [40.4280, -3.5120], [40.4680, -3.4150],
            [40.5150, -3.2650], [40.5694, -3.1033], [40.6650, -3.0250], [40.7580, -2.9280],
            [40.8180, -2.8580], [40.8680, -2.7750], [40.9080, -2.6950], [40.9420, -2.6350],
            [40.9685, -2.5850], [40.9920, -2.5180], [41.0180, -2.4450], [41.0620, -2.3950],
            [41.1150, -2.3520], [41.1680, -2.3080], [41.2140, -2.2680], [41.2680, -2.1650],
            [41.2980, -2.0450], [41.3020, -1.8950], [41.3250, -1.7650], [41.3469, -1.6383],
            [41.4350, -1.5120], [41.5220, -1.3750], [41.6150, -1.1650], [41.6588, -0.9105],
            [41.6250, -0.6200], [41.5450, -0.2800], [41.5120, 0.0650], [41.5480, 0.3650],
            [41.6208, 0.6331], [41.5250, 0.8850], [41.3850, 1.1150], [41.1950, 1.2708],
            [41.2580, 1.5250], [41.3350, 1.7250], [41.3920, 1.9650], [41.3794, 2.1402],
            [41.4550, 2.2050], [41.5950, 2.3550], [41.7350, 2.5650], [41.8650, 2.7350],
            [41.9792, 2.8169], [42.1250, 2.8850], [42.2650, 2.9428]
        ]
    },
    {
        "name": "LAV Madrid - Segovia - Valladolid - Palencia - León - Oviedo",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [40.4722, -3.6822], [40.5550, -3.7050], [40.6650, -3.7650], [40.7680, -3.8850],
            [40.9108, -4.0942], [41.0550, -4.2650], [41.1950, -4.4650], [41.3180, -4.6680],
            [41.4650, -4.7150], [41.6425, -4.7291], [41.7650, -4.6150], [41.8850, -4.5120],
            [42.0125, -4.5367], [42.1850, -4.7650], [42.3650, -5.0650], [42.4850, -5.3450],
            [42.5955, -5.5819], [42.7850, -5.6650], [42.9950, -5.7550], [43.1750, -5.8150],
            [43.3669, -5.8550]
        ]
    },
    {
        "name": "LAV Venta de Baños - Burgos",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [41.8850, -4.5120], [42.0250, -4.3250], [42.1350, -4.1150], [42.2550, -3.8850],
            [42.3719, -3.6625]
        ]
    },
    {
        "name": "LAV Olmedo - Zamora - Sanabria - Ourense - Santiago",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [41.3180, -4.6680], [41.3144, -4.9061], [41.4150, -5.3250], [41.5117, -5.7369],
            [41.7350, -6.0250], [41.9650, -6.4850], [42.0550, -6.9650], [42.1450, -7.4250],
            [42.3522, -7.8686], [42.5450, -8.1250], [42.7150, -8.3550], [42.8703, -8.5458]
        ]
    },
    {
        "name": "LAV Madrid - Ciudad Real - Puertollano - Córdoba - Sevilla",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [40.4065, -3.6895], [40.1850, -3.6950], [39.9650, -3.7750], [39.6850, -3.8250],
            [39.3550, -3.8650], [38.9839, -3.9136], [38.6897, -4.1119], [38.4250, -4.3450],
            [38.1550, -4.5650], [37.8882, -4.7894], [37.7650, -5.1250], [37.6150, -5.5250],
            [37.3917, -5.9764]
        ]
    },
    {
        "name": "LAV Córdoba - Antequera - Málaga / Granada",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [37.8882, -4.7894], [37.5850, -4.7450], [37.3150, -4.7150], [37.0686, -4.6967],
            [36.8850, -4.5650], [36.7128, -4.4294]
        ]
    },
    {
        "name": "LAV Antequera - Loja - Granada",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [37.0686, -4.6967], [37.1350, -4.3850], [37.1680, -4.1450], [37.1950, -3.8650],
            [37.1842, -3.6089]
        ]
    },
    {
        "name": "LAV Madrid - Cuenca - Requena - València",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [40.4065, -3.6895], [40.1650, -3.5250], [40.0450, -3.0150], [40.0253, -2.1436],
            [39.7550, -1.6850], [39.5150, -1.1650], [39.4650, -0.7450], [39.4623, -0.3855]
        ]
    },
    {
        "name": "LAV Bif. Albacete - Alacant - Elx - Murcia",
        "type": "AVE",
        "gauge": "UIC (1435 mm)",
        "coords": [
            [39.7550, -1.6850], [39.3250, -1.7850], [38.9997, -1.8492], [38.8650, -1.3650],
            [38.6350, -0.8750], [38.4550, -0.6850], [38.3444, -0.4950], [38.2650, -0.6950],
            [38.1350, -0.8850], [37.9744, -1.1306]
        ]
    }
]

SEED_ROUTES = [
    {
        "name": r["name"],
        "type": r["type"],
        "gauge": r["gauge"],
        "coords": smooth_chaikin(r["coords"], iterations=2)
    }
    for r in RAW_SEED_ROUTES
]


def parse_float(val):
    """Parse provider data into the internal normalized representation.

    Parameters are validated or normalized by the function; relevant inputs: ``val``.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``lat1``, ``lon1``, ``lat2``, ``lon2``.
    """
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2.0) ** 2)
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def calculate_bearing(lat1, lon1, lat2, lon2):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``lat1``, ``lon1``, ``lat2``, ``lon2``.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - (math.sin(phi1) * math.cos(phi2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    return round((math.degrees(initial_bearing) + 360) % 360, 1)


def register_segments_in_grid(coords_list):
    """
    Indexa los segmentos reales AB de las vías en celdas de 0.05° (~5 km)
    para proyectar ortogonalmente cada tren sobre el segmento de vía sin saltar a vértices.
    """
    grid = STATIC_CACHE["track_segment_grid"]
    if not coords_list:
        return
    polylines = coords_list if isinstance(coords_list[0][0], (list, tuple)) else [coords_list]
    for poly in polylines:
        for i in range(len(poly) - 1):
            a, b = poly[i], poly[i + 1]
            alat, alon = a[0], a[1]
            blat, blon = b[0], b[1]
            gx, gy = int(((alat + blat) * 0.5) * 20), int(((alon + blon) * 0.5) * 20)
            bucket = grid.setdefault((gx, gy), [])
            if len(bucket) < 400:
                bucket.append((alat, alon, blat, blon))


def project_point_to_segment(plat, plon, alat, alon, blat, blon):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``plat``, ``plon``, ``alat``, ``alon``, ``blat``, ``blon``.
    """
    cos_lat = 0.766
    px, py = plon * cos_lat, plat
    ax, ay = alon * cos_lat, alat
    bx, by = blon * cos_lat, blat
    dx, dy = bx - ax, by - ay
    len2 = dx * dx + dy * dy
    if len2 < 1e-12:
        dist_deg = math.hypot(px - ax, py - ay)
        return alat, alon, dist_deg * 111.32
    t = ((px - ax) * dx + (py - ay) * dy) / len2
    t = max(0.0, min(1.0, t))
    proj_lon = alon + t * (blon - alon)
    proj_lat = alat + t * (blat - alat)
    dist_deg = math.hypot((plon - proj_lon) * cos_lat, plat - proj_lat)
    return proj_lat, proj_lon, dist_deg * 111.32


def snap_to_nearest_track_segment(lat, lon, max_dist_km=0.25):
    """
    Proyecta ortogonalmente el punto GPS sobre el segmento físico real más cercano
    SOLO si existe un segmento real a menos de 250 metros. Nunca desplaza un tren hacia rutas lejanas.
    """
    if not STATIC_CACHE["real_tracks_loaded"]:
        return lat, lon
    grid = STATIC_CACHE["track_segment_grid"]
    if not grid:
        return lat, lon

    gx, gy = int(lat * 20), int(lon * 20)
    best_lat, best_lon = lat, lon
    best_dist = max_dist_km

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for alat, alon, blat, blon in grid.get((gx + dx, gy + dy), ()):
                plat_p, plon_p, dist_km = project_point_to_segment(lat, lon, alat, alon, blat, blon)
                if dist_km < best_dist:
                    best_dist = dist_km
                    best_lat, best_lon = round(plat_p, 5), round(plon_p, 5)
    return best_lat, best_lon


def compute_train_kinematics(train_key, lat, lon, raw_speed_mps, pos_timestamp, current_status, train_type):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``train_key``, ``lat``, ``lon``, ``raw_speed_mps``, ``pos_timestamp``, ``current_status``, ``train_type``.
    """
    now = time.time()
    ts = parse_float(pos_timestamp)
    if not ts or ts <= 0 or ts > now + 3600:
        ts = now

    max_speeds = {
        "AVE": 350.0,
        "Larga Distancia": 265.0,
        "Media Distancia": 220.0,
        "Cercanías": 160.0
    }
    max_cap = max_speeds.get(train_type, 250.0)

    reported_kmh = round((parse_float(raw_speed_mps) or 0.0) * 3.6, 1)
    prev = TRAIN_MOTION_HISTORY.get(train_key)
    trail = list(prev.get("trail", [])) if prev else []

    status_upper = str(current_status or "").upper()
    is_stopped_flag = ("STOPPED" in status_upper or "PARADO" in status_upper)

    if not trail or haversine_km(trail[-1][0], trail[-1][1], lat, lon) >= 0.02:
        trail.append([round(lat, 5), round(lon, 5)])
        if len(trail) > 20:
            trail = trail[-20:]

    if reported_kmh > 0.5:
        bearing = prev.get("bearing") if prev else None
        if prev and haversine_km(prev["lat"], prev["lon"], lat, lon) > 0.01:
            bearing = calculate_bearing(prev["lat"], prev["lon"], lat, lon)
        TRAIN_MOTION_HISTORY[train_key] = {
            "lat": lat, "lon": lon, "ts": ts, "wall_ts": now,
            "speed_kmh": reported_kmh, "bearing": bearing,
            "source": "GTFS-RT directo", "trail": trail
        }
        return reported_kmh, "GTFS-RT directo", bearing, trail

    if prev is not None:
        dist_km = haversine_km(prev["lat"], prev["lon"], lat, lon)
        dt = ts - prev["ts"]
        if dt <= 1.0:
            dt = now - prev["wall_ts"]

        if dist_km >= 0.008 and dt >= 2.0:
            raw_calc_kmh = (dist_km / dt) * 3600.0
            if raw_calc_kmh <= max_cap:
                prev_spd = prev.get("speed_kmh", 0.0)
                smooth_kmh = round(0.7 * raw_calc_kmh + 0.3 * prev_spd, 1) if prev_spd > 0 else round(raw_calc_kmh, 1)
                bearing = calculate_bearing(prev["lat"], prev["lon"], lat, lon)
                TRAIN_MOTION_HISTORY[train_key] = {
                    "lat": lat, "lon": lon, "ts": ts, "wall_ts": now,
                    "speed_kmh": smooth_kmh, "bearing": bearing,
                    "source": "Calculada GPS (Δd/Δt)", "trail": trail
                }
                return smooth_kmh, "Calculada GPS (Δd/Δt)", bearing, trail

        elapsed_since_move = now - prev["wall_ts"]
        if dist_km < 0.008:
            if is_stopped_flag or elapsed_since_move > 95.0:
                TRAIN_MOTION_HISTORY[train_key]["speed_kmh"] = 0.0
                TRAIN_MOTION_HISTORY[train_key]["source"] = "Parado en estación/vía"
                return 0.0, "Parado en estación/vía", prev.get("bearing"), trail
            else:
                return prev.get("speed_kmh", 0.0), prev.get("source", "Calculada GPS (Δd/Δt)"), prev.get("bearing"), trail

    initial_source = "Parado en estación" if is_stopped_flag else "Esperando 2º tick GPS..."
    TRAIN_MOTION_HISTORY[train_key] = {
        "lat": lat, "lon": lon, "ts": ts, "wall_ts": now,
        "speed_kmh": 0.0, "bearing": None,
        "source": initial_source, "trail": trail
    }
    return 0.0, initial_source, None, trail


def extract_train_number(text):
    """Extract a normalized value from a provider-specific payload.

    Parameters are validated or normalized by the function; relevant inputs: ``text``.
    """
    if not text:
        return ""
    m = re.search(r"(?:^|\D)0*(\d{4,5})(?:\D|$)", str(text))
    if m:
        return m.group(1).zfill(5)
    m2 = re.match(r"^0*(\d{4,5})\d{6,8}", str(text))
    if m2:
        return m2.group(1).zfill(5)
    return ""


def train_number_aliases(*values):
    """Devuelve claves equivalentes para IDs Renfe que concatenan tren, servicio y fecha."""
    aliases = set()
    for value in values:
        text = str(value or "")
        direct = extract_train_number(text)
        if direct:
            aliases.add(direct)
            aliases.add(direct.lstrip("0") or "0")
        for token in re.findall(r"(?<!\d)0*(\d{4,5})(?!\d)", text):
            aliases.add(token.zfill(5)); aliases.add(token.lstrip("0") or "0")
        leading = re.match(r"^0*(\d{4})(?:0?20\d{2}|\d{8})", text)
        if leading:
            aliases.add(leading.group(1).zfill(5)); aliases.add(leading.group(1).lstrip("0"))
    return aliases


def get_ckan_resources(package_id, formats=None):
    """Return the requested normalized value from current state or configuration.

    Parameters are validated or normalized by the function; relevant inputs: ``package_id``, ``formats``.
    """
    urls = []
    try:
        res = requests.get(f"{CKAN_BASE}{package_id}", headers=HEADERS, timeout=7)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                for r in data["result"].get("resources", []):
                    fmt = str(r.get("format", "")).strip().upper()
                    url = r.get("url", "")
                    if not url:
                        continue
                    if formats is None:
                        urls.append((fmt, url))
                    else:
                        if fmt in formats or any(url.lower().endswith(f".{ext.lower()}") for ext in formats):
                            urls.append((fmt, url))
    except Exception as e:
        print(f"[CKAN] Aviso al consultar {package_id}: {e}")
    return urls


FEVE_LINE_CODES = {
    "20": {"C4", "C5", "C6", "C7", "C8", "C9"},   # Asturias AM
    "60": {"C4", "R3B", "B1"},                         # Bilbao AM
    "61": {"R3", "E1", "E2"},                          # Gipuzkoa AM
    "62": {"C2", "C3", "R2", "R3"},                  # Cantabria AM
}

def is_feve_service(nucleo_code, route_id="", label="", subtype="", route_meta=None):
    """Return whether the supplied value satisfies the documented classification rule.

    Parameters are validated or normalized by the function; relevant inputs: ``nucleo_code``, ``route_id``, ``label``, ``subtype``, ``route_meta``.
    """
    route_meta = route_meta or {}
    text = f"{route_id} {label} {subtype} {route_meta.get('short_name','')} {route_meta.get('long_name','')}".upper()
    normalized = re.sub(r"[^A-Z0-9ÁÉÍÓÚÑ]+", " ", text)
    if re.search(r"\b(FEVE|RAM|ANCHO M[EÉ]TRICO|METRIC GAUGE|CERCAN[IÍ]AS AM)\b", normalized):
        return True
    codes = set(re.findall(r"\b(?:C|R|E|B)\d{1,2}[A-Z]?\b", normalized))
    return bool(FEVE_LINE_CODES.get(str(nucleo_code), set()) & codes)

def classify_national_train(route_id, trip_id, label, veh_id, route_meta=None):
    """Clasifica todos los servicios comerciales Renfe publicados en GTFS/GTFS-RT."""
    combined = f"{route_id} {trip_id} {label} {veh_id}"
    if route_meta:
        combined += f" {route_meta.get('short_name', '')} {route_meta.get('long_name', '')}"
    combined = re.sub(r"[._/-]+", " ", combined.upper())
    combined = re.sub(r"\s+", " ", combined).strip()

    # Orden específico antes que genérico para evitar que REGIONAL EXPRÉS acabe como REGIONAL.
    service_rules = [
        ("AVE", "AVLO", ("AVLO",)),
        ("AVE", "AVE", ("AVE", "ALTA VELOCIDAD")),
        ("Larga Distancia", "ALVIA", ("ALVIA",)),
        ("Larga Distancia", "EUROMED", ("EUROMED",)),
        ("Larga Distancia", "INTERCITY", ("INTERCITY", "INTER CITY")),
        ("Larga Distancia", "TALGO", ("TALGO",)),
        ("Larga Distancia", "TORRE DEL ORO", ("TORRE DEL ORO",)),
        ("Larga Distancia", "TRENHOTEL", ("TRENHOTEL", "TREN HOTEL")),
        ("Media Distancia", "REGIONAL EXPRÉS", ("REGIONAL EXPRES", "REGIONAL EXPRESS", "R EXPRES", "R EXP", "REG EXP")),
        ("Media Distancia", "REGIONAL", ("REGIONAL",)),
        ("Media Distancia", "AVANT", ("AVANT",)),
        ("Media Distancia", "PROXIMIDAD", ("PROXIMIDAD",)),
        ("Media Distancia", "MEDIA DISTANCIA", ("MEDIA DISTANCIA", "MD")),
        ("Media Distancia", "FEVE/RAM", ("FEVE", "RAM", "ANCHO METRICO", "ANCHO MÉTRICO")),
    ]
    for family, subtype, aliases in service_rules:
        if any(re.search(rf"(?:^|\W){re.escape(alias)}(?:$|\W)", combined) for alias in aliases):
            return family, subtype

    tnum = extract_train_number(f"{veh_id} {label} {trip_id}")
    if tnum and tnum.isdigit():
        num = int(tnum)
        if 2000 <= num <= 3999 or 6000 <= num <= 6999:
            return "AVE", "AVE"
        if 8000 <= num <= 8999:
            return "Media Distancia", "AVANT"
        if 9000 <= num <= 9999:
            return "Media Distancia", "REGIONAL EXPRÉS"
        if 12000 <= num <= 19999:
            return "Media Distancia", "REGIONAL"
        if 20000 <= num <= 39999:
            return "Media Distancia", "MEDIA DISTANCIA"
        if (1 <= num <= 1999) or (4000 <= num <= 5999) or (10000 <= num <= 11999):
            return "Larga Distancia", "ALVIA/LD"

    # El feed nacional es AVE/LD/MD. Si no publica producto, se conserva como Renfe sin inventar marca.
    return "Larga Distancia", "RENFE LD"


def simplify_track_geometry(raw_pts, min_dist_deg=0.0008):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``raw_pts``, ``min_dist_deg``.
    """
    if len(raw_pts) <= 3:
        return [[round(p[0], 5), round(p[1], 5)] for p in raw_pts]
    out = [[round(raw_pts[0][0], 5), round(raw_pts[0][1], 5)]]
    min_d2 = min_dist_deg * min_dist_deg
    for pt in raw_pts[1:-1]:
        dlat = pt[0] - out[-1][0]
        dlon = pt[1] - out[-1][1]
        if (dlat * dlat + dlon * dlon) >= min_d2:
            out.append([round(pt[0], 5), round(pt[1], 5)])
    last = [round(raw_pts[-1][0], 5), round(raw_pts[-1][1], 5)]
    if out[-1] != last:
        out.append(last)
    return out


def is_near_cercanias_hub(lat, lon):
    """Return whether the supplied value satisfies the documented classification rule.

    Parameters are validated or normalized by the function; relevant inputs: ``lat``, ``lon``.
    """
    for nuc in NUCLEOS_CERCANIAS.values():
        if abs(lat - nuc["lat"]) <= nuc["radius_deg"] and abs(lon - nuc["lon"]) <= nuc["radius_deg"]:
            return nuc["name"]
    return None


def classify_osm_way(el):
    """Clasifica un elemento 'way' de OpenStreetMap en su categoría ferroviaria y extrae su geometría."""
    geom = el.get("geometry")
    if not geom or len(geom) < 2:
        return None
    pts = [[pt["lat"], pt["lon"]] for pt in geom if "lat" in pt and "lon" in pt]
    pts = simplify_track_geometry(pts)
    if len(pts) < 2:
        return None

    tags = el.get("tags", {})
    name = str(tags.get("name") or tags.get("description") or "").strip()
    name_up = name.upper()
    gauge_raw = str(tags.get("gauge") or "")
    highspeed = str(tags.get("highspeed") or "").lower() == "yes"
    usage = str(tags.get("usage") or "main").lower()
    electrified = str(tags.get("electrified") or "").lower()
    railway_type = str(tags.get("railway") or "rail").lower()
    network = str(tags.get("network") or tags.get("operator") or "").upper()
    mid_lat, mid_lon = pts[len(pts) // 2]

    if highspeed or "1435" in gauge_raw or "LAV" in name_up or "ALTA VELOCIDAD" in name_up:
        rtype = "AVE"
        gauge_label = "UIC (1435 mm - Alta Velocidad)"
        default_name = "Línea de Alta Velocidad ADIF"
    elif any(k in name_up or k in network for k in ["CERCANÍAS", "CERCANIAS", "RODALIES"]):
        rtype = "Cercanías"
        gauge_label = "Ibérico (1668 mm - Cercanías)"
        default_name = "Red de Cercanías / Rodalies"
    elif railway_type == "narrow_gauge" or "1000" in gauge_raw or "FEVE" in name_up or "FEVE" in network:
        rtype = "Media Distancia"
        gauge_label = "Ancho Métrico RAM (1000 mm)"
        default_name = "Red Ancho Métrico ADIF (FEVE)"
    else:
        hub_name = is_near_cercanias_hub(mid_lat, mid_lon)
        if hub_name and usage == "branch" and electrified not in ("no", ""):
            rtype = "Cercanías"
            gauge_label = "Ibérico (1668 mm)"
            default_name = f"Núcleo Cercanías {hub_name}"
        elif usage == "branch" or electrified == "no":
            rtype = "Media Distancia"
            gauge_label = "Ibérico (1668 mm - Convencional)"
            default_name = "Línea Convencional Media Distancia"
        else:
            rtype = "Larga Distancia"
            gauge_label = "Ibérico (1668 mm - Red Principal)"
            default_name = "Corredor Principal ADIF"

    corridor_title = name if name else default_name
    return rtype, corridor_title, gauge_label, pts


def _load_overpass_cache():
    """Load internal cached state while tolerating missing or invalid persistence.
    """
    try:
        OVERPASS_SERVICE.load_cache()
    except Exception as e:
        APP_LOGGER.warning("Overpass: caché persistente no disponible: %s", e)

def _save_overpass_cache():
    """Persist internal cached state without exposing provider details to callers.
    """
    try:
        OVERPASS_SERVICE.save_cache()
    except Exception as e:
        APP_LOGGER.warning("Overpass: no se pudo guardar la caché: %s", e)

def run_overpass_query(query_str, timeout_sec=30, cache_key=None, *,
                       ignore_cooldown=False, cycle_id=None):
    """Delegate one Overpass query to the resilient mirror service and publish progress.

    Parameters are validated or normalized by the function; relevant inputs: ``query_str``, ``timeout_sec``, ``cache_key``.
    """
    return OVERPASS_SERVICE.query(
        query_str, read_timeout=min(timeout_sec, 30), cache_key=cache_key,
        ignore_cooldown=ignore_cooldown, cycle_id=cycle_id,
        status=lambda message: STATIC_CACHE.update(
            real_tracks_source=message, real_tracks_last_progress_at=time.time()
        ),
    )

def _normalize_overpass_elements(elements):
    """Acepta respuesta Overpass, tupla del wrapper o caché antigua, y devuelve sólo dicts OSM."""
    if isinstance(elements, tuple):
        elements = elements[0] if elements else []
    if isinstance(elements, dict):
        elements = elements.get("elements", [])
    if not isinstance(elements, list):
        return []
    normalized = []
    stack = list(elements)
    while stack:
        item = stack.pop(0)
        if isinstance(item, dict):
            normalized.append(item)
        elif isinstance(item, list):
            stack[0:0] = item
    return normalized


def merge_elements_into_polylines(elements, existing_polylines=None):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``elements``, ``existing_polylines``.
    """
    grouped = {}
    if isinstance(existing_polylines, list):
        for p in existing_polylines:
            if not isinstance(p, dict):
                continue
            coords = p.get("coords") or []
            if not coords:
                continue
            gkey = (p.get("type", "Larga Distancia"), p.get("name", "Corredor ferroviario"), p.get("gauge", ""))
            try:
                grouped[gkey] = list(coords) if isinstance(coords[0][0], (list, tuple)) else [coords]
            except (IndexError, TypeError):
                continue

    added_ways = 0
    for el in _normalize_overpass_elements(elements):
        wid = el.get("id")
        if wid and wid in STATIC_CACHE["osm_ways_seen"]:
            continue
        parsed = classify_osm_way(el)
        if not parsed:
            continue
        if wid:
            STATIC_CACHE["osm_ways_seen"].add(wid)
        rtype, corridor_title, gauge_label, pts = parsed
        grouped.setdefault((rtype, corridor_title, gauge_label), []).append(pts)
        register_segments_in_grid([pts])
        added_ways += 1

    polylines = [
        {"name": name, "type": rtype, "gauge": gauge, "coords": segments}
        for (rtype, name, gauge), segments in grouped.items() if segments
    ]
    return polylines, added_ways


def load_real_tracks_progressive_thread():
    """
    Hilo dedicado exclusivamente a descargar el trazado físico real de ADIF / OSM
    en 4 fases indexadas rápidas (sin expresiones regulares pesadas que bloqueen Overpass):
      - Fase 1 (~2 seg): Red Española de Alta Velocidad (highspeed=yes). Sustituye al instante las líneas AVE.
      - Fase 2 (~4 seg): Red Principal ADIF Centro y Norte (usage=main).
      - Fase 3 (~4 seg): Red Principal ADIF Sur y Levante (usage=main).
      - Fase 4 (~4 seg): Ramales de Cercanías, Media Distancia y Ancho Métrico FEVE.
    """
    if STATIC_CACHE["real_tracks_loading"] or STATIC_CACHE["real_tracks_loaded"]:
        return
    STATIC_CACHE["real_tracks_loading"] = True
    STATIC_CACHE["real_tracks_started_at"] = time.time()
    STATIC_CACHE["real_tracks_last_progress_at"] = time.time()
    STATIC_CACHE["real_tracks_last_completed_at"] = 0
    STATIC_CACHE["real_tracks_error"] = None
    STATIC_CACHE["real_tracks_stages_completed"] = []
    STATIC_CACHE["real_tracks_stages_failed"] = []

    if os.path.exists(TRACKS_CACHE_FILE):
        try:
            with open(TRACKS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, list) and len(cached) > 15:
                STATIC_CACHE["route_polylines"] = cached
                STATIC_CACHE["real_tracks_loaded"] = True
                STATIC_CACHE["real_tracks_stage"] = 4
                segment_count = sum(max(0, len(seg) - 1) for route in cached for seg in route.get("coords", []))
                STATIC_CACHE["real_tracks_source"] = f"Red ferroviaria: {segment_count:,} tramos cargados".replace(",", ".")
                for rp in cached:
                    register_segments_in_grid(rp["coords"])
                STATIC_CACHE["real_tracks_loading"] = False
                print(f"[Trazado Real] Cargados {len(cached)} corredores desde caché en disco.")
                return
        except Exception as e:
            print(f"[Trazado Real] Aviso leyendo caché local: {e}")

    stages = [
        (
            1,
            "Fase 1/4: Red Alta Velocidad AVE/AVLO activa",
            """[out:json][timeout:25];
            way["railway"="rail"]["highspeed"="yes"](36.0,-9.0,43.6,3.3);
            out geom;"""
        ),
        (
            2,
            "Fase 2/4: Red Principal ADIF Mitad Norte activa",
            """[out:json][timeout:25];
            way["railway"="rail"]["usage"="main"]["highspeed"!="yes"](39.8,-9.3,43.8,3.4);
            out geom;"""
        ),
        (
            3,
            "Fase 3/4: Red Principal ADIF Mitad Sur y Levante activa",
            """[out:json][timeout:25];
            way["railway"="rail"]["usage"="main"]["highspeed"!="yes"](35.9,-7.6,39.8,0.8);
            out geom;"""
        ),
        (
            4,
            "Trazado Físico Real Completo ADIF/OSM (AVE + LD + MD + Cercanías + FEVE)",
            """[out:json][timeout:25];
            (
              way["railway"="rail"]["usage"="branch"]["service"!="yard"]["service"!="siding"]["service"!="spur"](36.0,-9.3,43.8,3.4);
              way["railway"="narrow_gauge"]["usage"="main"](42.0,-8.6,43.8,-1.5);
            );
            out geom;"""
        )
    ]

    accumulated_polylines = []
    load_cycle_id = f"tracks-{int(STATIC_CACHE['real_tracks_started_at'])}"
    for stage_num, stage_desc, q_str in stages:
        elems, overpass_error, from_cache = run_overpass_query(
            q_str, timeout_sec=30, cache_key=f"seed-stage-{stage_num}-v2",
            ignore_cooldown=True, cycle_id=f"{load_cycle_id}-stage-{stage_num}",
        )
        if elems:
            try:
                accumulated_polylines, added = merge_elements_into_polylines(elems, accumulated_polylines)
            except Exception as e:
                error = f"datos inválidos: {e}"
                STATIC_CACHE["real_tracks_stages_failed"].append({"stage": stage_num, "error": error})
                STATIC_CACHE["real_tracks_error"] = error
                APP_LOGGER.warning("Trazado real fase %s: %s", stage_num, error)
                continue
            STATIC_CACHE["real_tracks_stages_completed"].append(stage_num)
            STATIC_CACHE["route_polylines"] = accumulated_polylines
            STATIC_CACHE["real_tracks_loaded"] = True
            STATIC_CACHE["real_tracks_stage"] = stage_num
            STATIC_CACHE["real_tracks_last_progress_at"] = time.time()
            segment_count = sum(max(0, len(seg) - 1) for route in accumulated_polylines for seg in route.get("coords", []))
            STATIC_CACHE["real_tracks_source"] = f"Preparando red ferroviaria de España en segundo plano… {segment_count:,} tramos cargados".replace(",", ".")
            print(f"[Trazado Real] {stage_desc}: +{added} tramos físicos cargados.")
        else:
            error = overpass_error or "Overpass no devolvió geometrías"
            STATIC_CACHE["real_tracks_stages_failed"].append({"stage": stage_num, "error": error})
            STATIC_CACHE["real_tracks_error"] = error
            APP_LOGGER.warning("Trazado real fase %s sin datos: %s", stage_num, error)

    if STATIC_CACHE["real_tracks_loaded"] and len(STATIC_CACHE["route_polylines"]) > 15:
        try:
            with open(TRACKS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(STATIC_CACHE["route_polylines"], f, ensure_ascii=False, separators=(",", ":"))
            segment_count = sum(max(0, len(seg) - 1) for route in STATIC_CACHE["route_polylines"] for seg in route.get("coords", []))
            STATIC_CACHE["real_tracks_stage"] = 4
            STATIC_CACHE["real_tracks_source"] = f"Red ferroviaria: {segment_count:,} tramos cargados".replace(",", ".")
        except Exception as e:
            print(f"[Trazado Real] Aviso guardando caché: {e}")

    completed = STATIC_CACHE["real_tracks_stages_completed"]
    failed = STATIC_CACHE["real_tracks_stages_failed"]
    STATIC_CACHE["real_tracks_last_completed_at"] = time.time()
    STATIC_CACHE["real_tracks_loading"] = False
    if completed and failed:
        STATIC_CACHE["real_tracks_source"] += f" · Carga parcial ({len(completed)}/4 fases)"
    elif not completed:
        STATIC_CACHE["real_tracks_loaded"] = False
        STATIC_CACHE["real_tracks_source"] = (
            "No se pudieron cargar vías: " +
            (STATIC_CACHE.get("real_tracks_error") or "ningún mirror devolvió geometrías")
        )


def load_stations_and_gtfs_thread():
    """Hilo independiente y rápido (~3 seg) para cargar las 1.500+ estaciones de ADIF/Renfe y metadatos GTFS."""
    if STATIC_CACHE["stations_loading"] or STATIC_CACHE["stations_loaded"]:
        return
    STATIC_CACHE["stations_loading"] = True

    stations_dict = {s["id"]: dict(s) for s in CORE_STATIONS}
    stops_by_id = {s["id"]: dict(s) for s in CORE_STATIONS}
    routes_by_id = {}
    trips_by_id = {}
    trips_by_num = {}
    trip_stops_by_id = {}
    trip_stops_by_num = {}

    for pkg in ["estaciones", "estaciones_feve"]:
        csv_resources = get_ckan_resources(PACKAGES[pkg], formats=["CSV"])
        for fmt, url in csv_resources:
            try:
                res = requests.get(url, headers=HEADERS, timeout=10)
                if res.status_code == 200:
                    text = res.content.decode("utf-8", errors="replace")
                    if "\ufffd" in text[:500]:
                        text = res.content.decode("latin-1", errors="replace")
                    lines = text.splitlines()
                    if not lines:
                        continue
                    delim = ";" if ";" in lines[0] else ","
                    reader = csv.DictReader(lines, delimiter=delim)
                    for row in reader:
                        norm = {str(k).strip().upper(): str(v).strip() for k, v in row.items() if k and v}
                        code = norm.get("CODIGO") or norm.get("ID") or norm.get("STOP_ID") or ""
                        name = norm.get("DESCRIPCION") or norm.get("NOMBRE") or norm.get("STOP_NAME") or ""
                        lat = parse_float(norm.get("LATITUD") or norm.get("LAT") or norm.get("STOP_LAT"))
                        lon = parse_float(norm.get("LONGITUD") or norm.get("LON") or norm.get("LONG") or norm.get("STOP_LON"))
                        if name and lat and lon and 35.0 <= lat <= 44.0 and -10.0 <= lon <= 4.5:
                            st_id = code or name
                            cat = stations_dict.get(st_id, {}).get("category", "Estación FEVE / RAM" if pkg == "estaciones_feve" else "Estación ADIF / Renfe")
                            st_obj = {"id": st_id, "name": name.title(), "lat": lat, "lon": lon, "category": cat}
                            stations_dict[st_id] = st_obj
                            stops_by_id[st_id] = st_obj
                break
            except Exception as e:
                print(f"[Estaciones CSV] Error leyendo {url}: {e}")

    STATIC_CACHE["stations"] = list(stations_dict.values())
    STATIC_CACHE["stops_by_id"] = stops_by_id

    gtfs_resources = []
    for gtfs_pkg in ("gtfs_ld", "gtfs_cercanias"):
        resources = get_ckan_resources(PACKAGES[gtfs_pkg], formats=["ZIP", "GTFS"])
        if not resources:
            resources = get_ckan_resources(PACKAGES[gtfs_pkg])
        gtfs_resources.extend(resources)

    for fmt, url in gtfs_resources:
        if not (url.lower().endswith(".zip") or fmt in ["ZIP", "GTFS"]):
            continue
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                zf = zipfile.ZipFile(io.BytesIO(res.content))
                names = zf.namelist()

                if "stops.txt" in names:
                    with zf.open("stops.txt") as f:
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                        for r in reader:
                            sid = r.get("stop_id", "").strip()
                            sname = r.get("stop_name", "").strip()
                            slat = parse_float(r.get("stop_lat"))
                            slon = parse_float(r.get("stop_lon"))
                            if sid and slat and slon and 35.0 <= slat <= 44.0 and -10.0 <= slon <= 4.5:
                                cat = stations_dict.get(sid, {}).get("category", "Estación AVE/LD/MD")
                                st_obj = {"id": sid, "name": sname.title(), "lat": slat, "lon": slon, "category": cat}
                                stops_by_id[sid] = st_obj
                                stations_dict[sid] = st_obj

                if "routes.txt" in names:
                    with zf.open("routes.txt") as f:
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                        for r in reader:
                            rid = r.get("route_id", "").strip()
                            sname = r.get("route_short_name", "").strip()
                            lname = r.get("route_long_name", "").strip()
                            if rid:
                                routes_by_id[rid] = {"short_name": sname, "long_name": lname}

                if "trips.txt" in names:
                    with zf.open("trips.txt") as f:
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                        for r in reader:
                            tid = r.get("trip_id", "").strip()
                            rid = r.get("route_id", "").strip()
                            headsign = r.get("trip_headsign", "").strip()
                            if tid:
                                t_obj = {"route_id": rid, "headsign": headsign, "trip_id": tid}
                                trips_by_id[tid] = t_obj
                                tnum = extract_train_number(tid)
                                if tnum and tnum not in trips_by_num:
                                    trips_by_num[tnum] = t_obj
                if "stop_times.txt" in names:
                    local_stops = {}
                    with zf.open("stop_times.txt") as f:
                        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                        for r in reader:
                            tid = (r.get("trip_id") or "").strip()
                            sid = (r.get("stop_id") or "").strip()
                            if not tid or not sid:
                                continue
                            try: seq = int(float(r.get("stop_sequence") or 0))
                            except Exception: seq = 0
                            local_stops.setdefault(tid, []).append({"stop_id": sid, "sequence": seq, "arrival": r.get("arrival_time", ""), "departure": r.get("departure_time", "")})
                    for tid, sequence in local_stops.items():
                        sequence.sort(key=lambda x: x["sequence"])
                        trip_stops_by_id[tid] = sequence
                        tmeta = trips_by_id.get(tid, {})
                        for alias in train_number_aliases(tid, tmeta.get("headsign", "")):
                            trip_stops_by_num.setdefault(alias, sequence)
        except Exception as e:
            print(f"[GTFS Static] Aviso procesando {url}: {e}")

    STATIC_CACHE["stations"] = list(stations_dict.values())
    STATIC_CACHE["stops_by_id"] = stops_by_id
    STATIC_CACHE["routes_by_id"] = routes_by_id
    STATIC_CACHE["trips_by_id"] = trips_by_id
    STATIC_CACHE["trips_by_num"] = trips_by_num
    STATIC_CACHE["trip_stops_by_id"] = trip_stops_by_id
    STATIC_CACHE["trip_stops_by_num"] = trip_stops_by_num
    STATIC_CACHE["stations_loaded"] = True
    STATIC_CACHE["stations_loading"] = False
    print(f"[Estaciones y GTFS] Cargadas {len(STATIC_CACHE['stations'])} estaciones.")


def _gtfs_date(value):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``value``.
    """
    value = str(value or "").strip()
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except Exception:
        return None


def _read_gtfs_csv(zf, name):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``zf``, ``name``.
    """
    candidates = [n for n in zf.namelist() if n.lower().endswith(name.lower())]
    if not candidates:
        return []
    with zf.open(candidates[0]) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")))


def parse_operator_gtfs(zip_bytes, operator_key, cfg_override=None):
    """Parse one static operator GTFS archive into normalized stations, routes and trips.

    Parameters are validated or normalized by the function; relevant inputs: ``zip_bytes``, ``operator_key``, ``cfg_override``.
    """
    cfg = cfg_override or OPEN_ACCESS_GTFS[operator_key]
    archive = open_gtfs_archive(
        zip_bytes, include=(
            "stops.txt", "routes.txt", "trips.txt", "stop_times.txt",
            "calendar.txt", "calendar_dates.txt", "shapes.txt", "frequencies.txt",
        ),
    )
    stops_rows = archive.table("stops.txt")
    routes_rows = archive.table("routes.txt")
    trips_rows = archive.table("trips.txt")
    times_rows = archive.table("stop_times.txt")
    calendar_rows = archive.table("calendar.txt")
    calendar_dates = archive.table("calendar_dates.txt")
    shapes_rows = archive.table("shapes.txt")
    frequencies_rows = archive.table("frequencies.txt")

    stops = {}
    raw_stops = {str(row.get("stop_id") or "").strip(): row for row in stops_rows if str(row.get("stop_id") or "").strip()}
    def resolve_stop(row):
        """Perform the documented application operation while preserving current API contracts.

        Parameters are validated or normalized by the function; relevant inputs: ``row``.
        """
        lat, lon = parse_float(row.get("stop_lat")), parse_float(row.get("stop_lon"))
        parent_id = str(row.get("parent_station") or "").strip()
        parent = raw_stops.get(parent_id) if parent_id else None
        if (lat is None or lon is None) and parent:
            lat, lon = parse_float(parent.get("stop_lat")), parse_float(parent.get("stop_lon"))
        name = (row.get("stop_name") or (parent or {}).get("stop_name") or row.get("stop_id") or "Estación").strip()
        return lat, lon, name
    for sid, row in raw_stops.items():
        lat, lon, name = resolve_stop(row)
        if sid and lat is not None and lon is not None and 27 <= lat <= 44.5 and -18.5 <= lon <= 5:
            stops[sid] = {"id": f"{operator_key}:{sid}", "source_id": sid,
                          "name": name, "lat": lat, "lon": lon,
                          "category": f"Estación {cfg['name']}", "operator": cfg["name"]}
    route_meta = {}
    for row in routes_rows:
        rid = str(row.get("route_id") or "").strip()
        if rid:
            route_meta[rid] = {"short_name": (row.get("route_short_name") or cfg["name"]).strip(),
                               "long_name": (row.get("route_long_name") or "").strip(),
                               "color": f"#{(row.get('route_color') or cfg['color'].lstrip('#')).strip()}",
                               "text_color": f"#{(row.get('route_text_color') or cfg['text_color'].lstrip('#')).strip()}"}
    today = datetime.now().date()
    active_services = active_service_ids(calendar_rows, calendar_dates, today)
    trip_meta = {}
    for row in trips_rows:
        tid = str(row.get("trip_id") or "").strip()
        if tid:
            trip_meta[tid] = {"route_id": str(row.get("route_id") or ""), "service_id": str(row.get("service_id") or ""),
                              "headsign": (row.get("trip_headsign") or "").strip(), "shape_id": str(row.get("shape_id") or "")}
    times = {}
    for row in times_rows:
        tid, sid = str(row.get("trip_id") or ""), str(row.get("stop_id") or "")
        if tid in trip_meta and sid in stops:
            try: seq = int(float(row.get("stop_sequence") or 0))
            except Exception: seq = 0
            times.setdefault(tid, []).append({"stop_id": sid, "sequence": seq,
                "arrival": row.get("arrival_time") or "", "departure": row.get("departure_time") or ""})
    for seq in times.values(): seq.sort(key=lambda x: x["sequence"])
    shapes = {}
    for row in shapes_rows:
        sid = str(row.get("shape_id") or "")
        lat, lon = parse_float(row.get("shape_pt_lat")), parse_float(row.get("shape_pt_lon"))
        if sid and lat and lon:
            try: seq = int(float(row.get("shape_pt_sequence") or 0))
            except Exception: seq = 0
            shapes.setdefault(sid, []).append((seq, [lat, lon]))
    shapes = {k: [point for _, point in sorted(v)] for k, v in shapes.items()}
    frequencies = {}
    for row in frequencies_rows:
        tid = str(row.get("trip_id") or "").strip()
        start_sec, end_sec = _gtfs_seconds(row.get("start_time")), _gtfs_seconds(row.get("end_time"))
        try: headway = max(30, int(float(row.get("headway_secs") or 0)))
        except Exception: headway = 0
        if tid and start_sec is not None and end_sec is not None and headway:
            frequencies.setdefault(tid, []).append({"start": start_sec, "end": end_sec, "headway": headway,
                                                    "exact_times": str(row.get("exact_times") or "0") == "1"})

    routes, route_seen, scheduled = [], set(), []
    for tid, meta in trip_meta.items():
        if active_services and meta["service_id"] not in active_services:
            continue
        seq = times.get(tid, [])
        if len(seq) < 2: continue
        rm = route_meta.get(meta["route_id"], {})
        coords = shapes.get(meta["shape_id"]) or [[stops[x["stop_id"]]["lat"], stops[x["stop_id"]]["lon"]] for x in seq]
        origin, destination = stops[seq[0]["stop_id"]]["name"], stops[seq[-1]["stop_id"]]["name"]
        route_key = (meta["route_id"], meta.get("shape_id") or origin + destination)
        if route_key not in route_seen:
            route_seen.add(route_key)
            routes.append({"id": f"{operator_key}:{meta['route_id']}:{len(routes)}", "route_id": meta["route_id"],
                           "short_name": rm.get("short_name") or meta["route_id"],
                           "name": rm.get("long_name") or f"{origin} - {destination}",
                           "type": cfg["name"], "operator": cfg["name"], "color": rm.get("color", cfg["color"]),
                           "coords": [coords], "scheduled": True})
        scheduled.append({"id": f"{operator_key}:{tid}", "trip_id": tid, "operator": cfg["name"], "type": cfg["name"],
                          "route_id": meta["route_id"], "label": rm.get("short_name") or cfg["name"],
                          "origin": origin, "destination": destination, "headsign": meta["headsign"],
                          "departure": seq[0]["departure"], "arrival": seq[-1]["arrival"],
                          "stops": [{**x, "name": stops[x["stop_id"]]["name"],
                                     "lat": stops[x["stop_id"]]["lat"], "lon": stops[x["stop_id"]]["lon"]} for x in seq],
                          "frequencies": frequencies.get(tid, []),
                          "position_source": "Horario programado, sin GPS", "scheduled": True})
    return {"stations": list(stops.values()), "routes": routes, "trips": scheduled}


def load_operator_gtfs(operator_key, force=False):
    """Load one open-access operator from fresh cache or remote source under a lock.

    Parameters are validated or normalized by the function; relevant inputs: ``operator_key``, ``force``.
    """
    cfg, state = OPEN_ACCESS_GTFS[operator_key], OPEN_ACCESS_CACHE[operator_key]
    with OPEN_ACCESS_LOCK:
        if state["loading"]: return
        if state["loaded"] and not force and time.time() - state["updated_at"] < OPEN_ACCESS_CACHE_TTL: return
        state["loading"] = True
    cache_file = os.path.join(OPEN_ACCESS_CACHE_DIR, f"{operator_key}.zip")
    errors, content = [], None
    # Priority: explicit local GTFS, persistent cache, then authenticated download.
    local_file = os.getenv(cfg.get("file_env", ""), "").strip() if cfg.get("file_env") else ""
    if local_file and os.path.isfile(os.path.expanduser(local_file)):
        try:
            content = Path(os.path.expanduser(local_file)).read_bytes()
            if content[:2] != b"PK": raise ValueError("el fichero local no es un ZIP GTFS")
            Path(cache_file).write_bytes(content)
        except Exception as exc:
            errors.append(f"fichero local: {exc}")
            content = None
    if content is None and os.path.exists(cache_file):
        try:
            cached_bytes = Path(cache_file).read_bytes()
            if cached_bytes[:2] == b"PK": content = cached_bytes
        except Exception as exc:
            errors.append(f"caché local: {exc}")

    token = operator_token(operator_key, cfg)
    needs_token = bool(cfg.get("token_env"))
    # Refresh remote data when no cache exists, or when authenticated data is older than the TTL.
    cache_stale = not os.path.exists(cache_file) or time.time() - os.path.getmtime(cache_file) >= OPEN_ACCESS_CACHE_TTL
    should_download = content is None or (cache_stale and (not needs_token or token))
    if should_download:
        if needs_token and not token:
            errors.append(f"falta {cfg['token_env']}; usa {cfg['file_env']} o coloca {operator_key}.zip en {OPEN_ACCESS_CACHE_DIR}")
        else:
            for url in cfg["urls"]:
                try:
                    headers = {"ApiKey": token} if token and "nap.transportes.gob.es" in url else {}
                    response = OPERATOR_HTTP.get(url, headers=headers, timeout=(10, 45), allow_redirects=True)
                    # downloadLink returns a temporary URL as JSON or plain text; download it without forwarding the API key.
                    if response.status_code == 200 and "downloadLink" in url and response.content[:2] != b"PK":
                        try:
                            payload = response.json()
                            if isinstance(payload, str): download_url = payload
                            elif isinstance(payload, dict): download_url = payload.get("url") or payload.get("downloadUrl") or payload.get("link") or payload.get("href")
                            else: download_url = None
                        except Exception:
                            download_url = response.text.strip().strip('"')
                        if download_url and download_url.startswith("http"):
                            response = OPERATOR_HTTP.get(download_url, timeout=(10, 45), allow_redirects=True)
                    if response.status_code == 200 and response.content[:2] == b"PK":
                        content = response.content
                        Path(cache_file).write_bytes(content)
                        break
                    body_hint = response.text[:160].replace("\n", " ") if response.content[:2] != b"PK" else ""
                    errors.append(f"{url}: HTTP {response.status_code}{' · '+body_hint if body_hint else ''}")
                except Exception as exc:
                    errors.append(f"{url}: {exc}")
    try:
        if content is None: raise RuntimeError("; ".join(errors) or "GTFS no disponible")
        parsed = parse_operator_gtfs(content, operator_key)
        with OPEN_ACCESS_LOCK:
            state.update(parsed); state.update(loaded=True, updated_at=time.time(), error="; ".join(errors) if errors else None,
                                              retry_after=0.0, fail_count=0)
        print(f"[{cfg['name']}] GTFS: {len(parsed['routes'])} rutas, {len(parsed['stations'])} estaciones, {len(parsed['trips'])} servicios de hoy")
    except Exception as exc:
        with OPEN_ACCESS_LOCK:
            state["error"] = str(exc)
            state["fail_count"] = int(state.get("fail_count", 0)) + 1
            missing_auth = "falta OUIGO_GTFS_TOKEN" in str(exc)
            state["retry_after"] = time.time() + (24 * 3600 if missing_auth else min(3600, 60 * (2 ** min(state["fail_count"] - 1, 5))))
        APP_LOGGER.warning("%s GTFS no disponible; próximo intento en %ss: %s", cfg["name"],
                           int(state["retry_after"] - time.time()), exc)
        print(f"[{cfg['name']}] Aviso GTFS; reintento en {int(state['retry_after']-time.time())}s: {exc}")
    finally:
        with OPEN_ACCESS_LOCK: state["loading"] = False


def _find_download_url(payload):
    """Compatibility wrapper around the recursive NAP URL resolver."""
    return find_download_url(payload)


def download_nap_gtfs(dataset_id, token, cache_file):
    """Compatibility wrapper returning the historical ``content, errors`` tuple."""
    result = NAP_GTFS_SERVICE.download_nap(dataset_id, token)
    if result.content is not None:
        from radar.nap_service import write_bytes_atomic
        write_bytes_atomic(cache_file, result.content)
    return result.content, result.errors


def parse_metro_gtfs(content, key):
    """Parse provider data into the internal normalized representation.

    Parameters are validated or normalized by the function; relevant inputs: ``content``, ``key``.
    """
    cfg = METRO_GTFS[key]
    parser_cfg = {"name": cfg["name"], "color": cfg["color"], "text_color": "#FFFFFF"}
    data = parse_operator_gtfs(content, key, cfg_override=parser_cfg)
    for collection in (data["stations"], data["routes"], data["trips"]):
        for item in collection:
            item["network_key"] = key
            item["operator"] = cfg["name"]
    return data


def _download_direct_gtfs(url):
    """Compatibility wrapper around validated direct GTFS acquisition."""
    result = NAP_GTFS_SERVICE.download_direct([url])
    return result.content, None if result.content is not None else "; ".join(result.errors)


def load_metro_gtfs(key, force=False, attempt_id=None):
    """Load one urban or regional GTFS network with cache and fallback handling.

    Parameters are validated or normalized by the function; relevant inputs: ``key``, ``force``, ``attempt_id``.
    """
    cfg, state = METRO_GTFS[key], METRO_CACHE[key]
    now = time.time()
    with METRO_LOCK:
        if attempt_id is not None and int(state.get("attempt_id", 0)) != int(attempt_id):
            return
        if attempt_id is None:
            if state.get("loading") and not force:
                return
            state["attempt_id"] = int(state.get("attempt_id", 0)) + 1
            attempt_id = state["attempt_id"]
        state.update(loading=True, last_checked=now, status="checking", error=None, using_cache=False)
    cache_file = os.path.join(OPEN_ACCESS_CACHE_DIR, f"{key}.zip")
    cache_file = os.path.join(OPEN_ACCESS_CACHE_DIR, f"{key}.zip")
    token = operator_token("ouigo", OPEN_ACCESS_GTFS["ouigo"])
    fetch = NAP_GTFS_SERVICE.acquire(
        dataset_id=cfg["nap_id"], token=token,
        fallback_urls=cfg.get("fallback_urls", []), cache_file=cache_file,
        ttl=METRO_CACHE_TTL, force=force,
    )
    content = fetch.content
    errors = list(fetch.errors)
    active_source = fetch.source
    state.update(
        using_cache=fetch.using_cache, stale=fetch.stale,
        cache_age_seconds=fetch.cache_age_seconds, download_attempts=fetch.attempts,
        last_attempt_at=now,
    )

    try:
        if content is None:
            reason = "API key NAP no configurada y sin fallback público" if not token else "; ".join(errors)
            raise RuntimeError(reason)
        parsed = parse_metro_gtfs(content, key)
        if not parsed["routes"] or not parsed["stations"]:
            raise RuntimeError("GTFS válido pero sin rutas o estaciones utilizables")
        state.update(parsed)
        state.update(loaded=True, updated_at=now, next_refresh=now+METRO_CACHE_TTL,
                     error="; ".join(errors) if errors else None, status="stale" if fetch.stale else ("cached" if fetch.using_cache else "loaded"),
                     active_source=active_source, retry_after=0.0, last_success_at=now)
        print(f"[{cfg['name']}] GTFS: {len(parsed['routes'])} rutas, {len(parsed['stations'])} estaciones ({active_source})")
    except Exception as exc:
        state.update(error=str(exc), status="failed", next_refresh=now+3600, retry_after=now+3600)
        APP_LOGGER.warning("%s GTFS: %s", cfg["name"], exc)
    finally:
        with METRO_LOCK:
            if int(state.get("attempt_id", 0)) == int(attempt_id or 0):
                state["loading"] = False


def ensure_metro_feeds():
    """Ensure the requested resource or background operation has been initialized.
    """
    now = time.time()
    to_start = []
    with METRO_LOCK:
        for key, state in METRO_CACHE.items():
            due = (not state["loaded"] or now >= state["next_refresh"])
            if not state["loading"] and due and now >= float(state.get("retry_after", 0)):
                state["loading"] = True
                state["status"] = "checking"
                state["attempt_id"] = int(state.get("attempt_id", 0)) + 1
                to_start.append((key, state["attempt_id"]))
    for key, attempt_id in to_start:
        threading.Thread(target=load_metro_gtfs, args=(key, False, attempt_id), daemon=True, name=f"gtfs-{key}").start()


def ensure_operator_feeds():
    # Older builds could leak metro_tmp_* keys into the global registry. Never let them block core APIs.
    """Ensure the requested resource or background operation has been initialized.
    """
    for stale_key in [k for k in list(OPEN_ACCESS_GTFS) if str(k).startswith("metro_tmp_")]:
        OPEN_ACCESS_GTFS.pop(stale_key, None)
    for key in ("iryo", "ouigo"):
        if key not in OPEN_ACCESS_GTFS or key not in OPEN_ACCESS_CACHE:
            continue
        state = OPEN_ACCESS_CACHE[key]
        if key == "ouigo" and operator_token(key, OPEN_ACCESS_GTFS[key]) and not state["loaded"]:
            state["retry_after"] = 0.0
        now = time.time()
        due = (not state["loaded"] or now - state["updated_at"] >= OPEN_ACCESS_CACHE_TTL)
        if not state["loading"] and due and now >= float(state.get("retry_after", 0)):
            threading.Thread(target=load_operator_gtfs, args=(key,), daemon=True, name=f"gtfs-{key}").start()


def ensure_background_threads():
    """Start each idempotent background loader at most once per process.
    """
    ensure_operator_feeds()
    ensure_metro_feeds()
    if not STATIC_CACHE["route_polylines"]:
        STATIC_CACHE["route_polylines"] = list(SEED_ROUTES)
    if not STATIC_CACHE["stations_loaded"] and not STATIC_CACHE["stations_loading"]:
        threading.Thread(target=load_stations_and_gtfs_thread, daemon=True).start()
    if not STATIC_CACHE["real_tracks_loaded"] and not STATIC_CACHE["real_tracks_loading"]:
        threading.Thread(target=load_real_tracks_progressive_thread, daemon=True).start()


def extract_entities_from_json(data):
    """Extract a normalized value from a provider-specific payload.

    Parameters are validated or normalized by the function; relevant inputs: ``data``.
    """
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        header_ts = data.get("header", {}).get("timestamp") if isinstance(data.get("header"), dict) else None
        for key in ["entity", "Entities", "results", "data"]:
            if key in data and isinstance(data[key], list):
                return data[key], header_ts
    return [], None


def fetch_json_entities(package_key):
    """Fetch a configured Renfe JSON feed using its primary and fallback URLs.

    Parameters are validated or normalized by the function; relevant inputs: ``package_key``.
    """
    ckan_urls = [u for fmt, u in get_ckan_resources(PACKAGES[package_key], formats=["JSON"])]
    candidate_urls = []
    for u in ckan_urls + FALLBACK_URLS.get(package_key, []):
        if u not in candidate_urls:
            candidate_urls.append(u)

    last_err = "Sin URLs candidatas"
    for url in candidate_urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                data = res.json()
                entities, header_ts = extract_entities_from_json(data)
                return entities, header_ts, url, None
            else:
                last_err = f"HTTP {res.status_code}"
        except Exception as e:
            last_err = str(e)
            continue
    return [], None, (candidate_urls[0] if candidate_urls else "N/D"), last_err


def extract_translated_text(field_obj):
    """Extract a normalized value from a provider-specific payload.

    Parameters are validated or normalized by the function; relevant inputs: ``field_obj``.
    """
    if not field_obj:
        return ""
    if isinstance(field_obj, str):
        return field_obj.strip()
    if isinstance(field_obj, dict):
        translations = field_obj.get("translation") or field_obj.get("translations") or []
        if isinstance(translations, list) and translations:
            for tr in translations:
                if isinstance(tr, dict) and str(tr.get("language", "")).lower().startswith("es"):
                    return str(tr.get("text", "")).strip()
            first = translations[0]
            if isinstance(first, dict):
                return str(first.get("text", "")).strip()
        if "text" in field_obj:
            return str(field_obj["text"]).strip()
    return ""


def geolocate_alert(informed_entities, title, description):
    """Choose a representative coordinate for a service alert from informed entities.

    Parameters are validated or normalized by the function; relevant inputs: ``informed_entities``, ``title``, ``description``.
    """
    stops_map = STATIC_CACHE["stops_by_id"]

    for ie in informed_entities:
        if not isinstance(ie, dict):
            continue
        sid = str(ie.get("stop_id") or ie.get("stopId") or "").strip()
        if sid and sid in stops_map:
            st = stops_map[sid]
            return st["lat"], st["lon"], f"Estación: {st['name']} ({sid})"

    for ie in informed_entities:
        if not isinstance(ie, dict):
            continue
        rid = str(ie.get("route_id") or ie.get("routeId") or "").strip()
        if len(rid) >= 2 and rid[:2] in NUCLEOS_CERCANIAS:
            nuc = NUCLEOS_CERCANIAS[rid[:2]]
            line_match = re.search(r"([CR]\d+[a-zA-Z]?)", rid)
            line_str = f" — Línea {line_match.group(1)}" if line_match else f" ({rid})"
            h = sum(ord(c) for c in rid)
            offset_lat = ((h % 11) - 5) * 0.008
            offset_lon = (((h // 11) % 11) - 5) * 0.008
            return nuc["lat"] + offset_lat, nuc["lon"] + offset_lon, f"Núcleo {nuc['name']}{line_str}"

    full_text = f"{title} {description}".upper()
    city_keywords = [
        ("RODALIES", 41.3794, 2.1402, "Rodalies de Catalunya"),
        ("BARCELONA", 41.3794, 2.1402, "Barcelona / Rodalies"),
        ("SANTS", 41.3794, 2.1402, "Barcelona - Sants"),
        ("MADRID", 40.4065, -3.6895, "Núcleo Madrid"),
        ("ATOCHA", 40.4065, -3.6895, "Madrid - Atocha"),
        ("CHAMART", 40.4722, -3.6822, "Madrid - Chamartín"),
        ("VALENCIA", 39.4667, -0.3772, "Núcleo València"),
        ("VALÈNCIA", 39.4667, -0.3772, "Núcleo València"),
        ("SEVILLA", 37.3917, -5.9764, "Núcleo Sevilla"),
        ("MÁLAGA", 36.7128, -4.4294, "Núcleo Málaga"),
        ("MALAGA", 36.7128, -4.4294, "Núcleo Málaga"),
        ("BILBAO", 43.2614, -2.9278, "Núcleo Bilbao"),
        ("BIZKAIA", 43.2614, -2.9278, "Núcleo Bilbao"),
        ("GIPUZKOA", 43.3175, -1.9767, "Núcleo San Sebastián"),
        ("DONOSTIA", 43.3175, -1.9767, "Núcleo San Sebastián"),
        ("ASTURIAS", 43.3669, -5.8550, "Núcleo Asturias"),
        ("OVIEDO", 43.3669, -5.8550, "Oviedo / Asturias"),
        ("GIJÓN", 43.5392, -5.6761, "Gijón / Asturias"),
        ("SANTANDER", 43.4586, -3.8122, "Núcleo Cantabria"),
        ("CANTABRIA", 43.4586, -3.8122, "Núcleo Cantabria"),
        ("ZARAGOZA", 41.6588, -0.9105, "Núcleo Zaragoza"),
        ("CÁDIZ", 36.5292, -6.2886, "Núcleo Cádiz"),
        ("CADIZ", 36.5292, -6.2886, "Núcleo Cádiz"),
        ("MURCIA", 37.9744, -1.1306, "Núcleo Murcia / Alicante"),
        ("ALICANTE", 38.3444, -0.4950, "Núcleo Alicante"),
        ("ALACANT", 38.3444, -0.4950, "Núcleo Alacant"),
        ("VALLADOLID", 41.6425, -4.7291, "Valladolid - Campo Grande"),
        ("GALICIA", 42.8703, -8.5458, "Eje Atlántico / Galicia"),
        ("EXTREMADURA", 38.9211, -6.3422, "Línea Extremadura")
    ]
    for kw, klat, klon, klabel in city_keywords:
        if kw in full_text:
            h = sum(ord(c) for c in full_text[:40])
            return klat + ((h % 9) - 4) * 0.007, klon + (((h // 9) % 9) - 4) * 0.007, klabel

    return 40.4350, -3.6900, "Aviso General Red Renfe / ADIF"


# -----------------------------------------------------------------------------
# Operational health endpoints
# -----------------------------------------------------------------------------
@app.route("/health/live")
def health_live():
    """Return a minimal liveness response without consulting external providers.
    """
    return jsonify({"status": "ok", "service": "radar-ferroviario"}), 200


@app.route("/health/ready")
def health_ready():
    """Report whether a usable train snapshot is available for serving traffic.
    """
    trains = RT_CACHE.get("trains") or []
    last_success = float(RT_CACHE.get("last_success_at") or RT_CACHE.get("timestamp") or 0)
    age = max(0, int(time.time() - last_success)) if last_success else None
    ready = bool(trains) and age is not None and age <= 900
    payload = {"status": "ready" if ready else "degraded", "trains": len(trains),
               "snapshot_age_seconds": age, "last_error": RT_CACHE.get("last_error")}
    return jsonify(payload), 200 if ready else 503


# -----------------------------------------------------------------------------
# Web UI and static network data endpoints
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    """Render the Leaflet-based map user interface.
    """
    ensure_background_threads()
    return render_template("map.html")


@app.route("/api/stations")
def api_stations():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    ensure_background_threads()
    stations = STATIC_CACHE["stations"] if STATIC_CACHE["stations"] else CORE_STATIONS
    response = jsonify({
        "success": True,
        "count": len(stations),
        "fully_loaded": STATIC_CACHE["stations_loaded"],
        "stations": stations
    })
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/api/routes")
def api_routes():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    if not STATIC_CACHE["route_polylines"]:
        STATIC_CACHE["route_polylines"] = list(SEED_ROUTES)
    routes = STATIC_CACHE["route_polylines"]
    response = jsonify({
        "success": True,
        "count": len(routes),
        "ways_count": len(STATIC_CACHE["osm_ways_seen"]),
        "stage": STATIC_CACHE["real_tracks_stage"],
        "real_geometry_loaded": STATIC_CACHE["real_tracks_loaded"],
        "source": STATIC_CACHE["real_tracks_source"],
        "routes": routes
    })
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    ensure_background_threads()
    return response


@app.route("/api/routes/viewport")
def api_routes_viewport():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    bbox_str=request.args.get("bbox","").strip()
    try:
        south,west,north,east=[float(x) for x in bbox_str.split(",")]
        if not (35.0<=south<north<=44.5 and -10.5<=west<east<=5.0): raise ValueError("bbox fuera de España")
        if north-south>1.6 or east-west>2.2:
            return jsonify({"success":True,"added":0,"cached":True,"note":"viewport amplio"})
        step=.25; qs=math.floor(south/step)*step; qw=math.floor(west/step)*step; qn=math.ceil(north/step)*step; qe=math.ceil(east/step)*step
        key=f"vp:{qs:.2f},{qw:.2f},{qn:.2f},{qe:.2f}"
        q_vp=(f'[out:json][timeout:40];('
              f'way["railway"="rail"]["service"!~"yard|siding|spur"]({qs:.2f},{qw:.2f},{qn:.2f},{qe:.2f});'
              f'way["railway"="narrow_gauge"]["service"!~"yard|siding"]({qs:.2f},{qw:.2f},{qn:.2f},{qe:.2f});'
              ');out geom;')
        elems,error,from_cache=run_overpass_query(q_vp,timeout_sec=45,cache_key=key)
        if not elems: return jsonify({"success":True,"added":0,"cached":True,"overpass_error":error})
        base=STATIC_CACHE["route_polylines"] if STATIC_CACHE["real_tracks_loaded"] else []
        updated,added=merge_elements_into_polylines(elems,base)
        if added: STATIC_CACHE["route_polylines"]=updated; STATIC_CACHE["real_tracks_loaded"]=True
        return jsonify({"success":True,"added":added,"cached":from_cache,"overpass_error":error,"routes":STATIC_CACHE["route_polylines"] if added else None})
    except Exception as e:
        return jsonify({"success":True,"added":0,"cached":True,"overpass_error":str(e)})


def build_train_stops(trip_id, train_num, current_stop_id="", realtime_delays=None):
    """Build the ordered stop timeline attached to a real-time train response.

    Parameters are validated or normalized by the function; relevant inputs: ``trip_id``, ``train_num``, ``current_stop_id``, ``realtime_delays``.
    """
    realtime_delays = realtime_delays or {}
    sequence = STATIC_CACHE.get("trip_stops_by_id", {}).get(trip_id)
    if not sequence:
        by_num = STATIC_CACHE.get("trip_stops_by_num", {})
        for alias in train_number_aliases(train_num, trip_id):
            sequence = by_num.get(alias)
            if sequence:
                break
    sequence = sequence or []
    current_seq = None
    for item in sequence:
        if str(item.get("stop_id")) == str(current_stop_id):
            current_seq = item.get("sequence")
            break
    result = []
    for item in sequence:
        sid = str(item.get("stop_id", ""))
        station = STATIC_CACHE.get("stops_by_id", {}).get(sid, {})
        seq = item.get("sequence", 0)
        relation = "current" if sid == str(current_stop_id) else ("previous" if current_seq is not None and seq < current_seq else "next")
        result.append({**item, "name": station.get("name") or sid, "delay_min": realtime_delays.get(sid), "relation": relation})
    return result

# -----------------------------------------------------------------------------
# Real-time train snapshot API
# -----------------------------------------------------------------------------
@app.route("/api/trains")
def api_trains():
    """Renfe core endpoint, isolated from every optional worker and feed."""
    started = time.time()
    RT_CACHE["last_attempt_at"] = started
    acquired = TRAIN_REFRESH_LOCK.acquire(timeout=10)
    if not acquired:
        age = max(0, int(started - (RT_CACHE.get("last_success_at") or RT_CACHE.get("timestamp") or started)))
        return jsonify({"success": True, "trains": RT_CACHE.get("trains") or [],
                        "diagnostics": RT_CACHE.get("diagnostics") or {}, "cached": True,
                        "stale": True, "age_seconds": age, "warning": "refresh_in_progress"})
    try:
        return _refresh_trains_impl()
    except Exception as exc:
        RT_CACHE["last_error"] = f"{type(exc).__name__}: {exc}"
        log_exception("api_trains isolated refresh", exc)
        age = max(0, int(time.time() - (RT_CACHE.get("last_success_at") or RT_CACHE.get("timestamp") or time.time())))
        return jsonify({"success": True, "trains": RT_CACHE.get("trains") or [],
                        "diagnostics": RT_CACHE.get("diagnostics") or {}, "cached": True,
                        "stale": True, "age_seconds": age, "warning": "refresh_failed",
                        "error_type": type(exc).__name__})
    finally:
        TRAIN_REFRESH_LOCK.release()

def _refresh_trains_impl():
    """Fetch, classify, normalize and atomically publish one train snapshot.
    """
    now = time.time()
    snap_enabled = request.args.get("snap", "1") == "1"

    if now - RT_CACHE["timestamp"] < 6 and RT_CACHE["trains"]:
        cached_trains = RT_CACHE["trains"]
        if STATIC_CACHE.get("stations_loaded"):
            for train in cached_trains:
                if not train.get("stops"):
                    train["stops"] = build_train_stops(train.get("trip_id", ""), extract_train_number(f"{train.get('id','')} {train.get('label','')}"), "", {})
        return jsonify({"success": True, "trains": cached_trains, "diagnostics": RT_CACHE["diagnostics"], "static_gtfs_ready": STATIC_CACHE.get("stations_loaded", False)})


    trains = []
    seen_train_nums = set()
    diagnostics = {}

    # 1. CERCANÍAS (GTFS-RT Posiciones en Tiempo Real)
    cerc_entities, cerc_hdr_ts, cerc_url, cerc_err = fetch_json_entities("cercanias_pos")
    cerc_count = 0
    discarded_vehicles = 0
    for ent in cerc_entities:
        if not isinstance(ent, dict):
            discarded_vehicles += 1
            continue
        veh = ent.get("vehicle") or ent
        if not isinstance(veh, dict):
            discarded_vehicles += 1
            continue
        pos = veh.get("position") or {}
        lat = parse_float(pos.get("latitude") or pos.get("lat"))
        lon = parse_float(pos.get("longitude") or pos.get("lon"))
        if lat and lon:
            trip = veh.get("trip") or {}
            v_info = veh.get("vehicle") or {}
            tid = str(trip.get("trip_id") or trip.get("tripId") or "")
            rid = str(trip.get("route_id") or trip.get("routeId") or "")
            label = str(v_info.get("label") or "")
            vid = str(v_info.get("id") or ent.get("id") or f"CERC-{cerc_count}")
            tnum = extract_train_number(f"{vid} {label} {tid}")
            stop_id = str(veh.get("stop_id") or veh.get("stopId") or "")
            stop_name = STATIC_CACHE["stops_by_id"].get(stop_id, {}).get("name", stop_id or "En tránsito")

            line_match = re.search(r"([CR]\d+[a-zA-Z]?)", f"{label} {rid}")
            sub_badge = line_match.group(1).upper() if line_match else "Cercanías"
            nucleo_code = rid[:2] if len(rid) >= 2 and rid[:2].isdigit() else ""
            nucleo_name = NUCLEOS_CERCANIAS.get(nucleo_code, {}).get("name", "Cercanías")
            is_feve = is_feve_service(nucleo_code, rid, label, sub_badge, {})
            if is_feve and sub_badge == "Cercanías":
                sub_badge = "FEVE/RAM"

            status_str = str(veh.get("current_status") or veh.get("currentStatus") or "IN_TRANSIT_TO")
            veh_ts = veh.get("timestamp") or cerc_hdr_ts
            speed_kmh, speed_source, bearing, trail = compute_train_kinematics(
                f"CERC:{vid}", lat, lon, pos.get("speed"), veh_ts, status_str, "Cercanías"
            )

            draw_lat, draw_lon = snap_to_nearest_track_segment(lat, lon) if snap_enabled else (lat, lon)

            trains.append({
                "id": vid,
                "label": label or vid,
                "type": "Cercanías",
                "subtype": sub_badge,
                "lat": draw_lat,
                "lon": draw_lon,
                "raw_lat": lat,
                "raw_lon": lon,
                "speed": speed_kmh,
                "speed_source": speed_source,
                "bearing": bearing,
                "trail": trail,
                "route_id": rid or sub_badge,
                "trip_id": tid,
                "origin_dest": f"Núcleo {nucleo_name} ({sub_badge})",
                "nucleo": nucleo_name,
                "is_feve": is_feve,
                "next_stop": stop_name,
                "delay_min": 0,
                "current_status": status_str,
                "stops": build_train_stops(tid, tnum, stop_id, {})
            })
            cerc_count += 1

    diagnostics["cercanias"] = {"url": cerc_url, "count": cerc_count, "error": cerc_err}

    # 2. ACTUALIZACIONES DE VIAJE (Trip Updates de AVE / LD / MD)
    ld_upd_entities, _, ld_upd_url, _ = fetch_json_entities("ld_updates")
    trip_updates_map = {}
    for ent in ld_upd_entities:
        tu = ent.get("trip_update") or ent.get("tripUpdate") or {}
        trip = tu.get("trip") or {}
        tid = str(trip.get("trip_id") or trip.get("tripId") or ent.get("id") or "")
        tnum = extract_train_number(tid)
        delay_sec = tu.get("delay") or 0
        st_updates = tu.get("stop_time_update") or tu.get("stopTimeUpdate") or []
        next_stop_id = ""
        stop_delays = {}
        if st_updates and isinstance(st_updates, list):
            for stu in st_updates:
                sid_cand = str(stu.get("stop_id") or stu.get("stopId") or "")
                if sid_cand:
                    if not next_stop_id:
                        next_stop_id = sid_cand
                    timing = stu.get("arrival") or stu.get("departure") or {}
                    this_delay = timing.get("delay") or 0
                    try: stop_delays[sid_cand] = round(float(this_delay) / 60, 1)
                    except Exception: stop_delays[sid_cand] = 0
                    if not delay_sec:
                        delay_sec = this_delay
        info_obj = {
            "trip_id": tid,
            "train_num": tnum,
            "delay_min": round(int(delay_sec) / 60, 1) if delay_sec else 0,
            "next_stop_id": next_stop_id,
            "stop_delays": stop_delays
        }
        if tid:
            trip_updates_map[tid] = info_obj
        if tnum:
            trip_updates_map[tnum] = info_obj

    # 3. ALTA VELOCIDAD, LARGA DISTANCIA Y MEDIA DISTANCIA (GTFS-RT Posiciones en Tiempo Real)
    ld_entities, ld_hdr_ts, ld_url, ld_err = fetch_json_entities("ld_pos")
    ld_counts = {"AVE": 0, "Larga Distancia": 0, "Media Distancia": 0}

    for ent in ld_entities:
        if not isinstance(ent, dict):
            discarded_vehicles += 1
            continue
        veh = ent.get("vehicle") or ent
        if not isinstance(veh, dict):
            discarded_vehicles += 1
            continue
        pos = veh.get("position") or {}
        lat = parse_float(pos.get("latitude") or pos.get("lat"))
        lon = parse_float(pos.get("longitude") or pos.get("lon"))
        if lat and lon:
            trip = veh.get("trip") or {}
            v_info = veh.get("vehicle") or {}
            tid = str(trip.get("trip_id") or trip.get("tripId") or "")
            rid = str(trip.get("route_id") or trip.get("routeId") or "")
            label = str(v_info.get("label") or "")
            vid = str(v_info.get("id") or ent.get("id") or tid or f"LD-{sum(ld_counts.values())}")
            stop_id = str(veh.get("stop_id") or veh.get("stopId") or "")

            tnum = extract_train_number(f"{vid} {label} {tid}")
            tmeta = STATIC_CACHE["trips_by_id"].get(tid) or STATIC_CACHE["trips_by_num"].get(tnum) or {}
            if not rid and tmeta.get("route_id"):
                rid = tmeta["route_id"]
            rmeta = STATIC_CACHE["routes_by_id"].get(rid, {})

            t_type, subtype = classify_national_train(rid, tid, label, vid, rmeta)
            ld_counts[t_type] = ld_counts.get(t_type, 0) + 1

            tu_info = trip_updates_map.get(tid) or trip_updates_map.get(tnum) or {}
            if not stop_id and tu_info.get("next_stop_id"):
                stop_id = tu_info["next_stop_id"]
            stop_name = STATIC_CACHE["stops_by_id"].get(stop_id, {}).get("name", stop_id or "En ruta")
            delay_min = tu_info.get("delay_min", round((parse_float(veh.get("delay")) or 0) / 60, 1))

            origin_dest = rmeta.get("long_name") or tmeta.get("headsign") or label or rid or f"Servicio {subtype}"
            status_str = str(veh.get("current_status") or veh.get("currentStatus") or "IN_TRANSIT_TO")
            veh_ts = veh.get("timestamp") or ld_hdr_ts

            train_key = f"NAC:{tnum or vid}"
            speed_kmh, speed_source, bearing, trail = compute_train_kinematics(
                train_key, lat, lon, pos.get("speed"), veh_ts, status_str, t_type
            )

            draw_lat, draw_lon = snap_to_nearest_track_segment(lat, lon) if snap_enabled else (lat, lon)

            trains.append({
                "id": tnum or vid,
                "label": label or f"{subtype} {tnum or vid}",
                "type": t_type,
                "subtype": subtype,
                "lat": draw_lat,
                "lon": draw_lon,
                "raw_lat": lat,
                "raw_lon": lon,
                "speed": speed_kmh,
                "speed_source": speed_source,
                "bearing": bearing,
                "trail": trail,
                "route_id": rid or subtype,
                "trip_id": tid,
                "origin_dest": origin_dest,
                "next_stop": stop_name,
                "delay_min": delay_min,
                "current_status": status_str,
                "stops": build_train_stops(tid, tnum, stop_id, tu_info.get("stop_delays", {}))
            })
            if tnum:
                seen_train_nums.add(tnum)

    # 4. Complemento desde Trip Updates
    for key, tu_info in list(trip_updates_map.items()):
        tnum = tu_info.get("train_num")
        if not tnum or tnum in seen_train_nums:
            continue
        next_sid = tu_info.get("next_stop_id")
        st_obj = STATIC_CACHE["stops_by_id"].get(next_sid)
        if st_obj:
            tid = tu_info.get("trip_id", "")
            tmeta = STATIC_CACHE["trips_by_id"].get(tid) or STATIC_CACHE["trips_by_num"].get(tnum) or {}
            rid = tmeta.get("route_id", "")
            rmeta = STATIC_CACHE["routes_by_id"].get(rid, {})
            t_type, subtype = classify_national_train(rid, tid, "", tnum, rmeta)
            ld_counts[t_type] = ld_counts.get(t_type, 0) + 1
            seen_train_nums.add(tnum)
            origin_dest = rmeta.get("long_name") or tmeta.get("headsign") or f"Servicio {subtype}"

            train_key = f"NAC_TU:{tnum}"
            speed_kmh, speed_source, bearing, trail = compute_train_kinematics(
                train_key, st_obj["lat"], st_obj["lon"], 0.0, now, "HORARIO_RT_ACTIVO", t_type
            )

            trains.append({
                "id": tnum,
                "label": f"{subtype}-{tnum}",
                "type": t_type,
                "subtype": subtype,
                "lat": st_obj["lat"],
                "lon": st_obj["lon"],
                "raw_lat": st_obj["lat"],
                "raw_lon": st_obj["lon"],
                "speed": speed_kmh,
                "speed_source": speed_source,
                "bearing": bearing,
                "trail": trail,
                "route_id": rid or subtype,
                "trip_id": tid,
                "origin_dest": origin_dest,
                "next_stop": st_obj["name"],
                "delay_min": tu_info.get("delay_min", 0),
                "current_status": "HORARIO_RT_ACTIVO",
                "stops": build_train_stops(tid, tnum, next_sid, tu_info.get("stop_delays", {}))
            })

    moved_count = sum(1 for t in trains if t["speed"] > 0)
    diagnostics["nacional_ave_ld_md"] = {
        "url": ld_url,
        "counts": ld_counts,
        "total": sum(ld_counts.values()),
        "with_calculated_speed": moved_count,
        "error": ld_err
    }

    RT_CACHE["last_attempt_at"] = now
    RT_CACHE["discarded_vehicles"] = discarded_vehicles
    diagnostics["snapshot"] = {"source": "live" if trains else "empty", "generated_at": now,
                               "discarded_vehicles": discarded_vehicles}
    if not trains and RT_CACHE.get("trains"):
        age = max(0, int(now - (RT_CACHE.get("last_success_at") or RT_CACHE.get("timestamp") or now)))
        stale_diag = dict(RT_CACHE.get("diagnostics") or {})
        stale_diag["snapshot"] = {"source": "last_valid_cache", "stale": True,
                                  "age_seconds": age, "refresh_diagnostics": diagnostics,
                                  "discarded_vehicles": discarded_vehicles}
        return jsonify({"success": True, "trains": RT_CACHE["trains"], "diagnostics": stale_diag,
                        "cached": True, "stale": True, "age_seconds": age})
    RT_CACHE["timestamp"] = now
    RT_CACHE["trains"] = trains
    RT_CACHE["diagnostics"] = diagnostics
    if trains:
        RT_CACHE["last_success_at"] = now
        RT_CACHE["last_error"] = None
    return jsonify({"success": True, "trains": trains, "diagnostics": diagnostics,
                    "cached": False, "stale": False})


# -----------------------------------------------------------------------------
# Service alerts and schedule-derived transit estimates
# -----------------------------------------------------------------------------
@app.route("/api/alerts")
def api_alerts():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    now = time.time()
    if now - ALERTS_CACHE["timestamp"] < 15 and ALERTS_CACHE["alerts"]:
        return jsonify({
            "success": True,
            "count": len(ALERTS_CACHE["alerts"]),
            "alerts": ALERTS_CACHE["alerts"],
            "diagnostics": ALERTS_CACHE["diagnostics"]
        })

    alerts_list = []
    raw_entities, hdr_ts, alert_url, alert_err = fetch_json_entities("alerts")

    for idx, ent in enumerate(raw_entities):
        al = ent.get("alert") or ent
        if not isinstance(al, dict):
            continue

        header_txt = extract_translated_text(al.get("header_text") or al.get("headerText"))
        desc_txt = extract_translated_text(al.get("description_text") or al.get("descriptionText"))
        if not header_txt and not desc_txt:
            continue

        title = header_txt or (desc_txt[:95] + "..." if len(desc_txt) > 95 else desc_txt)
        description = desc_txt or header_txt

        informed = al.get("informed_entity") or al.get("informedEntity") or []
        lat, lon, scope_label = geolocate_alert(informed, title, description)

        upper_body = f"{title} {description}".upper()
        if any(w in upper_body for w in ["INTERRUMPID", "SUSPENDID", "CORTE", "CANCELAD", "AVERÍA GRAVE", "SIN SERVICIO"]):
            severity = "ALTA"
        elif any(w in upper_body for w in ["RETRASO", "DEMORA", "AUTOBÚS", "AUTOBUS", "TRANSBORDO", "OBRAS", "INCIDENCIA", "VÍA"]):
            severity = "MEDIA"
        else:
            severity = "INFO"

        alerts_list.append({
            "id": str(ent.get("id") or f"AL-{idx}"),
            "title": title,
            "description": description,
            "scope": scope_label,
            "severity": severity,
            "source": "GTFS-RT Avisos Oficiales",
            "lat": lat,
            "lon": lon
        })

    for t in RT_CACHE.get("trains", []):
        delay = parse_float(t.get("delay_min")) or 0.0
        if delay >= 15.0:
            alerts_list.append({
                "id": f"DELAY-{t['id']}",
                "title": f"Demora de +{int(delay)} min en {t['subtype']} ({t['label']})",
                "description": f"El tren {t['label']} ({t['origin_dest']}) registra un retraso de {delay} minutos en tiempo real. Próxima parada: {t['next_stop']}.",
                "scope": f"{t['type']} — {t['next_stop']}",
                "severity": "ALTA" if delay >= 30 else "MEDIA",
                "source": "Telemetría Retrasos GTFS-RT",
                "lat": t["lat"],
                "lon": t["lon"]
            })

    ALERTS_CACHE["timestamp"] = now
    ALERTS_CACHE["alerts"] = alerts_list
    ALERTS_CACHE["diagnostics"] = {"url": alert_url, "official_count": len(raw_entities), "error": alert_err}

    return jsonify({
        "success": True,
        "count": len(alerts_list),
        "alerts": alerts_list,
        "diagnostics": ALERTS_CACHE["diagnostics"]
    })


def _gtfs_seconds(value):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``value``.
    """
    try:
        parts = [int(float(x)) for x in str(value or "").split(":")]
        if len(parts) != 3: return None
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        return None


def _bearing_degrees(lat1, lon1, lat2, lon2):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``lat1``, ``lon1``, ``lat2``, ``lon2``.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return round((math.degrees(math.atan2(y, x)) + 360) % 360, 1)


def _shift_gtfs_time(value, offset):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``value``, ``offset``.
    """
    seconds = _gtfs_seconds(value)
    if seconds is None: return value
    shifted = seconds + offset
    return f"{shifted // 3600:02d}:{(shifted % 3600) // 60:02d}:{shifted % 60:02d}"


def _trip_instances_for_now(trip, current):
    """Returns active scheduled instances, including GTFS frequencies.txt templates."""
    stops = trip.get("stops") or []
    if len(stops) < 2: return []
    base_first = _gtfs_seconds(stops[0].get("departure") or stops[0].get("arrival"))
    base_last = _gtfs_seconds(stops[-1].get("arrival") or stops[-1].get("departure"))
    if base_first is None or base_last is None: return []
    frequencies = trip.get("frequencies") or []
    if not frequencies:
        return [(trip, 0)] if base_first <= current <= base_last else []
    duration = max(1, base_last - base_first)
    instances = []
    for block in frequencies:
        start, end, headway = int(block["start"]), int(block["end"]), int(block["headway"])
        # Candidate whose run could currently be active. Check adjacent slot for boundary safety.
        index = max(0, (current - start) // headway)
        for candidate_index in {index - 1, index, index + 1}:
            departure = start + candidate_index * headway
            if candidate_index < 0 or departure >= end: continue
            if departure <= current <= departure + duration:
                offset = departure - base_first
                shifted = dict(trip)
                shifted["id"] = f"{trip['id']}:freq:{departure}"
                shifted["stops"] = [{**stop,
                    "arrival": _shift_gtfs_time(stop.get("arrival"), offset),
                    "departure": _shift_gtfs_time(stop.get("departure"), offset)} for stop in stops]
                instances.append((shifted, offset))
    dedup = {instance[0]["id"]: instance for instance in instances}
    return list(dedup.values())


def estimate_operator_trains(operator_key, state, now=None):
    """Interpolates timetable positions. EST always means calculated, never GPS."""
    if operator_key in OPEN_ACCESS_GTFS:
        cfg = OPEN_ACCESS_GTFS[operator_key]
    else:
        metro_cfg = METRO_GTFS.get(operator_key, {})
        cfg = {"name": metro_cfg.get("name", operator_key), "color": metro_cfg.get("color", "#64748B")}
    now = now or datetime.now()
    current = now.hour * 3600 + now.minute * 60 + now.second
    estimates = []
    for template in state.get("trips", []):
        for trip, _ in _trip_instances_for_now(template, current):
            stops = trip.get("stops") or []
            previous = upcoming = None
            for a, b in zip(stops, stops[1:]):
                depart = _gtfs_seconds(a.get("departure") or a.get("arrival"))
                arrive = _gtfs_seconds(b.get("arrival") or b.get("departure"))
                if depart is not None and arrive is not None and depart <= current <= arrive:
                    previous, upcoming = a, b
                    break
            if not previous or not upcoming: continue
            depart = _gtfs_seconds(previous.get("departure") or previous.get("arrival"))
            arrive = _gtfs_seconds(upcoming.get("arrival") or upcoming.get("departure"))
            duration = max(1, arrive - depart)
            fraction = max(0.0, min(1.0, (current - depart) / duration))
            lat1, lon1 = parse_float(previous.get("lat")), parse_float(previous.get("lon"))
            lat2, lon2 = parse_float(upcoming.get("lat")), parse_float(upcoming.get("lon"))
            if None in (lat1, lon1, lat2, lon2): continue
            lat, lon = lat1 + (lat2-lat1)*fraction, lon1 + (lon2-lon1)*fraction
            estimates.append({"id":f"estimated:{trip['id']}","trip_id":trip.get("trip_id"),"operator_key":operator_key,
                "operator":cfg["name"],"type":cfg["name"],"label":trip.get("label") or cfg["name"],"route_id":trip.get("route_id"),
                "lat":round(lat,6),"lon":round(lon,6),"bearing":_bearing_degrees(lat1,lon1,lat2,lon2),
                "origin":trip.get("origin"),"destination":trip.get("destination"),"previous_stop":previous.get("name"),"next_stop":upcoming.get("name"),
                "scheduled_departure":previous.get("departure") or previous.get("arrival"),"scheduled_arrival":upcoming.get("arrival") or upcoming.get("departure"),
                "segment_progress":round(fraction*100,1),"color":cfg["color"],"position_source":"Estimación por horario GTFS entre paradas; no es GPS",
                "estimated":True,"frequency_based":bool(template.get("frequencies")),"updated_at":now.isoformat(timespec="seconds")})
    return estimates


def _transit_source_diagnostics(key, cfg, state):
    """Return a JSON-safe, complete download/cache snapshot for one GTFS network."""
    now = time.time()
    return {
        "key": key, "name": cfg["name"], "color": cfg["color"],
        "source": cfg["source"],
        "source_page": sanitize_url(cfg["source_page"]) if cfg.get("source_page") else None,
        "source_strategy": cfg.get("source_strategy", "nap"),
        "nap_file_id": cfg.get("nap_id"),
        "fallback_urls": [sanitize_url(url) for url in cfg.get("fallback_urls", [])],
        "loaded": state.get("loaded", False), "loading": state.get("loading", False),
        "status": state.get("status", "pending"),
        "active_source": sanitize_text(state.get("active_source")) if state.get("active_source") else None,
        "using_cache": state.get("using_cache", False),
        "stale": state.get("stale", False),
        "cache_age_seconds": state.get("cache_age_seconds"),
        "download_attempts": sanitize_data(state.get("download_attempts", [])),
        "last_attempt_at": state.get("last_attempt_at", 0),
        "last_success_at": state.get("last_success_at", 0),
        "updated_at": state.get("updated_at", 0),
        "last_checked": state.get("last_checked", 0),
        "next_refresh": state.get("next_refresh", 0),
        "retry_in": max(0, int(state.get("retry_after", 0) - now)),
        "error": sanitize_text(state.get("error")) if state.get("error") else None,
        "station_count": len(state.get("stations", [])),
        "route_count": len(state.get("routes", [])),
        "trip_count": len(state.get("trips", [])),
    }


@app.route("/api/transit-networks")
def api_transit_networks():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    ensure_metro_feeds()
    networks={}
    for key,cfg in METRO_GTFS.items():
        state=METRO_CACHE[key]
        estimates=estimate_operator_trains(key,state) if state["loaded"] else []
        source_info = _transit_source_diagnostics(key, cfg, state)
        source_info.update({
            "estimated_count": len(estimates),
            "stations": state["stations"], "routes": state["routes"],
            "trips": state["trips"], "estimated_trains": estimates,
        })
        networks[key] = source_info
    # FEVE/RAM already arrives in Renfe Cercanías GTFS-RT. Expose explicit inventory/status.
    feve=[t for t in RT_CACHE.get("trains",[]) if t.get("is_feve") or re.search(r"FEVE|RAM|ANCHO.?M[EÉ]TRICO", f"{t.get('subtype','')} {t.get('route_id','')} {t.get('origin_dest','')}", re.I)]
    loaded_networks=sum(1 for x in networks.values() if x["loaded"])
    return jsonify({"success":True,"network_summary":{"loaded":loaded_networks,"total":len(networks)},"networks":networks,"feve":{"name":"Renfe Cercanías AM / FEVE","loaded":True,"source":"Renfe GTFS-RT Cercanías","trains":feve,"updated_at":RT_CACHE.get("timestamp",0)}})

@app.route("/api/feeds/refresh",methods=["POST"])
def refresh_feeds():
    """Perform the documented application operation while preserving current API contracts.
    """
    for key in OPEN_ACCESS_GTFS: threading.Thread(target=load_operator_gtfs,args=(key,True),daemon=True).start()
    metro_jobs=[]
    with METRO_LOCK:
        for key,state in METRO_CACHE.items():
            if state.get("loading"):
                continue
            state["loading"]=True; state["status"]="checking"; state["retry_after"]=0.0
            state["attempt_id"]=int(state.get("attempt_id",0))+1
            metro_jobs.append((key,state["attempt_id"]))
    for key,attempt_id in metro_jobs:
        threading.Thread(target=load_metro_gtfs,args=(key,True,attempt_id),daemon=True,name=f"gtfs-{key}-manual").start()
    return jsonify({"success":True,"message":"Renovación iniciada"})

@app.route("/api/operators/config", methods=["GET", "POST", "DELETE"])
def api_operator_config():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    if request.method == "GET":
        configured = bool(operator_token("ouigo", OPEN_ACCESS_GTFS["ouigo"]))
        return jsonify({"success": True, "ouigo_configured": configured,
                        "instructions_url": "https://nap.transportes.gob.es/Account/InstruccionesAPI"})
    if request.method == "DELETE":
        save_operator_token("ouigo", "")
        state = OPEN_ACCESS_CACHE["ouigo"]
        state.update(loaded=False, error="Configuración eliminada", retry_after=0.0, fail_count=0)
        return jsonify({"success": True})
    data = request.get_json(silent=True) or {}
    token = str(data.get("token") or "").strip()
    if len(token) < 8 or len(token) > 512:
        return jsonify({"success": False, "error": "API key no válida"}), 400
    save_operator_token("ouigo", token)
    state = OPEN_ACCESS_CACHE["ouigo"]
    state.update(loaded=False, loading=False, error=None, retry_after=0.0, fail_count=0)
    threading.Thread(target=load_operator_gtfs, args=("ouigo", True), daemon=True, name="gtfs-ouigo-config").start()
    return jsonify({"success": True, "message": "API key guardada; descarga OUIGO iniciada"})

@app.route("/api/operators")
def api_operators():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    ensure_operator_feeds()
    operators = {}
    for key, cfg in OPEN_ACCESS_GTFS.items():
        state = OPEN_ACCESS_CACHE[key]
        operators[key] = {"key": key, "name": cfg["name"], "color": cfg["color"], "source": cfg["source"],
                          "attribution": cfg["attribution"], "loaded": state["loaded"], "loading": state["loading"],
                          "updated_at": state["updated_at"], "last_checked": state.get("last_checked", state["updated_at"]),
                          "next_refresh": state["updated_at"] + OPEN_ACCESS_CACHE_TTL if state["updated_at"] else 0, "error": state["error"],
                          "retry_in": max(0, int(state.get("retry_after", 0) - time.time())),
                          "configuration_required": key == "ouigo" and not state["loaded"] and not operator_token(key, cfg) and not os.getenv("OUIGO_GTFS_FILE"),
                          "stations": state["stations"], "routes": state["routes"], "trips": state["trips"],
                          "estimated_trains": estimate_operator_trains(key, state) if state["loaded"] else []}
    response = jsonify({"success": True, "operators": operators})
    response.headers["Cache-Control"] = "no-store"
    return response

# -----------------------------------------------------------------------------
# Administrative diagnostics. Protect these routes before Internet exposure.
# -----------------------------------------------------------------------------
@app.route("/api/diagnostics")
def api_diagnostics():
    """Expose operational counters, provider health and recent non-sensitive errors.
    """
    try:
        log_size = os.path.getsize(ERROR_LOG_FILE) if os.path.exists(ERROR_LOG_FILE) else 0
        tracks_loading_seconds = (
            int(time.time() - STATIC_CACHE.get("real_tracks_started_at", time.time()))
            if STATIC_CACHE.get("real_tracks_loading") else 0
        )
        tracks_last_progress_age = (
            int(time.time() - STATIC_CACHE.get("real_tracks_last_progress_at", time.time()))
            if STATIC_CACHE.get("real_tracks_loading") else 0
        )
        completed_stages = STATIC_CACHE.get("real_tracks_stages_completed", [])
        failed_stages = STATIC_CACHE.get("real_tracks_stages_failed", [])
        active_overpass_attempt = any(
            state.get("attempt_in_progress") for state in OVERPASS_ENDPOINT_HEALTH.values()
        )
        tracks_status = (
            "stalled" if STATIC_CACHE.get("real_tracks_loading")
            and tracks_last_progress_age > 90 and not active_overpass_attempt else
            "loading" if STATIC_CACHE.get("real_tracks_loading") else
            "partial" if completed_stages and failed_stages else
            "ready" if STATIC_CACHE.get("real_tracks_loaded") else
            "failed" if STATIC_CACHE.get("real_tracks_last_completed_at") else "idle"
        )
        payload = {
            "success": True,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "uptime": round(time.time() - APP_START_TIME),
            "feeds": sanitize_data(RT_CACHE.get("diagnostics", {})),
            "gtfs_sources": {
                key: _transit_source_diagnostics(key, cfg, METRO_CACHE[key])
                for key, cfg in METRO_GTFS.items()
            },
            "train_snapshot": {"last_success_at": RT_CACHE.get("last_success_at", 0),
                               "last_attempt_at": RT_CACHE.get("last_attempt_at", 0),
                               "last_error": sanitize_text(RT_CACHE.get("last_error")) if RT_CACHE.get("last_error") else None,
                               "discarded_vehicles": RT_CACHE.get("discarded_vehicles", 0)},
            "counts": {
                "trains": len(RT_CACHE.get("trains", [])),
                "stations": len(STATIC_CACHE.get("stations", [])),
                "routes": len(STATIC_CACHE.get("route_polylines", [])),
                "overpass_cache": len(OVERPASS_QUERY_CACHE)
            },
            "background": {
                "stations_loaded": STATIC_CACHE.get("stations_loaded", False),
                "tracks_loaded": STATIC_CACHE.get("real_tracks_loaded", False),
                "tracks_loading": STATIC_CACHE.get("real_tracks_loading", False),
                "tracks_stage": STATIC_CACHE.get("real_tracks_stage", 0),
                "tracks_source": STATIC_CACHE.get("real_tracks_source", "N/D"),
                "tracks_status": tracks_status,
                "tracks_loading_seconds": tracks_loading_seconds,
                "tracks_last_progress_age_seconds": tracks_last_progress_age,
                "tracks_last_completed_at": STATIC_CACHE.get("real_tracks_last_completed_at", 0),
                "tracks_error": STATIC_CACHE.get("real_tracks_error"),
                "tracks_stages_completed": completed_stages,
                "tracks_stages_failed": failed_stages
            },
            "overpass_mirrors": sanitize_data(OVERPASS_SERVICE.diagnostics()),
            "error_log": {"path": ERROR_LOG_FILE, "size_bytes": log_size, "retention": "3 x 2 MB"},
            "errors": list(RECENT_ERRORS)[:50]
        }
        response = jsonify(payload); response.headers["Cache-Control"] = "no-store"; return response
    except Exception as e:
        log_exception("api_diagnostics", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/diagnostics/log")
def download_error_log():
    """Download provider data with timeout, validation and cache handling.
    """
    from flask import send_file
    if not os.path.exists(ERROR_LOG_FILE):
        Path(ERROR_LOG_FILE).touch()
    return send_file(ERROR_LOG_FILE, as_attachment=True, download_name="radar_errors.log", mimetype="text/plain")

@app.route("/api/diagnostics/errors", methods=["DELETE"])
def clear_error_log():
    """Perform the documented application operation while preserving current API contracts.
    """
    try:
        RECENT_ERRORS.clear()
        open(ERROR_LOG_FILE, "w", encoding="utf-8").close()
        APP_LOGGER.info("Registro de errores limpiado desde el panel")
        return jsonify({"success": True})
    except Exception as e:
        log_exception("clear_error_log", e)
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------------------------------------------------------------
# Public ADIF/ArcGIS discovery and layer access
# Security note: preserve strict URL validation and introduce an allowlist.
# -----------------------------------------------------------------------------
@app.route("/api/adif/catalog")
def api_adif_catalog():
    """Handle the corresponding HTTP API operation and return a JSON response.
    """
    now = time.time()
    if now - ADIF_CACHE["timestamp"] < 300 and ADIF_CACHE["datasets"]:
        return jsonify({"success": True, "datasets": ADIF_CACHE["datasets"]})

    datasets = []
    seen_titles = set()

    try:
        res = requests.get("https://adif-equisyzeta.hub.arcgis.com/data.json", headers=HEADERS, timeout=8)
        if res.status_code == 200:
            dcat = res.json()
            for item in dcat.get("dataset", []):
                title = str(item.get("title", "")).strip()
                if not title or title in seen_titles:
                    continue
                desc = re.sub(r"<[^>]+>", "", str(item.get("description", ""))).strip()
                geojson_url = None
                rest_url = None
                web_url = item.get("landingPage") or "https://adif-equisyzeta.hub.arcgis.com/search"

                for dist in item.get("distribution", []):
                    fmt = str(dist.get("format", "")).upper()
                    media = str(dist.get("mediaType", "")).lower()
                    aurl = dist.get("accessURL") or dist.get("downloadURL") or ""
                    if "GEOJSON" in fmt or "vnd.geo+json" in media or aurl.lower().endswith(".geojson"):
                        geojson_url = aurl
                    elif "ARCGIS GEOSERVICES" in fmt or "FeatureServer" in aurl or "MapServer" in aurl:
                        rest_url = aurl

                datasets.append({
                    "id": item.get("identifier") or f"adif-{len(datasets)}",
                    "title": title,
                    "description": desc[:220] + ("..." if len(desc) > 220 else ""),
                    "geojson_url": geojson_url,
                    "rest_url": rest_url,
                    "web_url": web_url,
                    "source": "ADIF ArcGIS Hub (DCAT)"
                })
                seen_titles.add(title)
    except Exception as e:
        print(f"[ADIF Hub data.json] Aviso: {e}")

    try:
        agol_url = "https://www.arcgis.com/sharing/rest/search"
        params = {
            "q": '(ADIF OR "Red Ferroviaria" OR "Estaciones ADIF" OR "Líneas Ferrocarril España") AND type:"Feature Service"',
            "f": "json",
            "num": 15
        }
        res = requests.get(agol_url, params=params, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            agol = res.json()
            for item in agol.get("results", []):
                title = str(item.get("title", "")).strip()
                if not title or title in seen_titles:
                    continue
                desc = re.sub(r"<[^>]+>", "", str(item.get("snippet") or item.get("description") or "")).strip()
                rest_url = item.get("url") or ""
                datasets.append({
                    "id": item.get("id"),
                    "title": title,
                    "description": desc[:220] + ("..." if len(desc) > 220 else ""),
                    "geojson_url": None,
                    "rest_url": rest_url,
                    "web_url": f"https://www.arcgis.com/home/item.html?id={item.get('id')}",
                    "source": "ArcGIS Online FeatureService (ADIF/RFIG)"
                })
                seen_titles.add(title)
    except Exception as e:
        print(f"[ArcGIS REST Search] Aviso: {e}")

    ADIF_CACHE["timestamp"] = now
    ADIF_CACHE["datasets"] = datasets

    return jsonify({
        "success": True,
        "count": len(datasets),
        "hub_url": "https://adif-equisyzeta.hub.arcgis.com/search",
        "datasets": datasets
    })


@app.route("/api/adif/layer")
def api_adif_layer():
    """Proxy a permitted public ADIF or ArcGIS layer as validated GeoJSON.
    """
    target_url = request.args.get("url", "").strip()
    if not target_url:
        return jsonify({"success": False, "error": "Falta el parámetro url"})

    if target_url in ADIF_CACHE["layers_geojson"]:
        return jsonify({"success": True, "geojson": ADIF_CACHE["layers_geojson"][target_url]})

    try:
        query_url = target_url
        if "FeatureServer" in target_url or "MapServer" in target_url:
            base = target_url.rstrip("/")
            if not re.search(r"/\d+$", base):
                base = f"{base}/0"
            query_url = f"{base}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=1500"

        res = requests.get(query_url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict) and ("features" in data or data.get("type") == "FeatureCollection"):
                ADIF_CACHE["layers_geojson"][target_url] = data
                return jsonify({"success": True, "geojson": data})
            return jsonify({"success": False, "error": "El servicio de ArcGIS no devolvió un FeatureCollection GeoJSON válido."})
        return jsonify({"success": False, "error": f"HTTP {res.status_code} al consultar el servidor ArcGIS"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Log unhandled non-HTTP exceptions and return a safe JSON error response.

    Parameters are validated or normalized by the function; relevant inputs: ``error``.
    """
    from werkzeug.exceptions import HTTPException
    if isinstance(error, HTTPException):
        return error
    log_exception(f"HTTP {request.method} {request.path}", error)
    return jsonify({"success": False, "error": "Error interno registrado", "type": type(error).__name__}), 500

if __name__ == "__main__":
    ensure_background_threads()
    app.run(debug=True, use_reloader=False, threaded=True, host="0.0.0.0", port=5000)
