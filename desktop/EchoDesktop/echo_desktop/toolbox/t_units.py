"""Unit conversions, one tool per kind of quantity (so the AI picks the right one and the units are checked)."""
from __future__ import annotations

from . import ToolError, fmt, tool

C = "units"


def _table(table: dict, value: float, from_unit: str, to_unit: str, label: str) -> str:
    aliases = {}
    for k, (factor, names) in table.items():
        for n in (k,) + names:
            aliases[n.lower()] = k
    a, b = aliases.get(from_unit.strip().lower()), aliases.get(to_unit.strip().lower())
    if a is None or b is None:
        raise ToolError(f"{label} units I know: " + ", ".join(table))
    out = value * table[a][0] / table[b][0]
    return f"{fmt(value)} {a} = {fmt(out, 6)} {b}"


LENGTH = {"mm": (0.001, ("millimetre", "millimeter", "millimetres", "millimeters")), "cm": (0.01, ("centimetre", "centimeter", "cms")),
          "m": (1, ("metre", "meter", "metres", "meters")), "km": (1000, ("kilometre", "kilometer", "kilometres", "kms")),
          "inch": (0.0254, ("in", "inches")), "foot": (0.3048, ("ft", "feet")), "yard": (0.9144, ("yd", "yards")),
          "mile": (1609.344, ("mi", "miles")), "nautical mile": (1852, ("nmi",)), "micrometre": (1e-6, ("micron", "µm"))}
MASS = {"mg": (1e-6, ("milligram", "milligrams")), "g": (0.001, ("gram", "grams", "gm")), "kg": (1, ("kilogram", "kilograms", "kilo", "kilos")),
        "tonne": (1000, ("ton", "t", "metric ton")), "lb": (0.45359237, ("pound", "pounds", "lbs")), "oz": (0.028349523125, ("ounce", "ounces")),
        "stone": (6.35029318, ("st",)), "quintal": (100, ("qtl",)), "tola": (0.0116638, ("tolas",)), "carat": (0.0002, ("ct", "carats"))}
VOLUME = {"ml": (0.001, ("millilitre", "milliliter")), "l": (1, ("litre", "liter", "litres", "liters")), "m3": (1000, ("cubic metre", "cubic meter")),
          "tsp": (0.00492892, ("teaspoon", "teaspoons")), "tbsp": (0.0147868, ("tablespoon", "tablespoons")),
          "cup": (0.24, ("cups",)), "fl oz": (0.0295735, ("fluid ounce", "fluid ounces")), "pint": (0.473176, ("pints", "us pint")),
          "gallon": (3.78541, ("gal", "gallons", "us gallon")), "uk gallon": (4.54609, ("imperial gallon",))}
AREA = {"sq m": (1, ("m2", "square metre", "square meter", "square metres")), "sq km": (1e6, ("km2", "square kilometre")),
        "sq ft": (0.09290304, ("ft2", "square foot", "square feet")), "sq yd": (0.83612736, ("square yard", "square yards", "gaj")),
        "acre": (4046.8564224, ("acres",)), "hectare": (10000, ("ha", "hectares")), "sq mile": (2589988.110336, ("square mile",)),
        "cent": (40.468564224, ("cents",)), "guntha": (101.17141056, ("gunta", "gunthas")), "bigha (UP)": (2529.285, ("bigha",))}
SPEED = {"m/s": (1, ("mps", "metres per second")), "km/h": (1 / 3.6, ("kmph", "kph", "kilometres per hour")),
         "mph": (0.44704, ("miles per hour",)), "knot": (0.514444, ("knots", "kn")), "ft/s": (0.3048, ("feet per second",))}
TIME = {"second": (1, ("s", "sec", "seconds")), "minute": (60, ("min", "minutes")), "hour": (3600, ("h", "hr", "hours")),
        "day": (86400, ("days",)), "week": (604800, ("weeks",)), "month": (2629746, ("months",)), "year": (31556952, ("years", "yr")),
        "millisecond": (0.001, ("ms", "milliseconds"))}
DATA = {"bit": (0.125, ("bits",)), "byte": (1, ("b", "bytes")), "kb": (1000, ("kilobyte", "kilobytes")), "mb": (1e6, ("megabyte", "megabytes")),
        "gb": (1e9, ("gigabyte", "gigabytes")), "tb": (1e12, ("terabyte", "terabytes")), "kib": (1024, ("kibibyte",)),
        "mib": (1024 ** 2, ("mebibyte",)), "gib": (1024 ** 3, ("gibibyte",)), "tib": (1024 ** 4, ("tebibyte",))}
