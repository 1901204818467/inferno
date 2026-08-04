"""Merge today's stats snapshot into the lifetime stats file.

Reads stats-day.json from $RUNNER_TEMP (written by fetch-data.py) and
accumulates it into stats.json in the repo root. Standalone script so the
workflow never needs inline Python. Only the first run of a GMT+3 calendar
day counts - reruns on the same day are skipped so testing never inflates
the lifetime numbers.
"""

import json
import os


def fmt(n):
    if n >= 1000000000:
        return "%.2fB" % (n / 1e9)
    if n >= 1000000:
        return "%.1fM" % (n / 1e6)
    if n >= 1000:
        return "%.1fK" % (n / 1e3)
    return str(int(n))


def main():
    tmp = os.environ.get("RUNNER_TEMP", "/tmp")
    day = {}
    try:
        with open(os.path.join(tmp, "stats-day.json"), encoding="utf-8") as f:
            day = json.load(f)
        os.remove(os.path.join(tmp, "stats-day.json"))
    except FileNotFoundError:
        pass
    except OSError:
        pass

    stats = {}
    try:
        with open("stats.json", encoding="utf-8") as f:
            stats = json.load(f)
    except FileNotFoundError:
        pass

    today = day.get("date", "")
    last = stats.get("last_day", "")

    if not today:
        print("stats: no day data, skipping")
    elif last == today:
        print("stats: same day (%s), skipping accumulation" % today)
    else:
        stats["refuels"] = stats.get("refuels", 0) + 1
        stats["fuel_blocks"] = stats.get("fuel_blocks", 0) + 50
        stats["total_net_bo"] = stats.get("total_net_bo", 0) + int(day.get("net_bo") or 0)
        stats["total_net_ib"] = stats.get("total_net_ib", 0) + int(day.get("net_ib") or 0)
        stats["total_income_sell"] = stats.get("total_income_sell", 0) + int(day.get("income_sell") or 0)
        stats["total_income_order"] = stats.get("total_income_order", 0) + int(day.get("income_order") or 0)
        stats["total_spent_bo"] = stats.get("total_spent_bo", 0) + int(day.get("spent_bo") or 0)
        stats["total_spent_ib"] = stats.get("total_spent_ib", 0) + int(day.get("spent_ib") or 0)
        stats["total_crude_opp_sell"] = stats.get("total_crude_opp_sell", 0) + int(day.get("crude_cost_sell") or 0)
        stats["total_crude_opp_order"] = stats.get("total_crude_opp_order", 0) + int(day.get("crude_cost_order") or 0)

        if day.get("spike_fired"):
            stats["spike_days"] = stats.get("spike_days", 0) + 1
            stats["last_spike"] = day.get("spike_items")
        if day.get("stockup_fired"):
            stats["stockup_days"] = stats.get("stockup_days", 0) + 1
            stats["last_stockup_pct"] = day.get("stockup_pct")
        if day.get("craftbuy_fired"):
            stats["craftbuy_days"] = stats.get("craftbuy_days", 0) + 1
            stats["last_craftbuy_savings"] = day.get("craftbuy_savings")

        if not stats.get("first_day") and today:
            stats["first_day"] = today
        if today:
            stats["last_day"] = today

        nbo = int(day.get("net_bo") or 0)
        nib = int(day.get("net_ib") or 0)
        if nbo > stats.get("best_day_net_bo", 0):
            stats["best_day_net_bo"] = nbo
            stats["best_day_date_bo"] = today
        if nib > stats.get("best_day_net_ib", 0):
            stats["best_day_net_ib"] = nib
            stats["best_day_date_ib"] = today
        if "worst_day_net_ib" not in stats or nib < stats.get("worst_day_net_ib", 0):
            stats["worst_day_net_ib"] = nib
            stats["worst_day_date_ib"] = today
        inc = int(day.get("income_sell") or 0)
        if inc > stats.get("best_day_income_sell", 0):
            stats["best_day_income_sell"] = inc
            stats["best_day_income_date"] = today

    refuels = stats.get("refuels", 0)
    if refuels:
        stats["avg_net_bo"] = stats["total_net_bo"] // refuels
        stats["avg_net_ib"] = stats["total_net_ib"] // refuels
        stats["avg_income_sell"] = stats["total_income_sell"] // refuels
        stats["avg_income_order"] = stats["total_income_order"] // refuels
        stats["avg_spent_bo"] = stats["total_spent_bo"] // refuels
        stats["avg_spent_ib"] = stats["total_spent_ib"] // refuels
        stats["avg_crude_opp_sell"] = stats["total_crude_opp_sell"] // refuels

    stats["total_net_disp"] = fmt(stats.get("total_net_ib", 0))
    stats["total_spent_disp"] = fmt(stats.get("total_spent_ib", 0))
    stats["avg_net_ib_disp"] = fmt(stats.get("avg_net_ib", 0))
    stats["best_day_net_ib_disp"] = fmt(stats.get("best_day_net_ib", 0))
    stats["worst_day_net_ib_disp"] = fmt(stats.get("worst_day_net_ib", 0))
    stats["days_tracked"] = refuels

    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)


if __name__ == "__main__":
    main()
