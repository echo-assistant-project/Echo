"""Maths, statistics, number formats and randomness."""
from __future__ import annotations

import itertools
import math
import random
import secrets
import statistics
from fractions import Fraction
from typing import Literal

from . import ToolError, fmt, tool

C = "math"


def nums(values: list) -> list:
    try:
        out = [float(v) for v in values]
    except (TypeError, ValueError):
        raise ToolError("give a list of numbers")
    if not out:
        raise ToolError("give at least one number")
    return out


@tool(C, ex={"expression": "(15% of 2400) + 3^2"}, keys="calculator compute evaluate arithmetic sum multiply divide")
def calculate(expression: str) -> str:
    """Calculate a maths expression (+ - * / ^, %, sqrt, brackets, 'x% of y')."""
    import re
    from .. import tools
    e = re.sub(r"([\d.]+)\s*(?:%|percent)\s*of\s*([\d.]+)", r"(\1*\2/100)", expression, flags=re.I)
    e = e.replace("×", "*").replace("÷", "/").replace("**", "^")
    out = tools.calc(e)
    if out is None:
        raise ToolError("I couldn't work that out")
    return out


@tool(C, ex={"percent": 18, "value": 2500}, keys="percentage")
def percent_of(percent: float, value: float) -> str:
    """What is P percent of a number."""
    return fmt(value * percent / 100)


@tool(C, ex={"part": 45, "whole": 180}, keys="percentage ratio share")
def what_percent(part: float, whole: float) -> str:
    """What percent one number is of another."""
    if whole == 0:
        raise ToolError("the whole can't be zero")
    return fmt(part / whole * 100, 2) + "%"


@tool(C, ex={"old": 80, "new": 100}, keys="increase decrease growth difference")
def percent_change(old: float, new: float) -> str:
    """Percentage increase or decrease from an old value to a new one."""
    if old == 0:
        raise ToolError("the old value can't be zero")
    ch = (new - old) / abs(old) * 100
    return f"{'up' if ch >= 0 else 'down'} {fmt(abs(ch), 2)}%"


@tool(C, ex={"a": 1920, "b": 1080}, keys="aspect proportion")
def simplify_ratio(a: int, b: int) -> str:
    """Simplify a ratio like 1920:1080 to 16:9."""
    g = math.gcd(a, b) or 1
    return f"{a // g}:{b // g}"


@tool(C, ex={"numbers": [12, 18, 30]}, keys="greatest common divisor hcf")
def gcd(numbers: list[int]) -> str:
    """Greatest common divisor (HCF) of whole numbers."""
    return fmt(math.gcd(*[int(n) for n in numbers]))


@tool(C, ex={"numbers": [4, 6, 10]}, keys="least common multiple")
def lcm(numbers: list[int]) -> str:
    """Least common multiple of whole numbers."""
    return fmt(math.lcm(*[int(n) for n in numbers]))


@tool(C, ex={"n": 97}, keys="prime number check")
def is_prime(n: int) -> str:
    """Is a whole number prime?"""
    if n < 2:
        return f"{n} is not prime."
    for p in range(2, math.isqrt(n) + 1):
        if n % p == 0:
            return f"{n} is not prime; it's divisible by {p}."
    return f"{n} is prime."


@tool(C, ex={"n": 360}, keys="factorise factorize")
def prime_factors(n: int) -> str:
    """Prime factorisation of a whole number."""
    if n < 2 or n > 10**15:
        raise ToolError("use a whole number from 2 to 10^15")
    out, p = [], 2
    while p * p <= n:
        while n % p == 0:
            out.append(p)
            n //= p
        p += 1
    if n > 1:
        out.append(n)
    return " × ".join(map(str, out))