ENERGY = {"joule": (1, ("j", "joules")), "kj": (1000, ("kilojoule", "kilojoules")), "calorie": (4.184, ("cal", "calories")),
          "kcal": (4184, ("kilocalorie", "kilocalories", "food calorie")), "wh": (3600, ("watt hour", "watt hours")),
          "kwh": (3.6e6, ("kilowatt hour", "unit", "units")), "btu": (1055.06, ("btus",)), "ev": (1.602176634e-19, ("electronvolt",))}
PRESSURE = {"pa": (1, ("pascal",)), "kpa": (1000, ("kilopascal",)), "bar": (1e5, ("bars",)), "atm": (101325, ("atmosphere",)),
            "psi": (6894.757, ("pounds per square inch",)), "mmhg": (133.322, ("mm of mercury", "torr"))}
POWER = {"w": (1, ("watt", "watts")), "kw": (1000, ("kilowatt", "kilowatts")), "hp": (745.7, ("horsepower", "bhp")),
         "ton (ac)": (3516.85, ("ton", "tr", "refrigeration ton", "ac ton")), "btu/h": (0.29307107, ("btu per hour",))}
ANGLE = {"degree": (1, ("deg", "degrees", "°")), "radian": (57.29577951308232, ("rad", "radians")),
         "gradian": (0.9, ("grad", "gon")), "turn": (360, ("turns", "revolution"))}


def _mk(name, table, label, ex, keys):
    def fn(value: float, from_unit: str, to_unit: str) -> str:
        return _table(table, value, from_unit, to_unit, label)
    fn.__doc__ = f"Convert {label} ({', '.join(table)})."
    fn.__name__ = name
    tool(C, ex=ex, keys=keys, name=name)(fn)


_mk("convert_length", LENGTH, "length/distance", {"value": 5, "from_unit": "km", "to_unit": "miles"}, "distance height feet inches metres")
_mk("convert_weight", MASS, "weight/mass", {"value": 70, "from_unit": "kg", "to_unit": "lb"}, "mass pounds kilos grams tola")
_mk("convert_volume", VOLUME, "volume/liquid", {"value": 2, "from_unit": "cups", "to_unit": "ml"}, "litres gallons cups liquid")
_mk("convert_area", AREA, "area/land", {"value": 1, "from_unit": "acre", "to_unit": "sq ft"}, "land acres hectares square feet gaj cent")
_mk("convert_speed", SPEED, "speed", {"value": 100, "from_unit": "km/h", "to_unit": "mph"}, "velocity kmph mph")
_mk("convert_duration", TIME, "time spans", {"value": 3, "from_unit": "hours", "to_unit": "minutes"}, "hours minutes seconds duration")
_mk("convert_data_size", DATA, "data sizes", {"value": 1.5, "from_unit": "GB", "to_unit": "MB"}, "bytes megabytes gigabytes storage")
_mk("convert_energy", ENERGY, "energy", {"value": 500, "from_unit": "kcal", "to_unit": "kJ"}, "calories joules kwh units electricity")
_mk("convert_pressure", PRESSURE, "pressure", {"value": 32, "from_unit": "psi", "to_unit": "bar"}, "tyre tire psi bar")
_mk("convert_power", POWER, "power", {"value": 1.5, "from_unit": "ton (ac)", "to_unit": "kW"}, "watts horsepower ac tonnage")
_mk("convert_angle", ANGLE, "angles", {"value": 90, "from_unit": "degrees", "to_unit": "radians"}, "degrees radians")


@tool(C, ex={"value": 98.6, "from_unit": "F", "to_unit": "C"}, keys="celsius fahrenheit kelvin fever")
def convert_temperature(value: float, from_unit: str, to_unit: str) -> str:
    """Convert temperatures between Celsius, Fahrenheit and Kelvin."""
    norm = {"c": "C", "celsius": "C", "centigrade": "C", "f": "F", "fahrenheit": "F", "k": "K", "kelvin": "K"}
    a, b = norm.get(from_unit.strip().lower().strip("°")), norm.get(to_unit.strip().lower().strip("°"))
    if not a or not b:
        raise ToolError("use C, F or K")
    c = value if a == "C" else (value - 32) * 5 / 9 if a == "F" else value - 273.15
    out = c if b == "C" else c * 9 / 5 + 32 if b == "F" else c + 273.15
    return f"{fmt(value)}°{a} = {fmt(round(out, 2))}°{b}"


