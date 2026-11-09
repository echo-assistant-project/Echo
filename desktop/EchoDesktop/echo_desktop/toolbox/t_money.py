"""Money: loans, savings, investments, GST, prices, bills. Live rates use the internet."""
from __future__ import annotations

from typing import Literal

from . import ToolError, fmt, tool
from ..words import many

C = "money"


def rs(x: float) -> str:
    """₹6,20,274 for amounts of ₹1,000 or more (whole rupees, as banks state EMIs and maturities); ₹96.50 below that
    (paise always two digits, never "₹69,118.4")."""
    from .t_math import format_number
    if abs(x) >= 1000:
        return "₹" + format_number(round(x), "indian", 0)
    s = format_number(round(x, 2), "indian", 2)
    whole, _, frac = s.partition(".")
    return "₹" + (f"{whole}.{frac:0<2}" if frac else whole)


def _emi(p, annual_rate, months):
    r = annual_rate / 12 / 100
    return p / months if r == 0 else p * r * (1 + r) ** months / ((1 + r) ** months - 1)


@tool(C, ex={"principal": 1000000, "annual_rate": 8.5, "years": 20}, keys="loan emi home car monthly payment")
def loan_emi(principal: float, annual_rate: float, years: float) -> str:
    """Monthly EMI, total interest and total paid for a loan."""
    n = round(years * 12)
    if principal <= 0 or n <= 0 or annual_rate < 0:
        raise ToolError("need a positive amount and term")
    e = _emi(principal, annual_rate, n)
    return f"EMI {rs(e)} a month for {n} months; total interest {rs(e * n - principal)}; total paid {rs(e * n)}."


