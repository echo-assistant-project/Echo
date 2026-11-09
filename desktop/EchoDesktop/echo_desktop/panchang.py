"""Tithi, paksha and lunar month for any date, computed from the Sun's and Moon's positions (no internet, no AI).

Positions: Meeus, "Astronomical Algorithms" (ch. 25 Sun, ch. 47 Moon, main terms; about 0.01° — a tithi is 12° of
Moon-Sun elongation, so the only uncertainty is a few minutes around a tithi's start or end). Hindu calendar rules:
the tithi that prevails at local sunrise names the day; the amanta month is named from the Sun's sidereal sign
(Lahiri ayanamsa) at the new moon that starts it; two new moons in one sign make an Adhika (extra) month.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

TITHIS = ("Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami", "Ashtami", "Navami",
          "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi")
# amanta month named by the sidereal sign the Sun is in at the new moon that begins it (Meena → Chaitra, …)
MONTHS = ("Vaishakha", "Jyeshtha", "Ashadha", "Shravana", "Bhadrapada", "Ashwin", "Kartika", "Margashirsha", "Pausha",
          "Magha", "Phalguna", "Chaitra")            # index = sign (0 Mesha … 11 Meena)
IST = timezone(timedelta(hours=5, minutes=30))
NEW_DELHI = (28.6139, 77.2090)

_MOON = (  # (D, M, M', F, coefficient in 1e-6 degrees) — Meeus table 47.A, terms over 0.003°
    (0, 0, 1, 0, 6288774), (2, 0, -1, 0, 1274027), (2, 0, 0, 0, 658314), (0, 0, 2, 0, 213618), (0, 1, 0, 0, -185116),
    (0, 0, 0, 2, -114332), (2, 0, -2, 0, 58793), (2, -1, -1, 0, 57066), (2, 0, 1, 0, 53322), (2, -1, 0, 0, 45758),
    (0, 1, -1, 0, -40923), (1, 0, 0, 0, -34720), (0, 1, 1, 0, -30383), (2, 0, 0, -2, 15327), (0, 0, 1, 2, -12528),
    (0, 0, 1, -2, 10980), (4, 0, -1, 0, 10675), (0, 0, 3, 0, 10034), (4, 0, -2, 0, 8548), (2, 1, -1, 0, -7888),
    (2, 1, 0, 0, -6766), (1, 0, -1, 0, -5163), (1, 1, 0, 0, 4987), (2, -1, 1, 0, 4036), (2, 0, 2, 0, 3994),
    (4, 0, 0, 0, 3861), (2, 0, -3, 0, 3665), (0, 1, -2, 0, -2689), (2, 0, -1, 2, -2602), (2, -1, -2, 0, 2390),
    (1, 0, 1, 0, -2348), (2, -2, 0, 0, 2236), (0, 1, 2, 0, -2120), (0, 2, 0, 0, -2069), (2, -2, -1, 0, 2048),
    (2, 0, 1, -2, -1773), (2, 0, 0, 2, -1595), (4, -1, -1, 0, 1215), (0, 0, 2, 2, -1110), (3, 0, -1, 0, -892),
    (2, 1, 1, 0, -810), (4, -1, -2, 0, 759), (0, 2, -1, 0, -713), (2, 2, -1, 0, -700), (2, 1, -2, 0, 691),
    (2, -1, 0, -2, 596), (4, 0, 1, 0, 549), (0, 0, 4, 0, 537), (4, -1, 0, 0, 520), (1, 0, -2, 0, -487))


def _jd(t: datetime) -> float:
    t = t.astimezone(timezone.utc)
    return 2440587.5 + t.timestamp() / 86400.0


def _sun(T: float) -> float:
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = math.radians(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M) + (0.019993 - 0.000101 * T) * math.sin(2 * M)
         + 0.000289 * math.sin(3 * M))
    omega = math.radians(125.04 - 1934.136 * T)
    return (L0 + C - 0.00569 - 0.00478 * math.sin(omega)) % 360          # apparent longitude


def _moon(T: float) -> float:
    Lp = 218.3164477 + 481267.88123421 * T - 0.0015786 * T * T
    D = 297.8501921 + 445267.1114034 * T - 0.0018819 * T * T
    M = 357.5291092 + 35999.0502909 * T - 0.0001536 * T * T
    Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T * T
    F = 93.2720950 + 483202.0175233 * T - 0.0036539 * T * T
    E = 1 - 0.002516 * T - 0.0000074 * T * T
    s = 0.0
    for d, m, mp, f, c in _MOON:
        arg = math.radians(d * D + m * M + mp * Mp + f * F)
        s += c * (E ** abs(m)) * math.sin(arg)
    A1, A2 = math.radians(119.75 + 131.849 * T), math.radians(53.09 + 479264.290 * T)
    s += 3958 * math.sin(A1) + 1962 * math.sin(math.radians(Lp) - math.radians(F)) + 318 * math.sin(A2)
    omega = math.radians(125.04452 - 1934.136261 * T)
    return (Lp + s / 1e6 - 0.00478 * math.sin(omega)) % 360              # apparent (nutation in longitude)


def elongation(t: datetime) -> float:
    """Moon minus Sun longitude, 0-360° (0 = new moon, 180 = full moon)."""
    T = (_jd(t) - 2451545.0) / 36525
    return (_moon(T) - _sun(T)) % 360


def sun_sidereal(t: datetime) -> float:
    T = (_jd(t) - 2451545.0) / 36525
    ayanamsa = 23.853 + (_jd(t) - 2451545.0) / 365.25 * 50.29 / 3600     # Lahiri: 23.853° at J2000, +50.29"/year
    return (_sun(T) - ayanamsa) % 360


def sunrise(day: date, place=NEW_DELHI, tz=IST) -> datetime:
    """Local sunrise (NOAA method, upper limb with refraction, ±1 min)."""
    lat, lon = place
    n = day.toordinal() - date(day.year, 1, 1).toordinal() + 1
    for _ in range(2):                                   # refine once with the first estimate's hour
        g = 2 * math.pi / 365 * (n - 1 + (6 - lon / 15) / 24)
        eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                       - 0.040849 * math.sin(2 * g))
        dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
               + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
        ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(math.radians(lat)) * math.cos(dec))
                                    - math.tan(math.radians(lat)) * math.tan(dec)))
        minutes = 720 - 4 * (lon + ha) - eq             # UTC minutes after midnight
    utc = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return utc.astimezone(tz)


def _cross(t0: datetime, target: float, forward: bool = True) -> datetime:
    """The moment the elongation reaches `target` degrees, searching forward (or back) from t0 (bisection, ~1 min)."""
    step = timedelta(hours=6) * (1 if forward else -1)
    def ahead(t):                                        # degrees still to go (forward) / since (back), 0-360
        e = elongation(t)
        return (target - e) % 360 if forward else (e - target) % 360
    a, da = t0, ahead(t0)
    for _ in range(200):                                 # ~50 days at most
        b = a + step
        db = ahead(b)
        if db > da:                                      # wrapped past the target between a and b
            break
        a, da = b, db
    else:
        return a
    lo, hi = (a, b) if forward else (b, a)
    for _ in range(30):
        mid = lo + (hi - lo) / 2
        e = elongation(mid)
        passed = ((e - target) % 360) < 180
        if passed:
            hi = mid
        else:
            lo = mid
    return hi


def tithi_at(t: datetime) -> int:
    """1-30: 1-15 Shukla (15 = Purnima), 16-30 Krishna (30 = Amavasya)."""
    return int(elongation(t) // 12) + 1


def tithi_name(n: int) -> str:
    if n == 15:
        return "Shukla Purnima"
    if n == 30:
        return "Krishna Amavasya"
    return ("Shukla " if n <= 15 else "Krishna ") + TITHIS[(n - 1) % 15]


def month_at(t: datetime) -> str:
    """Amanta month for the moment t: named from the Sun's sign at the new moon that began it."""
    nm = _cross(t, 0.0, forward=False)
    nxt = _cross(t + timedelta(hours=1), 0.0, forward=True)
    s1, s2 = int(sun_sidereal(nm) // 30), int(sun_sidereal(nxt) // 30)
    name = MONTHS[s1]
    return ("Adhika " + MONTHS[(s1 + 1) % 12]) if s1 == s2 else name


def day_panchang(day: date, place=NEW_DELHI, tz=IST) -> dict:
    """The tithi at sunrise (which names the day), when it ends, and the next one."""
    rise = sunrise(day, place, tz)
    n = tithi_at(rise)
    end = _cross(rise, (n * 12) % 360, forward=True)
    month = month_at(rise)
    # North India (purnimanta) starts each month after the full moon: its Krishna paksha belongs to the next month
    base = month.replace("Adhika ", "")
    north = MONTHS[(MONTHS.index(base) + 1) % 12] if n > 15 else base
    return {"date": day, "sunrise": rise, "tithi": n, "name": tithi_name(n), "ends": end.astimezone(tz),
            "next": tithi_name(n % 30 + 1), "month": month, "month_north": north}
