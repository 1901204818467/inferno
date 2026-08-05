"""Compute the daily craft-vs-sell decision for the reminder embed.

Reads today's prices.json (written by fetch-data.py) plus the stockpile
ledger, compares the day's very crude gabagool against three uses - sell
raw, craft into Fuel Gabagool, or craft into Hypergolic - and writes the
recommendation to $RUNNER_TEMP/decision.txt. Rolls the day's very crude
through the stockpile ledger (first decision per GMT+3 day only, mirroring
the update-stats dedup) and merges decision fields into stats-day.json for
lifetime stats. Standalone script: no imports from other scripts, no
network calls, every missing input degrades gracefully.
"""

import json
import os

TMP = os.environ.get("RUNNER_TEMP", "/tmp")

PROFIT = {
    "very_crude_per_day": 175,
    "sell_tax": 0.0125,
}

RECIPES = {
    "hypergolic": {"very": 36, "coal": 301},
    "gabagool": {"very": 1, "coal": 8, "makes": 8},
}

GATES = {
    "hyper_sell_cap": 5,
    "hyper_vol_min": 50,
    "gab_vol_min": 28000,
    "gab_min_margin": 15000.0,
    "crash_ratio": 0.85,
    "roi_threshold": 0.10,
    "spread_wide": 0.30,
}

EMPTY_STATE = {
    "schema": 1,
    "last_decision_date": "",
    "very_produced": 0,
    "very_consumed": 0,
    "hyper_rec": 0,
    "gabagool_batches_rec": 0,
    "last_action": "",
    "last_margin": None,
    "margin_history": [],
}


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def fmt(n):
    if n is None or n <= 0:
        return ""
    if n >= 1000000:
        s = "%.2f" % (n / 1000000.0)
        return s.rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        s = "%.1f" % (n / 1000.0)
        k = s.rstrip("0").rstrip(".")
        if float(k) >= 1000:
            s = "%.2f" % (n / 1000000.0)
            return s.rstrip("0").rstrip(".") + "M"
        return k + "K"
    return str(int(n))


def fmt_signed(n):
    if n is None:
        return "-"
    if n >= 0:
        return "+" + fmt(n)
    return "-" + fmt(-n)


def fmt_int(n):
    return "{:,}".format(int(n))


def anchored(spot, wm):
    if not wm or wm <= 0:
        return spot
    return median([spot, wm, wm * 0.9])


def pct_below(is_price, wm):
    if not is_price or not wm or wm <= 0:
        return None
    return int(round((1.0 - is_price / wm) * 100.0))


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def compute(very, coal, gab, hyper):
    tax = PROFIT["sell_tax"]

    very_is = very.get("instasell") or 0
    very_so = very.get("sell_order") or 0
    very_wm = (very.get("week") or {}).get("sell", {}).get("median") or 0
    coal_bo = coal.get("buy_order") or 0
    gab_is = gab.get("instasell") or 0
    gab_so = gab.get("sell_order") or 0
    gab_wm = (gab.get("week") or {}).get("sell", {}).get("median") or 0
    gab_vol = gab.get("buy_moving_week") or gab.get("buy_volume_day") or 0
    hyper_is = hyper.get("instasell") or 0
    hyper_so = hyper.get("sell_order") or 0
    hyper_wm = (hyper.get("week") or {}).get("sell", {}).get("median") or 0
    hyper_vol = hyper.get("buy_moving_week") or hyper.get("buy_volume_day") or 0

    hyper_anchor = anchored(hyper_so, hyper_wm)
    gab_anchor = anchored(gab_so, gab_wm)

    hyper_margin = None
    hyper_floor = None
    if very_so > 0 and coal_bo > 0 and hyper_anchor > 0:
        craft_cost = 36.0 * very_so * (1.0 - tax) + RECIPES["hypergolic"]["coal"] * coal_bo
        hyper_margin = hyper_anchor * (1.0 - tax) - craft_cost
        if hyper_is > 0:
            hyper_floor = hyper_is * (1.0 - tax) - craft_cost

    gab_margin = None
    gab_floor = None
    if very_so > 0 and coal_bo > 0 and gab_anchor > 0:
        craft_cost = (
            RECIPES["gabagool"]["coal"] * coal_bo + very_so * (1.0 - tax)
        )
        gab_margin = RECIPES["gabagool"]["makes"] * gab_anchor * (1.0 - tax) - craft_cost
        if gab_is > 0:
            gab_floor = RECIPES["gabagool"]["makes"] * gab_is * (1.0 - tax) - craft_cost

    very_falling = bool(very_wm > 0 and very_is > 0 and very_is < GATES["crash_ratio"] * very_wm)
    gab_falling = bool(gab_wm > 0 and gab_is > 0 and gab_is < GATES["crash_ratio"] * gab_wm)
    hyper_falling = bool(hyper_wm > 0 and hyper_is > 0 and hyper_is < GATES["crash_ratio"] * hyper_wm)

    return {
        "very_is": very_is,
        "very_so": very_so,
        "very_wm": very_wm,
        "coal_bo": coal_bo,
        "gab_is": gab_is,
        "gab_so": gab_so,
        "gab_wm": gab_wm,
        "gab_vol": gab_vol,
        "hyper_is": hyper_is,
        "hyper_so": hyper_so,
        "hyper_wm": hyper_wm,
        "hyper_vol": hyper_vol,
        "hyper_anchor": hyper_anchor,
        "gab_anchor": gab_anchor,
        "hyper_margin": hyper_margin,
        "hyper_floor": hyper_floor,
        "gab_margin": gab_margin,
        "gab_floor": gab_floor,
        "very_falling": very_falling,
        "gab_falling": gab_falling,
        "hyper_falling": hyper_falling,
    }


