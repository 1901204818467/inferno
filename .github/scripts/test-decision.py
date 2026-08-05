"""Fixture tests for decision.py - no network required.

Builds synthetic prices.json and stockpile-state.json fixtures in a temp
directory, runs decision.py as a subprocess against them, and asserts the
decision.txt output plus the ledger updates. Run: python3 test-decision.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DECISION = os.path.join(HERE, "decision.py")


def item(instasell, sell_order, wm=None, vol=0):
    d = {"instasell": instasell, "sell_order": sell_order}
    if wm:
        d["week"] = {"sell": {"median": wm}}
    if vol:
        d["buy_moving_week"] = vol
    return d


def prices_fixture(very, coal_bo, gab, hyper, date="2026-08-05"):
    return {
        "date": date,
        "items": {
            "VERY_CRUDE_GABAGOOL": very,
            "SULPHURIC_COAL": {"buy_order": coal_bo, "instabuy": int(coal_bo * 1.38)},
            "FUEL_GABAGOOL": gab,
            "HYPERGOLIC_GABAGOOL": hyper,
        },
    }


def run_case(fixture_prices, state=None, date="2026-08-05"):
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "out")
        os.makedirs(tmp)
        if fixture_prices is not None:
            with open(os.path.join(d, "prices.json"), "w", encoding="utf-8") as f:
                json.dump(fixture_prices, f)
        if state is not None:
            with open(os.path.join(d, "stockpile-state.json"), "w", encoding="utf-8") as f:
                json.dump(state, f)
        env = dict(os.environ)
        env["RUNNER_TEMP"] = tmp
        proc = subprocess.run(
            [sys.executable, DECISION],
            cwd=d, env=env, capture_output=True, text=True, timeout=60,
        )
        decision_txt = ""
        dp = os.path.join(tmp, "decision.txt")
        if os.path.exists(dp):
            with open(dp, encoding="utf-8") as f:
                decision_txt = f.read().strip()
        new_state = None
        sp = os.path.join(d, "stockpile-state.json")
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as f:
                new_state = json.load(f)
        return proc, decision_txt, new_state


def expect(ok, msg):
    if ok:
        print("PASS: %s" % msg)
    else:
        print("FAIL: %s" % msg)
        raise SystemExit(1)


def main():
    cases = 0

    very_today = item(56560, 67856, wm=78087)
    gab_today = item(9502, 19644, wm=16453, vol=16535)
    hyper_today = item(3886037, 4699602, wm=5100000, vol=991)

    proc, txt, st = run_case(prices_fixture(very_today, 5796, gab_today, hyper_today))
    cases += 1
    expect(proc.returncode == 0, "HOLD case exits 0")
    expect(txt.startswith("Decision - Hold - market falling"), "HOLD case: %r" % txt.splitlines()[0] if txt else "empty")
    expect("very crude 28% below 7d avg" in txt, "HOLD case shows very crude drawdown pct")
    expect(st["very_produced"] == 175 and st["very_consumed"] == 0, "HOLD case rolls all 175 into stockpile")
    expect(st["last_action"] == "HOLD", "HOLD case records last_action")

    very_strong = item(70000, 78000, wm=78087)
    gab_dead = item(9502, 19644, wm=16453, vol=10000)
    hyper_strong = item(5300000, 5500000, wm=5100000, vol=991)
    proc, txt, st = run_case(prices_fixture(very_strong, 5796, gab_dead, hyper_strong))
    cases += 1
    expect(proc.returncode == 0, "CRAFT_HYPER case exits 0")
    expect(txt.startswith("Decision - Craft 4x Hypergolic - sell order"), "CRAFT_HYPER case crafts 4: %r" % (txt.splitlines()[0] if txt else "empty"))
    expect("uses 144 very + 1,204 coal" in txt, "CRAFT_HYPER case shows exact inputs")
    expect(st["very_produced"] == 175 and st["very_consumed"] == 144, "CRAFT_HYPER case consumes 144, holds 31")
    expect(st["hyper_rec"] == 4, "CRAFT_HYPER case records 4 hypergolics")

    very_ok = item(68000, 70000, wm=78087)
    gab_healthy = item(18000, 20000, wm=19000, vol=40000)
    hyper_bad = item(3800000, 4000000, wm=4200000, vol=991)
    proc, txt, st = run_case(prices_fixture(very_ok, 5796, gab_healthy, hyper_bad))
    cases += 1
    expect(proc.returncode == 0, "CRAFT_GABAGOOL case exits 0")
    expect(txt.startswith("Decision - Craft 1,400x Fuel Gabagool - sell order"), "CRAFT_GABAGOOL case: %r" % (txt.splitlines()[0] if txt else "empty"))
    expect("+34.6K/very" in txt, "CRAFT_GABAGOOL case shows honest margin")
    expect(st["very_consumed"] == 175, "CRAFT_GABAGOOL case consumes all 175")

    hyper_noweek = item(4800000, 5200000, wm=None, vol=991)
    proc, txt, st = run_case(prices_fixture(very_ok, 5796, gab_dead, hyper_noweek))
    cases += 1
    expect(proc.returncode == 0, "no-week-history case exits 0")
    expect(txt.startswith("Decision - Craft 4x Hypergolic - sell order"), "no-week-history case falls back to spot anchor: %r" % (txt.splitlines()[0] if txt else "empty"))

    hyper_dead = item(3800000, 4000000, wm=4200000, vol=991)
    proc, txt, st = run_case(prices_fixture(very_ok, 5796, gab_dead, hyper_dead))
    cases += 1
    expect(proc.returncode == 0, "SELL_RAW case exits 0")
    expect(txt.startswith("Decision - Sell 175x Very Crude - sell order"), "SELL_RAW case: %r" % (txt.splitlines()[0] if txt else "empty"))
    expect(st["very_consumed"] == 175, "SELL_RAW case consumes all 175")

    proc, txt, st = run_case(None)
    cases += 1
    expect(proc.returncode == 0, "missing prices.json exits 0")
    expect(txt == "", "missing prices.json writes no decision.txt")

    proc, txt, st = run_case(prices_fixture(very_strong, 5796, gab_dead, hyper_strong))
    expect(proc.returncode == 0, "dedup first run exits 0")
    expect(st["very_produced"] == 175, "dedup first run produces 175")
    proc2, txt2, st2 = run_case(prices_fixture(very_strong, 5796, gab_dead, hyper_strong), state=st)
    cases += 1
    expect(proc2.returncode == 0, "dedup rerun exits 0")
    expect(st2["very_produced"] == 175 and st2["very_consumed"] == 144, "dedup rerun does not double-add")
    expect(txt2.startswith("Decision - Craft 5x Hypergolic"), "dedup rerun crafts from stockpile: %r" % (txt2.splitlines()[0] if txt2 else "empty"))

    hyper_no_instasell = item(0, 5500000, wm=5100000, vol=991)
    proc, txt, st = run_case(prices_fixture(very_ok, 5796, gab_dead, hyper_no_instasell))
    cases += 1
    expect(proc.returncode == 0, "floor-gate hyper case exits 0")
    expect(txt.startswith("Decision - Sell 175x Very Crude"), "floor-gate hyper blocks craft on missing instasell: %r" % (txt.splitlines()[0] if txt else "empty"))
    expect(st["very_consumed"] == 175, "floor-gate hyper case sells raw")

    gab_no_instasell = item(0, 20000, wm=20000, vol=40000)
    proc, txt, st = run_case(prices_fixture(very_ok, 5796, gab_no_instasell, hyper_bad))
    cases += 1
    expect(proc.returncode == 0, "floor-gate gab case exits 0")
    expect(txt.startswith("Decision - Sell 175x Very Crude"), "floor-gate gab blocks craft on missing instasell: %r" % (txt.splitlines()[0] if txt else "empty"))
    expect(st["very_consumed"] == 175, "floor-gate gab case sells raw")

    proc = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util, sys; "
         "spec = importlib.util.spec_from_file_location('d', %r); "
         "d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d); "
         "assert d.fmt(999950) == '1M', d.fmt(999950); "
         "assert d.fmt(999949) == '999.9K', d.fmt(999949); "
         "assert d.fmt(1234567) == '1.23M', d.fmt(1234567); "
         "print('fmt ok')" % DECISION],
        capture_output=True, text=True, timeout=60,
    )
    out = proc.stdout
    cases += 1
    expect(proc.returncode == 0 and out.strip() == "fmt ok", "fmt 1000K rounding case: %r" % out.strip())

    print("ALL %d CASES PASSED" % cases)


if __name__ == "__main__":
    main()