@tool(C, ex={"value": 15, "from_unit": "km/l", "to_unit": "l/100km"}, keys="mileage fuel efficiency mpg")
def convert_fuel_economy(value: float, from_unit: str, to_unit: str) -> str:
    """Convert fuel economy between km/l, l/100km, mpg (US) and mpg (UK)."""
    to_kml = {"km/l": lambda v: v, "kmpl": lambda v: v, "l/100km": lambda v: 100 / v, "mpg": lambda v: v * 0.425144,
              "mpg (us)": lambda v: v * 0.425144, "mpg (uk)": lambda v: v * 0.354006}
    from_kml = {"km/l": lambda v: v, "kmpl": lambda v: v, "l/100km": lambda v: 100 / v, "mpg": lambda v: v / 0.425144,
                "mpg (us)": lambda v: v / 0.425144, "mpg (uk)": lambda v: v / 0.354006}
    a, b = from_unit.strip().lower(), to_unit.strip().lower()
    if a not in to_kml or b not in from_kml or value <= 0:
        raise ToolError("use km/l, l/100km, mpg (us) or mpg (uk), with a positive value")
    return f"{fmt(value)} {a} = {fmt(round(from_kml[b](to_kml[a](value)), 2))} {b}"


# grams per (US) cup, for cooking
DENSITY = {"water": 240, "milk": 245, "flour": 125, "maida": 125, "atta": 120, "wheat flour": 120, "sugar": 200, "brown sugar": 220,
           "powdered sugar": 120, "rice": 185, "basmati rice": 185, "butter": 227, "ghee": 220, "oil": 218, "honey": 340,
           "salt": 292, "rava": 170, "semolina": 170, "besan": 92, "gram flour": 92, "oats": 90, "cocoa": 85, "yogurt": 245,
           "curd": 245, "toor dal": 200, "moong dal": 200, "poha": 80, "grated coconut": 80, "cashews": 140, "almonds": 140}


@tool(C, ex={"amount": 2, "unit": "cups", "ingredient": "flour"}, keys="cups grams cooking baking kitchen measure")
def cups_to_grams(amount: float, unit: str, ingredient: str) -> str:
    """Kitchen conversion: cups / tablespoons / teaspoons of an ingredient to grams (or grams to cups)."""
    ing = ingredient.strip().lower()
    per_cup = DENSITY.get(ing)
    if per_cup is None:
        raise ToolError("ingredients I know: " + ", ".join(DENSITY))
    u = unit.strip().lower().rstrip("s")
    cup_frac = {"cup": 1, "tablespoon": 1 / 16, "tbsp": 1 / 16, "teaspoon": 1 / 48, "tsp": 1 / 48}
    if u in cup_frac:
        return f"{fmt(amount)} {unit} of {ing} ≈ {fmt(round(amount * cup_frac[u] * per_cup))} g"
    if u in ("g", "gram"):
        return f"{fmt(amount)} g of {ing} ≈ {fmt(round(amount / per_cup, 2))} cups"
    raise ToolError("units: cups, tbsp, tsp or grams")


@tool(C, ex={"value": 180, "from_unit": "C"}, keys="oven gas mark baking temperature")
def oven_temperature(value: float, from_unit: str = "C") -> str:
    """Oven temperature in °C, °F and gas mark."""
    c = value if from_unit.upper().startswith("C") else (value - 32) * 5 / 9 if from_unit.upper().startswith("F") else None
    if from_unit.lower().startswith("gas"):
        c = {1: 140, 2: 150, 3: 170, 4: 180, 5: 190, 6: 200, 7: 220, 8: 230, 9: 240}.get(int(value))
    if c is None:
        raise ToolError("from_unit is C, F or gas")
    marks = [(140, 1), (150, 2), (170, 3), (180, 4), (190, 5), (200, 6), (220, 7), (230, 8), (240, 9)]
    gas = min(marks, key=lambda m: abs(m[0] - c))[1]
    return f"{round(c)}°C = {round(c * 9 / 5 + 32)}°F ≈ gas mark {gas}"


SHOE = [(35, 2.5, 5, 22.0), (36, 3.5, 6, 22.9), (37, 4, 6.5, 23.5), (38, 5, 7.5, 24.1), (39, 6, 8.5, 24.8), (40, 6.5, 9, 25.4),
        (41, 7.5, 10, 26.0), (42, 8, 10.5, 26.7), (43, 9, 11.5, 27.3), (44, 9.5, 12, 27.9), (45, 10.5, 13, 28.6), (46, 11.5, 14, 29.2)]


@tool(C, ex={"size": 9, "system": "uk"}, keys="footwear size chart")
def shoe_size(size: float, system: str = "uk") -> str:
    """Adult shoe size across EU, UK/India, US (men's) and foot length in cm (approximate)."""
    col = {"eu": 0, "uk": 1, "india": 1, "in": 1, "us": 2, "cm": 3}.get(system.strip().lower())
    if col is None:
        raise ToolError("system: eu, uk, india, us or cm")
    row = min(SHOE, key=lambda r: abs(r[col] - size))
    return f"EU {row[0]} ≈ UK/India {row[1]} ≈ US men's {row[2]} ≈ foot {row[3]} cm (sizes vary by brand)"
