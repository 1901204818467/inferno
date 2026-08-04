#!/usr/bin/env python3
"""Merge today's stats snapshot into the lifetime stats file.

Reads stats-day.json from $RUNNER_TEMP (written by fetch-data.py) and
accumulates it into stats.json in the repo root. This is a standalone
script (called from the workflow) so there is zero risk of YAML heredoc
indentation breaking the Python.
"""
import json
import os
import sys


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
    day_path = os.path.join(tmp, "stats-day.json")

    day = {}
    try:
        with open(day_path, encoding="utf-8") as f:
            day = json.load(f)
    except FileNotFoundError:
        pass  # no stats-day.json yet (profit data unavailable this run)

    stats = {}
    try:
        with open("stats.json", encoding="utf-8") as f:
            stats = json.load(f)
    except FileNotFoundError:
        pass  # fresh start, no stats file yet

    dbo = int(day.get("net_bo") or 0)
    dib = int(day.get("net_ib") or 0)

    stats["refuels"] = stats.get("refuels", 0) + 1
    stats["fuel_blocks"] = stats.get("fuel_blocks", 0) + 50
    stats["total_net_bo"] = stats.get("total_net_bo", 0) + dbo
    stats["total_net_ib"] = stats.get("total_net_ib", 0) + dib
    stats["total_income_sell"] = (
        stats.get("total_income_sell", 0)
        + int(day.get("income_sell") or 0)
    )
    stats["total_income_order"] = (
        stats.get("total_income_order", 0)
        + int(day.get("income_order") or 0)
    )
    stats["total_spent_bo"] = (
        stats.get("total_spent_bo", 0) + int(day.get("spent_bo") or 0)
    )
    stats["total_spent_ib"] = (
        stats.get("total_spent_ib", 0) + int(day.get("spent_ib") or 0)
    )

    if not stats.get("first_day") and day.get("date"):
        stats["first_day"] = day["date"]
    if day.get("date"):
        stats["last_day"] = day["date"]

    if dbo > stats.get("best_day_net_bo", 0):
        stats["best_day_net_bo"] = dbo
        stats["best_day_date_bo"] = day.get("date", "")
    if dib > stats.get("best_day_net_ib", 0):
        stats["best_day_net_ib"] = dib
        stats["best_day_date_ib"] = day.get("date", "")

    r = stats["refuels"]
    stats["avg_net_bo"] = stats["total_net_bo"] // r if r else 0
    stats["avg_net_ib"] = stats["total_net_ib"] // r if r else 0

    stats["total_net_disp"] = fmt(stats.get("total_net_ib", 0))
    stats["total_spent_disp"] = fmt(stats.get("total_spent_ib", 0))
    stats["avg_net_ib_disp"] = fmt(stats.get("avg_net_ib", 0))
    stats["best_day_net_ib_disp"] = fmt(stats.get("best_day_net_ib", 0))

    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)


if __name__ == "__main__":
    main()
