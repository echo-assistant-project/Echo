"""Everyday calculators: health, fitness, home, cooking, travel. General guidance only — not medical advice."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Literal

from . import ToolError, fmt, tool
from ..words import many

C = "life"
NOTE = " (General guide, not medical advice.)"


@tool(C, ex={"weight_kg": 70, "height_cm": 172}, keys="bmi body mass index weight healthy")
def bmi(weight_kg: float, height_cm: float) -> str:
    """Body mass index with the standard and Asian-Indian categories."""
    if weight_kg <= 0 or height_cm <= 0:
        raise ToolError("weight and height must be positive")
    b = weight_kg / (height_cm / 100) ** 2
    who = "underweight" if b < 18.5 else "normal" if b < 25 else "overweight" if b < 30 else "obese"
    asian = "underweight" if b < 18.5 else "normal" if b < 23 else "overweight" if b < 25 else "obese"
    return f"BMI {b:.1f}: {who} (WHO); {asian} by the Asian-Indian cut-offs.{NOTE}"


@tool(C, ex={"weight_kg": 70, "height_cm": 172, "age": 35, "sex": "male", "activity": "light"}, keys="calories per day bmr tdee diet maintenance")
def daily_calories(weight_kg: float, height_cm: float, age: int, sex: Literal["male", "female"],
                   activity: Literal["sitting", "light", "moderate", "active", "very_active"] = "light") -> str:
    """Calories a day to keep weight steady (Mifflin-St Jeor), plus lose/gain targets."""
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)
    f = {"sitting": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}[activity]
    t = bmr * f
    return f"Resting {round(bmr)} kcal; maintain about {round(t)} kcal/day; lose ~0.5 kg/week at {round(t - 500)}; gain at {round(t + 300)}.{NOTE}"


@tool(C, ex={"height_cm": 165, "sex": "female"}, keys="ideal weight healthy range")
def healthy_weight_range(height_cm: float, sex: Literal["male", "female"] = "male") -> str:
    """Healthy weight range for a height (BMI 18.5–24.9) and the Devine formula."""
    m = height_cm / 100
    inches = height_cm / 2.54
    devine = (50 if sex == "male" else 45.5) + 2.3 * max(inches - 60, 0)
    return f"{18.5 * m * m:.0f}–{24.9 * m * m:.0f} kg by BMI; Devine formula about {devine:.0f} kg.{NOTE}"


@tool(C, ex={"weight_kg": 70}, keys="water intake how much drink daily hydration")
def water_intake(weight_kg: float, active_minutes: int = 0, hot_weather: bool = False) -> str:
    """Rough daily water need."""
    l = weight_kg * 0.033 + active_minutes / 30 * 0.35 + (0.5 if hot_weather else 0)
    return f"About {l:.1f} litres a day (more if you sweat a lot).{NOTE}"


MET = {"walking": 3.5, "brisk walking": 4.3, "running": 9.8, "cycling": 7.5, "swimming": 6.0, "yoga": 2.5, "dancing": 5.0,
       "skipping": 11.0, "gardening": 3.8, "housework": 3.3, "climbing stairs": 8.0, "badminton": 5.5, "cricket": 5.0, "football": 7.0}


@tool(C, ex={"activity": "brisk walking", "minutes": 30, "weight_kg": 70}, keys="calories burned exercise walking running")
def calories_burned(activity: str, minutes: float, weight_kg: float) -> str:
    """Calories burned by an activity (MET estimate)."""
    m = MET.get(activity.strip().lower())
    if m is None:
        raise ToolError("activities: " + ", ".join(MET))
    return f"About {round(m * 3.5 * weight_kg / 200 * minutes)} kcal.{NOTE}"


@tool(C, ex={"age": 45}, keys="heart rate zones max pulse exercise")
def heart_rate_zones(age: int, resting_hr: int = 0) -> dict:
    """Training heart-rate zones (max ≈ 220 − age; Karvonen if resting rate given)."""
    mx = 220 - age
    def z(lo, hi):
        if resting_hr:
            return f"{round(resting_hr + (mx - resting_hr) * lo)}–{round(resting_hr + (mx - resting_hr) * hi)} bpm"
        return f"{round(mx * lo)}–{round(mx * hi)} bpm"
    return {"max": f"{mx} bpm", "easy (50–60%)": z(.5, .6), "fat burn (60–70%)": z(.6, .7), "cardio (70–80%)": z(.7, .8),
            "hard (80–90%)": z(.8, .9), "note": NOTE.strip()}


@tool(C, ex={"last_period": "2026-03-01"}, keys="pregnancy due date expected delivery")
def pregnancy_due_date(last_period: str, cycle_days: int = 28) -> str:
    """Estimated due date (Naegele's rule) and current week of pregnancy."""
    from .t_time import parse_date
    lmp = parse_date(last_period)
    due = lmp + timedelta(days=280 + cycle_days - 28)
    weeks = (date.today() - lmp).days // 7
    return f"Estimated due date {due:%d %B %Y}" + (f"; about week {weeks} now" if 0 <= weeks <= 42 else "") + f".{NOTE}"


@tool(C, ex={"servings_from": 4, "servings_to": 6, "ingredients": ["2 cups rice", "500 g chicken", "1.5 tsp salt"]}, keys="recipe scale servings double half quantity")
def scale_recipe(servings_from: float, servings_to: float, ingredients: list[str]) -> list:
    """Scale recipe quantities to a different number of servings."""
    import re
    f = servings_to / servings_from

    def scale(line):
        m = re.match(r"\s*(\d+(?:\.\d+)?(?:/\d+)?)\s*(.*)", line)
        if not m:
            return line
        q = m.group(1)
        v = (float(q.split("/")[0]) / float(q.split("/")[1])) if "/" in q else float(q)
        return f"{fmt(round(v * f, 2))} {m.group(2)}"
    return [scale(l) for l in ingredients]


@tool(C, ex={"room_length_m": 4, "room_width_m": 3.5}, keys="ac tonnage air conditioner size room")
def ac_size_for_room(room_length_m: float, room_width_m: float, sunny: bool = False, people: int = 2) -> str:
    """Rough AC size (tons) for a room."""
    sqft = room_length_m * room_width_m * 10.764
    tons = sqft / 120 * (1.15 if sunny else 1) + max(people - 2, 0) * 0.1
    return f"Room ≈ {round(sqft)} sq ft → about {max(0.75, round(tons * 4) / 4)} ton AC."


@tool(C, ex={"area_sqft": 1200, "coats": 2}, keys="paint how much litres wall")
def paint_needed(area_sqft: float, coats: int = 2, coverage_sqft_per_litre: float = 100) -> str:
    """Litres of paint for a wall area."""
    l = area_sqft * coats / coverage_sqft_per_litre
    return f"About {math.ceil(l)} litres (for {fmt(area_sqft)} sq ft, {coats} coats)."


@tool(C, ex={"room_length_ft": 12, "room_width_ft": 10, "tile_size_in": 24}, keys="tiles flooring how many")
def tiles_needed(room_length_ft: float, room_width_ft: float, tile_size_in: float = 24, wastage_percent: float = 10) -> str:
    """Number of square floor tiles for a room (with wastage)."""
    per = (tile_size_in / 12) ** 2
    n = math.ceil(room_length_ft * room_width_ft / per * (1 + wastage_percent / 100))
    return f"About {n} tiles of {fmt(tile_size_in)}×{fmt(tile_size_in)} inches."


@tool(C, ex={"distance_km": 10, "minutes": 55}, keys="pace speed running walking per km")
def pace(distance_km: float, minutes: float) -> str:
    """Pace (minutes per km) and speed for a run or walk."""
    p = minutes / distance_km
    return f"Pace {int(p)}:{round((p % 1) * 60):02d} per km; speed {fmt(round(distance_km / (minutes / 60), 2))} km/h."


@tool(C, ex={"distance_km": 350, "speed_kmh": 60, "breaks_minutes": 30}, keys="travel time journey how long drive")
def travel_time(distance_km: float, speed_kmh: float, breaks_minutes: int = 0) -> str:
    """How long a journey takes at an average speed."""
    m = distance_km / speed_kmh * 60 + breaks_minutes
    return f"About {int(m // 60)} h {round(m % 60)} min."


@tool(C, ex={"birth_date": "1990-05-17"}, keys="life stats days lived heartbeats fun")
def life_in_numbers(birth_date: str) -> dict:
    """Fun numbers about your life so far (days, weeks, approximate heartbeats and breaths)."""
    from .t_time import parse_date
    days = (date.today() - parse_date(birth_date)).days
    return {"days": f"{days:,}", "weeks": f"{days // 7:,}", "hours": f"{days * 24:,}", "heartbeats (approx)": f"{days * 24 * 60 * 72:,}",
            "breaths (approx)": f"{days * 24 * 60 * 15:,}", "full moons": f"{round(days / 29.53):,}"}


@tool(C, ex={"medicine_times": ["8:00", "20:00"], "days": 5}, keys="medicine schedule dose times tablets")
def dose_schedule(medicine_times: list[str], days: int = 7) -> list:
    """A printable dose schedule for times each day (to tick off)."""
    from .t_time import parse_time
    ts = [parse_time(t).strftime("%I:%M %p").lstrip("0") for t in medicine_times]
    start = date.today()
    return [f"{(start + timedelta(days=i)):%a %d %b}: " + "  ".join(f"☐ {t}" for t in ts) for i in range(max(1, min(days, 60)))]


@tool(C, ex={"items": ["milk", "bread", "milk", "eggs"]}, keys="shopping list tidy group dedupe")
def tidy_shopping_list(items: list[str]) -> dict:
    """Group a shopping list by aisle and merge repeats."""
    aisles = {"Dairy": "milk curd yogurt paneer cheese butter ghee cream eggs egg", "Bakery": "bread bun cake biscuits rusk",
              "Fruit & veg": "apple banana mango onion tomato potato carrot spinach coriander chilli ginger garlic lemon grapes orange",
              "Grains & pulses": "rice atta flour dal moong toor rava poha oats sugar salt besan",
              "Household": "soap detergent shampoo toothpaste tissue cleaner"}
    out = {}
    for it in dict.fromkeys(i.strip().lower() for i in items if i.strip()):
        a = next((k for k, words in aisles.items() if any(w in it.split() or w == it for w in words.split())), "Other")
        out.setdefault(a, []).append(it)
    return out


@tool(C, ex={"bill_units": [120, 135, 150, 98]}, keys="average monthly usage trend bills")
def usage_trend(bill_units: list[float]) -> str:
    """Average and trend of monthly readings (electricity units, data GB, spending…)."""
    from .t_math import nums
    xs = nums(bill_units)
    avg = sum(xs) / len(xs)
    trend = "rising" if xs[-1] > avg * 1.1 else "falling" if xs[-1] < avg * 0.9 else "steady"
    return f"Average {fmt(round(avg, 1))}; latest {fmt(xs[-1])} ({trend}); highest {fmt(max(xs))}, lowest {fmt(min(xs))}."


@tool(C, ex={"people": 8, "dish": "biryani"}, keys="party food quantity how much cook for guests")
def party_food_quantity(people: int, dish: Literal["biryani", "rice", "chapati", "curry", "dal", "sweets", "snacks", "drinks"] = "rice") -> str:
    """How much food to make for a number of guests (rough averages)."""
    per = {"biryani": (0.15, "kg uncooked rice"), "rice": (0.1, "kg uncooked rice"), "chapati": (3, "chapatis"), "curry": (0.2, "kg"),
           "dal": (0.05, "kg uncooked dal"), "sweets": (2, "pieces"), "snacks": (0.1, "kg"), "drinks": (0.5, "litres")}[dish]
    return f"About {fmt(round(per[0] * people, 2))} {per[1]} for {many(people, 'person')}."
