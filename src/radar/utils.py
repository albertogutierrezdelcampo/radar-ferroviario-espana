"""Pure, reusable helpers with no Flask or network dependencies."""
from __future__ import annotations

import math
import re
from datetime import datetime

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


def _gtfs_date(value):
    """Perform the documented application operation while preserving current API contracts.

    Parameters are validated or normalized by the function; relevant inputs: ``value``.
    """
    value = str(value or "").strip()
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except Exception:
        return None


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