@tool(C, ex={"n": 20}, keys="divisors")
def factors(n: int) -> str:
    """All divisors of a whole number."""
    if not 1 <= n <= 10**12:
        raise ToolError("use a whole number from 1 to 10^12")
    small = [d for d in range(1, math.isqrt(n) + 1) if n % d == 0]
    return ", ".join(map(str, sorted(set(small + [n // d for d in small]))))


@tool(C, ex={"n": 10})
def factorial(n: int) -> str:
    """n! (n factorial)."""
    if not 0 <= n <= 500:
        raise ToolError("use 0 to 500")
    return str(math.factorial(n))


@tool(C, ex={"n": 10}, keys="sequence")
def fibonacci(n: int) -> str:
    """The first n Fibonacci numbers."""
    n = max(1, min(n, 90))
    a, b, out = 0, 1, []
    for _ in range(n):
        out.append(a)
        a, b = b, a + b
    return ", ".join(map(str, out))


@tool(C, ex={"value": 27, "n": 3}, keys="square root cube root")
def nth_root(value: float, n: float = 2) -> str:
    """The n-th root (2 = square root, 3 = cube root)."""
    if n == 0:
        raise ToolError("n can't be zero")
    if value < 0 and int(n) == n and int(n) % 2 == 1:
        return fmt(-((-value) ** (1 / n)))
    if value < 0:
        raise ToolError("even roots of negative numbers aren't real")
    return fmt(value ** (1 / n))


@tool(C, ex={"base": 2, "exponent": 10}, keys="exponent raise")
def power(base: float, exponent: float) -> str:
    """base raised to exponent."""
    r = base ** exponent
    if isinstance(r, complex):
        raise ToolError("that isn't a real number")
    return fmt(r)


@tool(C, ex={"value": 1000, "base": 10}, keys="log ln natural")
def logarithm(value: float, base: float = 10) -> str:
    """Logarithm of a number (base 10 by default; use 2.718281828 for natural log)."""
    if value <= 0 or base <= 0 or base == 1:
        raise ToolError("value and base must be positive, base not 1")
    return fmt(math.log(value, base))


@tool(C, ex={"function": "sin", "angle": 30}, keys="sine cosine tangent trigonometry")
def trig(function: Literal["sin", "cos", "tan", "asin", "acos", "atan"], angle: float, degrees: bool = True) -> str:
    """Trigonometry in degrees (or radians). For asin/acos/atan, 'angle' is the ratio and the answer is an angle."""
    f = getattr(math, function)
    if function.startswith("a"):
        r = f(angle)
        return fmt(math.degrees(r) if degrees else r) + ("°" if degrees else " rad")
    return fmt(f(math.radians(angle) if degrees else angle))


@tool(C, ex={"value": 3.14159, "places": 2})
def round_number(value: float, places: int = 0) -> str:
    """Round a number to some decimal places."""
    return fmt(round(value, max(0, min(places, 12))), 12)


@tool(C, ex={"numbers": [4, 8, 15, 16, 23, 42]}, keys="mean median mode standard deviation variance average range")
def statistics_summary(numbers: list[float]) -> dict:
    """Count, sum, mean, median, mode, min, max, range, standard deviation and quartiles of numbers."""
    xs = nums(numbers)
    out = {"count": len(xs), "sum": fmt(sum(xs)), "mean": fmt(statistics.fmean(xs), 4), "median": fmt(statistics.median(xs), 4),
           "min": fmt(min(xs)), "max": fmt(max(xs)), "range": fmt(max(xs) - min(xs))}
    modes = statistics.multimode(xs)
    out["mode"] = ", ".join(fmt(m) for m in modes[:5]) if len(modes) < len(xs) else "none"
    if len(xs) > 1:
        out["stdev_sample"] = fmt(statistics.stdev(xs), 4)
        out["stdev_population"] = fmt(statistics.pstdev(xs), 4)
        q = statistics.quantiles(xs, n=4)
        out["q1"], out["q3"] = fmt(q[0], 4), fmt(q[2], 4)
    return out


@tool(C, ex={"numbers": [70, 80, 90], "weights": [1, 2, 1]}, keys="weighted average grade")
def weighted_average(numbers: list[float], weights: list[float]) -> str:
    """Weighted average of numbers."""
    xs, ws = nums(numbers), nums(weights)
    if len(xs) != len(ws) or sum(ws) == 0:
        raise ToolError("give one weight per number, not all zero")
    return fmt(sum(x * w for x, w in zip(xs, ws)) / sum(ws), 4)


@tool(C, ex={"x": [1, 2, 3, 4], "y": [2, 4.1, 5.9, 8.2]}, keys="regression trend line fit correlation")
def linear_regression(x: list[float], y: list[float]) -> str:
    """Best-fit line y = a·x + b and the correlation of two lists."""
    xs, ys = nums(x), nums(y)
    if len(xs) != len(ys) or len(xs) < 2:
        raise ToolError("give two lists of the same length (2+ points)")
    slope, intercept = statistics.linear_regression(xs, ys)
    r = statistics.correlation(xs, ys) if len(set(xs)) > 1 and len(set(ys)) > 1 else float("nan")
    return f"y = {fmt(slope, 4)}·x + {fmt(intercept, 4)}; correlation r = {fmt(r, 4)}"


@tool(C, ex={"a": 1, "b": -3, "c": 2}, keys="equation solve roots")
def solve_quadratic(a: float, b: float, c: float) -> str:
    """Solve a·x² + b·x + c = 0."""
    if a == 0:
        if b == 0:
            raise ToolError("that isn't an equation in x")
        return f"x = {fmt(-c / b)}"
    d = b * b - 4 * a * c
    if d < 0:
        re_, im = -b / (2 * a), math.sqrt(-d) / (2 * a)
        return f"No real roots; x = {fmt(re_, 4)} ± {fmt(abs(im), 4)}i"
    r1, r2 = (-b + math.sqrt(d)) / (2 * a), (-b - math.sqrt(d)) / (2 * a)
    return f"x = {fmt(r1, 6)}" if d == 0 else f"x = {fmt(r1, 6)} or x = {fmt(r2, 6)}"


@tool(C, ex={"a1": 2, "b1": 3, "c1": 8, "a2": 1, "b2": -1, "c2": -1}, keys="simultaneous equations solve system")
def solve_linear_2x2(a1: float, b1: float, c1: float, a2: float, b2: float, c2: float) -> str:
    """Solve a1·x + b1·y = c1 and a2·x + b2·y = c2."""
    det = a1 * b2 - a2 * b1
    if det == 0:
        raise ToolError("no single solution (the lines are parallel or the same)")
    return f"x = {fmt((c1 * b2 - c2 * b1) / det)}, y = {fmt((a1 * c2 - a2 * c1) / det)}"


@tool(C, ex={"matrix": [[1, 2], [3, 4]]}, keys="matrix determinant")
def matrix_determinant(matrix: list[list[float]]) -> str:
    """Determinant of a square matrix (up to 6×6)."""
    m = [[float(v) for v in row] for row in matrix]
    n = len(m)
    if n == 0 or n > 6 or any(len(r) != n for r in m):
        raise ToolError("give a square matrix up to 6×6")
    det = 1.0
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(m[r][i]))
        if abs(m[p][i]) < 1e-12:
            return "0"
        if p != i:
            m[i], m[p] = m[p], m[i]
            det = -det
        det *= m[i][i]
        for r in range(i + 1, n):
            f = m[r][i] / m[i][i]
            for c in range(i, n):
                m[r][c] -= f * m[i][c]
    return fmt(det, 6)


@tool(C, ex={"a": [[1, 2], [3, 4]], "b": [[5, 6], [7, 8]]}, keys="matrix product")
def matrix_multiply(a: list[list[float]], b: list[list[float]]) -> list:
    """Multiply two matrices."""
    if not a or not b or len(a[0]) != len(b):
        raise ToolError("columns of the first must equal rows of the second")
    return [[sum(x * y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


@tool(C, ex={"value": "ff", "from_base": 16, "to_base": 2}, keys="binary hexadecimal octal base conversion")
def convert_base(value: str, from_base: int, to_base: int) -> str:
    """Convert a whole number between bases 2–36."""
    if not (2 <= from_base <= 36 and 2 <= to_base <= 36):
        raise ToolError("bases go from 2 to 36")
    n = int(value.strip().lower().removeprefix("0x").removeprefix("0b").removeprefix("0o"), from_base)
    if n == 0:
        return "0"
    digits, neg, n = "0123456789abcdefghijklmnopqrstuvwxyz", n < 0, abs(n)
    out = ""
    while n:
        n, r = divmod(n, to_base)
        out = digits[r] + out
    return ("-" if neg else "") + out


@tool(C, ex={"n": 2026}, keys="roman numerals")
def to_roman(n: int) -> str:
    """Whole number (1–3999) to Roman numerals."""
    if not 1 <= n <= 3999:
        raise ToolError("Roman numerals go from 1 to 3999")
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


@tool(C, ex={"roman": "MMXXVI"}, keys="roman numerals")
def from_roman(roman: str) -> str:
    """Roman numerals to a number."""
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    s = roman.strip().upper()
    if not s or any(ch not in vals for ch in s):
        raise ToolError("that isn't a Roman numeral")
    total = sum(-vals[a] if vals[a] < vals[b] else vals[a] for a, b in zip(s, s[1:] + "I"))
    if to_roman(total) != s:
        raise ToolError(f"{s} isn't written the standard way")
    return str(total)


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _words_99(n):
    return ONES[n] if n < 20 else TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")


def _words_999(n):
    h, r = divmod(n, 100)
    return (ONES[h] + " hundred" + (" and " + _words_99(r) if r else "")) if h else _words_99(r)


def number_words(n: int, system: str = "international") -> str:
    if n < 0:
        return "minus " + number_words(-n, system)
    if n == 0:
        return "zero"
    units = ([(10**7, "crore"), (10**5, "lakh"), (1000, "thousand")] if system == "indian"
             else [(10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand")])
    parts = []
    for v, name in units:
        if n >= v:
            q, n = divmod(n, v)
            parts.append(f"{number_words(q, system) if q >= 1000 else _words_999(q)} {name}")
    if n:
        parts.append(_words_999(n))
    return " ".join(parts)


@tool(C, ex={"n": 1250000, "system": "indian"}, keys="spell number words lakh crore cheque")
def number_to_words(n: int, system: Literal["international", "indian"] = "international") -> str:
    """Write a whole number in words (international: million; indian: lakh, crore)."""
    if abs(n) >= 10**15:
        raise ToolError("that number is too big")
    return number_words(n, system)


@tool(C, ex={"words": "two lakh fifty thousand three hundred"}, keys="parse spoken number")
def words_to_number(words: str) -> str:
    """Turn a number in words ('two lakh fifty thousand') into digits."""
    small = {w: i for i, w in enumerate(ONES)} | {w: i * 10 for i, w in enumerate(TENS) if w != "_"}
    big = {"hundred": 100, "thousand": 1000, "lakh": 10**5, "lakhs": 10**5, "lac": 10**5, "crore": 10**7, "crores": 10**7,
           "million": 10**6, "billion": 10**9, "trillion": 10**12}
    total = current = 0
    for w in words.lower().replace("-", " ").replace(",", " ").split():
        if w in ("and", "a"):
            current = current or (1 if w == "a" else 0)
            continue
        if w in small:
            current += small[w]
        elif w == "hundred":
            current = (current or 1) * 100
        elif w in big:
            total += (current or 1) * big[w]
            current = 0
        elif w.replace(".", "").isdigit():
            current += float(w) if "." in w else int(w)
        else:
            raise ToolError(f"I don't know the word {w!r}")
    return fmt(total + current)


@tool(C, ex={"value": 12345678.5, "style": "indian"}, keys="format commas lakh crore separators")
def format_number(value: float, style: Literal["international", "indian", "compact"] = "international", places: int = 2) -> str:
    """Format a number with separators (12,345,678 / 1,23,45,678) or compactly (12.3M)."""
    if not 0 <= places <= 20:
        raise ToolError("decimal places can be 0 to 20")
    if style == "compact":
        for v, s in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(value) >= v:
                return fmt(round(value / v, 1)) + s
        return fmt(value)
    if style == "international":
        return f"{value:,.{places}f}".rstrip("0").rstrip(".") if places else f"{value:,.0f}"
    neg, value = value < 0, abs(value)
    whole, _, frac = f"{value:.{places}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    out = ",".join(groups + [tail]) if groups else tail
    frac = frac.rstrip("0")
    return ("-" if neg else "") + out + (("." + frac) if frac else "")


@tool(C, ex={"value": 0.000123}, keys="exponent notation")
def scientific_notation(value: float, digits: int = 4) -> str:
    """Write a number in scientific notation."""
    m, e = f"{value:.{max(1, min(digits, 15)) - 1}e}".split("e")
    return f"{m} × 10^{int(e)}"


@tool(C, ex={"value": 0.375}, keys="fraction decimal")
def decimal_to_fraction(value: float, max_denominator: int = 1000) -> str:
    """Closest simple fraction for a decimal."""
    f = Fraction(value).limit_denominator(max(1, max_denominator))
    whole, rem = divmod(f.numerator, f.denominator)
    mixed = f" (= {whole} {rem}/{f.denominator})" if whole and rem and f > 0 else ""
    return f"{f.numerator}/{f.denominator}{mixed}"


@tool(C, ex={"fraction": "3/8"}, keys="fraction decimal")
def fraction_to_decimal(fraction: str) -> str:
    """Fraction (like 3/8 or 1 1/2) to a decimal."""
    parts = fraction.strip().split()
    total = sum(Fraction(p) for p in parts)
    return fmt(float(total), 10)


@tool(C, ex={"n": 10, "r": 3}, keys="nCr nPr choose permutations combinations")
def combinations(n: int, r: int) -> str:
    """Ways to choose r of n: combinations (order doesn't matter) and permutations (order matters)."""
    if not 0 <= r <= n <= 10**6:
        raise ToolError("need 0 ≤ r ≤ n")
    return f"Combinations nCr = {math.comb(n, r):,}; permutations nPr = {math.perm(n, r):,}"


@tool(C, ex={"low": 1, "high": 100}, keys="random number generator pick")
def random_number(low: int = 1, high: int = 100, count: int = 1) -> str:
    """Random whole number(s) between low and high (inclusive)."""
    if low > high:
        low, high = high, low
    count = max(1, min(count, 100))
    return ", ".join(str(low + secrets.randbelow(high - low + 1)) for _ in range(count))


@tool(C, ex={"options": ["pizza", "dosa", "biryani"]}, keys="pick choose decide random")
def random_choice(options: list[str], count: int = 1) -> str:
    """Pick at random from a list of options."""
    opts = [o for o in options if str(o).strip()]
    if not opts:
        raise ToolError("give some options")
    return ", ".join(random.SystemRandom().sample(opts, min(max(1, count), len(opts))))


@tool(C, ex={"items": ["a", "b", "c", "d"]}, keys="random order mix")
def shuffle_list(items: list[str]) -> list:
    """Shuffle a list into random order."""
    out = list(items)
    random.SystemRandom().shuffle(out)
    return out


@tool(C, ex={"people": ["Asha", "Ravi", "Meena", "John", "Sita", "Ali"], "teams": 2}, keys="groups teams split random")
def split_into_teams(people: list[str], teams: int = 2) -> dict:
    """Split people randomly into balanced teams."""
    ppl = list(people)
    random.SystemRandom().shuffle(ppl)
    teams = max(1, min(teams, len(ppl) or 1))
    return {f"Team {i + 1}": ppl[i::teams] for i in range(teams)}


@tool(C, ex={"dice": 2, "sides": 6}, keys="roll dice die")
def roll_dice(dice: int = 1, sides: int = 6) -> str:
    """Roll one or more dice (any number of sides)."""
    dice, sides = max(1, min(dice, 20)), max(2, min(sides, 1000))
    rolls = [1 + secrets.randbelow(sides) for _ in range(dice)]
    return f"{', '.join(map(str, rolls))}" + (f" (total {sum(rolls)})" if dice > 1 else "")


@tool(C, ex={}, keys="heads tails toss")
def flip_coin(times: int = 1) -> str:
    """Flip a coin."""
    flips = ["heads" if secrets.randbelow(2) else "tails" for _ in range(max(1, min(times, 50)))]
    return ", ".join(flips) + (f" ({flips.count('heads')} heads)" if len(flips) > 1 else "")


@tool(C, ex={"items": ["a", "b", "c"]}, keys="arrangements orders")
def list_permutations(items: list[str], limit: int = 50) -> list:
    """All orderings of a few items (up to 7)."""
    if len(items) > 7:
        raise ToolError("up to 7 items")
    return [" ".join(p) for p in itertools.islice(itertools.permutations(items), max(1, min(limit, 5040)))]


@tool(C, ex={"value": 37, "low": 0, "high": 100, "new_low": 0, "new_high": 1}, keys="scale map range normalize")
def rescale(value: float, low: float, high: float, new_low: float, new_high: float) -> str:
    """Map a value from one range to another (e.g. a score out of 37 to a percentage)."""
    if high == low:
        raise ToolError("the range can't be empty")
    return fmt(new_low + (value - low) * (new_high - new_low) / (high - low), 6)


@tool(C, ex={"marks": [78, 85, 92], "out_of": [100, 100, 100]}, keys="marks percentage grade total exam")
def marks_percentage(marks: list[float], out_of: list[float]) -> str:
    """Total marks and percentage from marks and maximums."""
    m, o = nums(marks), nums(out_of)
    if len(o) == 1:
        o = o * len(m)
    if len(m) != len(o) or sum(o) == 0:
        raise ToolError("give one maximum per mark")
    return f"{fmt(sum(m))} out of {fmt(sum(o))} = {fmt(sum(m) / sum(o) * 100, 2)}%"


@tool(C, ex={"a": [0, 0], "b": [3, 4]}, keys="distance points pythagoras")
def point_distance(a: list[float], b: list[float]) -> str:
    """Straight-line distance between two points (2D or 3D)."""
    if len(a) != len(b):
        raise ToolError("points need the same number of coordinates")
    return fmt(math.dist(nums(a), nums(b)), 6)


@tool(C, ex={"shape": "circle", "a": 7}, keys="area perimeter geometry circle rectangle triangle")
def shape_area(shape: Literal["circle", "square", "rectangle", "triangle", "trapezium", "ellipse", "sphere", "cylinder", "cone", "cube"],
               a: float, b: float = 0, c: float = 0) -> str:
    """Area/perimeter (2D) or volume/surface (3D). circle a=radius; rectangle a,b; triangle a=base b=height;
    trapezium a,b parallel sides c=height; ellipse a,b semi-axes; sphere a=radius; cylinder/cone a=radius b=height; cube a=side."""
    pi = math.pi
    if shape == "circle":
        return f"area {fmt(pi * a * a, 4)}, circumference {fmt(2 * pi * a, 4)}"
    if shape == "square":
        return f"area {fmt(a * a, 4)}, perimeter {fmt(4 * a, 4)}"
    if shape == "rectangle":
        return f"area {fmt(a * b, 4)}, perimeter {fmt(2 * (a + b), 4)}"
    if shape == "triangle":
        return f"area {fmt(0.5 * a * b, 4)}"
    if shape == "trapezium":
        return f"area {fmt((a + b) / 2 * c, 4)}"
    if shape == "ellipse":
        return f"area {fmt(pi * a * b, 4)}"
    if shape == "sphere":
        return f"volume {fmt(4 / 3 * pi * a ** 3, 4)}, surface {fmt(4 * pi * a * a, 4)}"
    if shape == "cylinder":
        return f"volume {fmt(pi * a * a * b, 4)}, surface {fmt(2 * pi * a * (a + b), 4)}"
    if shape == "cone":
        return f"volume {fmt(pi * a * a * b / 3, 4)}, surface {fmt(pi * a * (a + math.hypot(a, b)), 4)}"
    return f"volume {fmt(a ** 3, 4)}, surface {fmt(6 * a * a, 4)}"