def choose(rec, held):
    cap = GATES["hyper_sell_cap"]
    available = held + PROFIT["very_crude_per_day"]

    if (
        rec["hyper_margin"] is not None
        and not rec["hyper_falling"]
        and rec["hyper_vol"] >= GATES["hyper_vol_min"]
        and rec["hyper_anchor"] > 0
        and rec["hyper_margin"] >= GATES["roi_threshold"] * rec["hyper_anchor"]
        and (rec["hyper_floor"] is not None and rec["hyper_floor"] >= 0)
    ):
        n = min(cap, int(available // RECIPES["hypergolic"]["very"]))
        if n >= 1:
            return "CRAFT_HYPER", n, RECIPES["hypergolic"]["very"] * n

    if (
        rec["gab_margin"] is not None
        and not rec["gab_falling"]
        and rec["gab_vol"] >= GATES["gab_vol_min"]
        and rec["gab_margin"] >= GATES["gab_min_margin"]
        and (rec["gab_floor"] is not None and rec["gab_floor"] >= 0)
    ):
        return "CRAFT_GABAGOOL", 0, PROFIT["very_crude_per_day"]

    if rec["very_falling"]:
        return "HOLD", 0, 0

    return "SELL_RAW", 0, PROFIT["very_crude_per_day"]


def trigger_price(rec):
    if rec["hyper_margin"] is None:
        return None
    cost = 36.0 * rec["very_so"] * (1.0 - PROFIT["sell_tax"]) + RECIPES["hypergolic"]["coal"] * rec["coal_bo"]
    if cost <= 0:
        return None
    return cost / (1.0 - PROFIT["sell_tax"] - GATES["roi_threshold"])


def decision_lines(rec, decision, n, held):
    lines = []
    gab_gated = bool(rec["gab_vol"] < GATES["gab_vol_min"])
    thin = " (thin)" if gab_gated else ""
    leaderboard = "Margins vs sell raw: Hypergolic %s/unit | Gabagool %s/very%s | sell very %s/very" % (
        fmt_signed(rec["hyper_margin"]),
        fmt_signed(rec["gab_margin"]),
        thin,
        fmt(rec["very_so"]) or "-",
    )

    if decision == "CRAFT_HYPER":
        coal_needed = n * RECIPES["hypergolic"]["coal"]
        very_used = n * RECIPES["hypergolic"]["very"]
        delta = n * rec["hyper_margin"] if rec["hyper_margin"] is not None else None
        lines.append("Decision - Craft %dx Hypergolic - sell order" % n)
        lines.append(
            "%s each | %s/day vs selling very raw | uses %s very + %s coal"
            % (fmt_signed(rec["hyper_margin"]), fmt_signed(delta), fmt_int(very_used), fmt_int(coal_needed))
        )
        lines.append(leaderboard)
        lines.append("Stockpile - %s very held" % fmt_int(held))
    elif decision == "CRAFT_GABAGOOL":
        delta = PROFIT["very_crude_per_day"] * rec["gab_margin"] if rec["gab_margin"] is not None else None
        lines.append("Decision - Craft %sx Fuel Gabagool - sell order" % fmt_int(PROFIT["very_crude_per_day"] * 8))
        lines.append(
            "%s/very | %s/day vs selling very raw | uses %d very + %d coal"
            % (
                fmt_signed(rec["gab_margin"]),
                fmt_signed(delta),
                PROFIT["very_crude_per_day"],
                PROFIT["very_crude_per_day"] * RECIPES["gabagool"]["coal"],
            )
        )
        lines.append(leaderboard)
        lines.append("Stockpile - %s very held" % fmt_int(held))
    elif decision == "HOLD":
        trg = trigger_price(rec)
        lines.append("Decision - Hold - market falling")
        vp = pct_below(rec["very_is"], rec["very_wm"])
        hp = pct_below(rec["hyper_is"], rec["hyper_wm"])
        bits = []
        if vp is not None:
            bits.append("very crude %d%% below 7d avg" % vp)
        if hp is not None:
            bits.append("hypergolic %d%% below 7d avg" % hp)
        lines.append(" | ".join(bits))
        if trg:
            lines.append("Craft trigger: hypergolic sell order > %s | margin %s now" % (fmt(trg), fmt_signed(rec["hyper_margin"])))
        else:
            lines.append("Craft trigger: none until prices recover")
        lines.append(leaderboard)
        lines.append("Stockpile - %s very held | sell raw if you need coins" % fmt_int(held))
    else:
        so = rec["very_so"] or rec["very_is"]
        daily = PROFIT["very_crude_per_day"] * so * (1.0 - PROFIT["sell_tax"])
        lines.append("Decision - Sell %dx Very Crude - sell order" % PROFIT["very_crude_per_day"])
        lines.append("%s/very | %s/day | best play today" % (fmt(so), fmt(daily)))
        lines.append(leaderboard)
        lines.append("Stockpile - %s very held" % fmt_int(held))
    return lines


def main():
    prices = load_json("prices.json", {})
    if not isinstance(prices, dict):
        prices = {}
    items = prices.get("items") or {}
    date = prices.get("date") or ""

    very = items.get("VERY_CRUDE_GABAGOOL") or {}
    coal = items.get("SULPHURIC_COAL") or {}
    gab = items.get("FUEL_GABAGOOL") or {}
    hyper = items.get("HYPERGOLIC_GABAGOOL") or {}

    if not (very.get("instasell") or very.get("sell_order")):
        print("decision: no very crude prices, skipping")
        return

    state = dict(EMPTY_STATE)
    loaded = load_json("stockpile-state.json", {})
    if isinstance(loaded, dict):
        state.update(loaded)
    held = max(0, int(state.get("very_produced") or 0) - int(state.get("very_consumed") or 0))

    rec = compute(very, coal, gab, hyper)
    decision, n, used = choose(rec, held)
    held_now = max(0, held + PROFIT["very_crude_per_day"] - used)

    if date and date != state.get("last_decision_date"):
        state["very_produced"] = int(state.get("very_produced") or 0) + PROFIT["very_crude_per_day"]
        state["very_consumed"] = int(state.get("very_consumed") or 0) + used
        state["last_decision_date"] = date
        state["last_action"] = decision
        if rec["hyper_margin"] is not None:
            state["last_margin"] = int(rec["hyper_margin"])
        hist = state.get("margin_history") if isinstance(state.get("margin_history"), list) else []
        hist.append({
            "date": date,
            "action": decision,
            "hyper_margin": int(rec["hyper_margin"]) if rec["hyper_margin"] is not None else None,
            "gab_margin": int(rec["gab_margin"]) if rec["gab_margin"] is not None else None,
        })
        state["margin_history"] = hist[-7:]
        if decision == "CRAFT_HYPER":
            state["hyper_rec"] = int(state.get("hyper_rec") or 0) + n
        elif decision == "CRAFT_GABAGOOL":
            state["gabagool_batches_rec"] = int(state.get("gabagool_batches_rec") or 0) + PROFIT["very_crude_per_day"]
        with open("stockpile-state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)

    lines = decision_lines(rec, decision, n, held_now)
    with open(os.path.join(TMP, "decision.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    day_path = os.path.join(TMP, "stats-day.json")
    if date and os.path.exists(day_path):
        day = load_json(day_path, {})
        if not isinstance(day, dict):
            day = {}
        day["date"] = date
        day["decision"] = decision
        day["hyper_crafted"] = n
        day["hyper_margin"] = int(rec["hyper_margin"]) if rec["hyper_margin"] is not None else None
        day["gab_margin"] = int(rec["gab_margin"]) if rec["gab_margin"] is not None else None
        day["gab_gated"] = bool(rec["gab_vol"] < GATES["gab_vol_min"])
        day["falling"] = bool(rec["very_falling"] or rec["gab_falling"] or rec["hyper_falling"])
        with open(day_path, "w", encoding="utf-8") as f:
            json.dump(day, f)

    held_now = max(0, int(state.get("very_produced") or 0) - int(state.get("very_consumed") or 0))
    print("decision: %s n=%d used=%d held=%s hyper_margin=%s gab_margin=%s" % (
        decision, n, used, fmt(held_now), fmt(rec["hyper_margin"]), fmt(rec["gab_margin"])))


if __name__ == "__main__":
    main()
