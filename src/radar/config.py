"""Immutable application configuration and source catalogues.

Runtime state and secrets deliberately remain outside this module.
"""
from __future__ import annotations

import os
from pathlib import Path

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) RenfeAdifTracker/6.0",
    "Accept": "application/json, text/csv, */*"
}


CKAN_BASE = "https://data.renfe.com/api/3/action/package_show?id="


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


OPERATOR_CONFIG_FILE = os.path.join(OPEN_ACCESS_CACHE_DIR, "operator_config.json")


OPEN_ACCESS_CACHE_TTL = 24 * 3600


OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]


OVERPASS_CACHE_TTL = 30 * 24 * 3600


OVERPASS_FAILURE_COOLDOWN = 180


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


FEVE_LINE_CODES = {
    "20": {"C4", "C5", "C6", "C7", "C8", "C9"},   # Asturias AM
    "60": {"C4", "R3B", "B1"},                         # Bilbao AM
    "61": {"R3", "E1", "E2"},                          # Gipuzkoa AM
    "62": {"C2", "C3", "R2", "R3"},                  # Cantabria AM
}