@tool(C, ex={"principal": 500000, "annual_rate": 9, "years": 3}, keys="amortization schedule loan yearly balance")
def loan_schedule(principal: float, annual_rate: float, years: float) -> list:
    """Year-by-year loan schedule: principal and interest paid, balance left."""
    n, r = round(years * 12), annual_rate / 12 / 100
    e, bal, rows = _emi(principal, annual_rate, n), principal, []
    for y in range(1, (n + 11) // 12 + 1):
        pi = ii = 0.0
        for _ in range(min(12, n - (y - 1) * 12)):
            interest = bal * r
            ii += interest
            pi += e - interest
            bal -= e - interest
        rows.append({"year": y, "principal_paid": rs(pi), "interest_paid": rs(ii), "balance": rs(max(bal, 0))})
    return rows


@tool(C, ex={"principal": 2000000, "annual_rate": 8.5, "emi": 20000}, keys="loan how long tenure")
def loan_tenure(principal: float, annual_rate: float, emi: float) -> str:
    """How long it takes to repay a loan with a given monthly EMI."""
    import math
    r = annual_rate / 12 / 100
    if emi <= principal * r:
        raise ToolError("that EMI doesn't even cover the monthly interest")
    n = principal / emi if r == 0 else -math.log(1 - principal * r / emi) / math.log(1 + r)
    n = math.ceil(n)
    return f"{many(n, 'month')} ({many(n // 12, 'year')} {many(n % 12, 'month')}); total interest about {rs(emi * n - principal)}."


@tool(C, ex={"principal": 100000, "annual_rate": 7, "years": 5, "per_year": 4}, keys="compound interest growth")
def compound_interest(principal: float, annual_rate: float, years: float, per_year: int = 1) -> str:
    """Compound interest: final amount and interest earned (per_year = compounding times a year, 4 = quarterly)."""
    per_year = max(1, per_year)
    amt = principal * (1 + annual_rate / 100 / per_year) ** (per_year * years)
    return f"After {fmt(years)} years: {rs(amt)} (interest {rs(amt - principal)})."


@tool(C, ex={"principal": 50000, "annual_rate": 6, "years": 2}, keys="simple interest")
def simple_interest(principal: float, annual_rate: float, years: float) -> str:
    """Simple interest and final amount."""
    i = principal * annual_rate * years / 100
    return f"Interest {rs(i)}; total {rs(principal + i)}."


@tool(C, ex={"monthly": 5000, "annual_return": 12, "years": 10}, keys="sip mutual fund monthly investment")
def sip_future_value(monthly: float, annual_return: float, years: float) -> str:
    """What a monthly SIP grows to (expected return, compounded monthly, paid at the start of each month)."""
    n, r = round(years * 12), annual_return / 12 / 100
    fv = monthly * n if r == 0 else monthly * ((1 + r) ** n - 1) / r * (1 + r)
    return f"Invested {rs(monthly * n)}; could grow to {rs(fv)} (gain {rs(fv - monthly * n)}). Returns aren't guaranteed."


@tool(C, ex={"goal": 2500000, "annual_return": 12, "years": 15}, keys="sip target goal how much monthly")
def sip_needed_for_goal(goal: float, annual_return: float, years: float) -> str:
    """Monthly SIP needed to reach a goal amount."""
    n, r = round(years * 12), annual_return / 12 / 100
    m = goal / n if r == 0 else goal / (((1 + r) ** n - 1) / r * (1 + r))
    return f"About {rs(m)} a month for {n} months."


@tool(C, ex={"amount": 100000, "annual_return": 10, "years": 10}, keys="lumpsum one time investment future value")
def lumpsum_future_value(amount: float, annual_return: float, years: float) -> str:
    """What a one-time investment grows to."""
    return f"{rs(amount * (1 + annual_return / 100) ** years)} after {fmt(years)} years."


@tool(C, ex={"start": 100000, "end": 250000, "years": 6}, keys="cagr annual growth rate returns")
def cagr(start: float, end: float, years: float) -> str:
    """Compound annual growth rate between two values."""
    if start <= 0 or end <= 0 or years <= 0:
        raise ToolError("values and years must be positive")
    return fmt(((end / start) ** (1 / years) - 1) * 100, 2) + "% a year"


@tool(C, ex={"cost": 40000, "gain": 52000}, keys="return on investment profit")
def roi(cost: float, gain: float) -> str:
    """Return on investment."""
    if cost == 0:
        raise ToolError("cost can't be zero")
    return f"ROI {fmt((gain - cost) / cost * 100, 2)}% (profit {rs(gain - cost)})."


@tool(C, ex={"amount": 100000, "inflation": 6, "years": 10}, keys="inflation future cost purchasing power")
def inflation_adjust(amount: float, inflation: float, years: float) -> str:
    """Future cost of something today, and today's value of money in the future."""
    f = (1 + inflation / 100) ** years
    return f"{rs(amount)} today will cost about {rs(amount * f)} in {fmt(years)} years; {rs(amount)} then is worth {rs(amount / f)} today."


@tool(C, ex={"principal": 100000, "annual_rate": 7.1, "years": 5}, keys="fixed deposit fd maturity bank")
def fd_maturity(principal: float, annual_rate: float, years: float) -> str:
    """Fixed deposit maturity (quarterly compounding, as most Indian banks use)."""
    amt = principal * (1 + annual_rate / 400) ** (4 * years)
    return f"Maturity {rs(amt)} (interest {rs(amt - principal)}), before tax."


@tool(C, ex={"monthly": 5000, "annual_rate": 7, "months": 36}, keys="recurring deposit rd")
def rd_maturity(monthly: float, annual_rate: float, months: int) -> str:
    """Recurring deposit maturity (quarterly compounding)."""
    total = sum(monthly * (1 + annual_rate / 400) ** (4 * (months - i) / 12) for i in range(months))
    return f"Maturity about {rs(total)} on deposits of {rs(monthly * months)}."


@tool(C, ex={"yearly": 150000, "annual_rate": 7.1, "years": 15}, keys="ppf epf yearly deposit")
def yearly_deposit_maturity(yearly: float, annual_rate: float, years: int = 15) -> str:
    """Maturity of a yearly deposit like PPF (deposited at the start of each year, compounded yearly)."""
    total = sum(yearly * (1 + annual_rate / 100) ** (years - i) for i in range(years))
    return f"About {rs(total)} after {years} years on deposits of {rs(yearly * years)}."


@tool(C, ex={"price": 1000, "rate": 18}, keys="gst tax add")
def gst_add(price: float, rate: float = 18) -> str:
    """Add GST to a price (rates 0, 5, 12, 18, 28…)."""
    g = price * rate / 100
    return f"Price {rs(price)} + GST {rs(g)} ({fmt(rate)}%: CGST {rs(g / 2)} + SGST {rs(g / 2)}) = {rs(price + g)}."


@tool(C, ex={"price": 1180, "rate": 18}, keys="gst inclusive remove reverse")
def gst_remove(price: float, rate: float = 18) -> str:
    """Split a GST-inclusive price into base price and GST."""
    base = price / (1 + rate / 100)
    return f"Base {rs(base)} + GST {rs(price - base)} ({fmt(rate)}%) = {rs(price)}."


@tool(C, ex={"price": 2499, "percent": 30}, keys="discount sale offer")
def discount(price: float, percent: float, extra_percent: float = 0) -> str:
    """Price after a discount (and an optional extra discount on top)."""
    p = price * (1 - percent / 100) * (1 - extra_percent / 100)
    return f"You pay {rs(p)}, saving {rs(price - p)} ({fmt((price - p) / price * 100, 1)}% overall)."


@tool(C, ex={"bill": 1850, "percent": 10, "people": 3}, keys="tip restaurant split")
def tip(bill: float, percent: float = 10, people: int = 1) -> str:
    """Tip and per-person share."""
    t = bill * percent / 100
    people = max(1, people)
    return f"Tip {rs(t)}; total {rs(bill + t)}; {rs((bill + t) / people)} each for {people}."


@tool(C, ex={"total": 3600, "people": 4}, keys="split share divide expenses")
def split_bill(total: float, people: int, already_paid: list[float] = None) -> str:
    """Split a bill evenly; with already_paid (one amount per person) it says who owes whom."""
    people = max(1, people)
    share = total / people
    if not already_paid:
        return f"{rs(share)} each."
    if len(already_paid) != people:
        raise ToolError("give one paid amount per person")
    lines = [f"Person {i + 1} {'gets back' if p > share else 'owes'} {rs(abs(p - share))}" for i, p in enumerate(already_paid) if abs(p - share) > 0.005]
    return f"Each share {rs(share)}. " + ("; ".join(lines) or "Everyone is square.")


@tool(C, ex={"price_a": 120, "qty_a": 500, "price_b": 210, "qty_b": 1000}, keys="unit price compare cheaper value pack")
def compare_unit_price(price_a: float, qty_a: float, price_b: float, qty_b: float) -> str:
    """Which pack is better value (price per unit)."""
    a, b = price_a / qty_a, price_b / qty_b
    better = "A" if a < b else "B" if b < a else "neither"
    return f"A: {fmt(a, 4)} per unit, B: {fmt(b, 4)} per unit. " + (f"Pack {better} is cheaper by {fmt(abs(a - b) / max(a, b) * 100, 1)}%." if better != "neither" else "Same value.")


@tool(C, ex={"fixed_costs": 50000, "price": 250, "variable_cost": 150}, keys="break even business")
def break_even(fixed_costs: float, price: float, variable_cost: float) -> str:
    """Units you must sell to break even."""
    if price <= variable_cost:
        raise ToolError("price must be more than the cost per unit")
    import math
    u = math.ceil(fixed_costs / (price - variable_cost))
    return f"{u:,} units ({rs(u * price)} in sales)."


@tool(C, ex={"cost": 400, "price": 550}, keys="profit margin markup")
def margin_markup(cost: float, price: float) -> str:
    """Profit, margin (on price) and markup (on cost)."""
    if cost <= 0 or price <= 0:
        raise ToolError("cost and price must be positive")
    return f"Profit {rs(price - cost)}; margin {fmt((price - cost) / price * 100, 2)}%; markup {fmt((price - cost) / cost * 100, 2)}%."


@tool(C, ex={"cost": 400, "margin_percent": 25}, keys="selling price margin pricing")
def price_for_margin(cost: float, margin_percent: float) -> str:
    """Selling price that gives a target margin."""
    if margin_percent >= 100:
        raise ToolError("margin must be under 100%")
    return rs(cost / (1 - margin_percent / 100))


@tool(C, ex={"amount": 1200000, "period": "year", "hours_per_week": 45}, keys="salary hourly monthly annual ctc")
def salary_breakdown(amount: float, period: Literal["hour", "day", "month", "year"] = "year", hours_per_week: float = 40) -> dict:
    """Convert pay between hourly, daily, monthly and yearly (gross, before tax)."""
    per_year = {"hour": amount * hours_per_week * 52, "day": amount * 5 * 52, "month": amount * 12, "year": amount}[period]
    return {"year": rs(per_year), "month": rs(per_year / 12), "week": rs(per_year / 52), "day (5-day week)": rs(per_year / 260),
            "hour": rs(per_year / (hours_per_week * 52))}


@tool(C, ex={"units": 250, "rate_per_unit": 7.5, "fixed_charge": 50}, keys="electricity bill power units kwh")
def electricity_cost(units: float, rate_per_unit: float, fixed_charge: float = 0) -> str:
    """Estimate an electricity bill from units (kWh) used and your tariff."""
    return rs(units * rate_per_unit + fixed_charge)


@tool(C, ex={"watts": 1500, "hours_per_day": 8, "rate_per_unit": 7}, keys="appliance running cost ac heater power")
def appliance_running_cost(watts: float, hours_per_day: float, rate_per_unit: float, days: int = 30) -> str:
    """What an appliance costs to run (e.g. a 1.5 kW AC for 8 hours a day)."""
    kwh = watts / 1000 * hours_per_day * days
    return f"{fmt(round(kwh, 1))} units over {many(days, 'day')} ≈ {rs(kwh * rate_per_unit)}."


@tool(C, ex={"distance_km": 450, "mileage_kmpl": 15, "fuel_price": 105}, keys="trip fuel cost petrol diesel car travel")
def trip_fuel_cost(distance_km: float, mileage_kmpl: float, fuel_price: float, people: int = 1) -> str:
    """Fuel needed and cost for a trip."""
    litres = distance_km / mileage_kmpl
    cost = litres * fuel_price
    return f"{fmt(round(litres, 1))} litres, {rs(cost)}" + (f", {rs(cost / people)} each" if people > 1 else "") + "."


@tool(C, ex={"amount": 100, "from_currency": "USD", "to_currency": "INR"}, net=True, keys="currency exchange convert dollar rupee euro forex")
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert money between currencies at today's rate (live)."""
    from .. import internet
    return internet.info("EXCHANGE", {"a": from_currency, "b": to_currency, "n": str(amount)}).text


@tool(C, ex={"base": "INR"}, net=True, keys="exchange rates table forex")
def exchange_rates(base: str = "USD", currencies: list[str] = None) -> dict:
    """Today's exchange rates from one currency to many (live)."""
    from .. import internet
    d = internet.get_json(f"https://open.er-api.com/v6/latest/{base.upper()}", 1800)
    want = [c.upper() for c in (currencies or ["USD", "INR", "EUR", "GBP", "AED", "SGD", "JPY", "AUD", "CAD", "CNY"])]
    return {c: d.get("rates", {}).get(c) for c in want if c != base.upper()} | {"updated": d.get("time_last_update_utc", "")[:16]}


@tool(C, ex={"coin": "ethereum"}, net=True, keys="crypto bitcoin price coin")
def crypto_price(coin: str) -> str:
    """Live price of a cryptocurrency in USD and INR."""
    from .. import internet
    return internet.info("CRYPTO", {"q": coin}).text


@tool(C, ex={"count": 5}, net=True, keys="crypto market top coins ranking")
def top_cryptos(count: int = 10) -> list:
    """Top cryptocurrencies by market cap (live)."""
    from .. import internet
    d = internet.get_json(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={max(1, min(count, 25))}&page=1", 300)
    return [f"{c['market_cap_rank']}. {c['name']}: ${c['current_price']:,} ({(c.get('price_change_percentage_24h') or 0):+.1f}% 24h)" for c in d]


@tool(C, ex={"monthly_expenses": 40000, "months": 6}, keys="emergency fund savings safety")
def emergency_fund(monthly_expenses: float, months: int = 6) -> str:
    """How big an emergency fund should be (usually 3–6 months of expenses)."""
    return f"{rs(monthly_expenses * months)} ({months} months of expenses)."


@tool(C, ex={"current_age": 30, "retire_age": 60, "monthly_expenses_today": 40000, "inflation": 6, "years_after": 25}, keys="retirement corpus plan pension")
def retirement_corpus(current_age: int, retire_age: int, monthly_expenses_today: float, inflation: float = 6,
                      years_after: int = 25, return_after: float = 7) -> str:
    """Rough retirement corpus needed (expenses grown by inflation, drawn down over years_after)."""
    n = retire_age - current_age
    if n <= 0:
        raise ToolError("retire age must be after current age")
    yearly = monthly_expenses_today * 12 * (1 + inflation / 100) ** n
    real = (1 + return_after / 100) / (1 + inflation / 100) - 1
    corpus = yearly * years_after if abs(real) < 1e-9 else yearly * (1 - (1 + real) ** -years_after) / real * (1 + real)
    return f"At {retire_age} you'd spend about {rs(yearly)} a year; a corpus of about {rs(corpus)} lasts {years_after} years. A rough guide only."
