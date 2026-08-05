# .github/scripts — pipeline code

**Generated:** 2026-08-06 (child of root AGENTS.md — see parent for project-wide rules)

## OVERVIEW

All executable logic of the project: 6 standalone, stdlib-only Python 3.12+ scripts. Zero imports between them — the pipeline is a sequence of separate `python3` invocations wired by the workflow YAML.

## STRUCTURE

| Script | Role | I/O contract |
|--------|------|--------------|
| `fetch-data.py` | Stage 1: prices + history + random fact | Hypixel bazaar, Coflnet, uselessfacts, Wikipedia → `prices.json`, `prices.jsonl`, `$RUNNER_TEMP/{shopping-list,profit,fact,animal-*}.txt` |
| `decision.py` | Stage 2: craft-vs-sell engine | `prices.json` + `stockpile-state.json` → `$RUNNER_TEMP/decision.txt`, updates ledger |
| `purge-messages.py` | Stage 0: delete previous Discord message | `../reminder-state.json` → DELETE webhook msg |
| `update-stats.py` | Stage 4: lifetime stats | `$RUNNER_TEMP/stats-day.json` → `stats.json` |
| `generate-chart.py` | Stage 5: SVG sparkline | `prices.jsonl` → `chart.svg` |
| `test-decision.py` | Offline tests for decision.py | synthetic fixtures → PASS/FAIL output; NOT in CI |

## WHERE TO LOOK

- **PROFIT dict** (all economic constants: minion output, tax, fuel burn, bits math) — top of `fetch-data.py`
- **RECIPES / GATES / EMPTY_STATE dicts** (decision logic source of truth) — `decision.py`
- **Fact pipeline** (keyword ranking, Wikipedia image match, 36-animal fallback) — `fetch-data.py`
- **Anchor formula / margin math** (patient-everywhere price sides) — `decision.py`

## CONVENTIONS

- Every script: module docstring (purpose, I/O, failure behavior) → `def main()` → `if __name__ == "__main__": main()`
- stdout logging prefixed per script: `purge:` `prices:` `profit:` `chart:` `stats:` `decision:` `fact:`
- Graceful degradation: `load_json(path, default)` pattern; every network call optional; missing input → sensible default, never crash
- Temp outputs → `$RUNNER_TEMP` via env var; repo files written with `encoding="utf-8"`, `json.dump(indent=1)`
- Bazaar tags SCREAMING_SNAKE (`SULPHURIC_COAL`, `CRUDE_GABAGOOL_DISTILLATE`...); action enums SCREAMING_SNAKE (`CRAFT_HYPER`, `SELL_RAW`, `HOLD`); helpers snake_case verb-first (`fetch_fact`, `series_metrics`, `side_prices`)
- JSON keys snake_case; price sides always `buy_order`/`instabuy`/`instasell`/`sell_order`; `_bo`/`_ib`/`_disp` suffixes

## ANTI-PATTERNS (THIS DIR)

- Importing a sibling script (breaks standalone contract)
- Adding network calls to `decision.py` (pure offline computation only)
- Comments — stripped by design; rename functions instead
- Anything beyond stdlib; new temp/output files outside `$RUNNER_TEMP` or the 6 committed data files

## TESTING

`test-decision.py` runs `decision.py` as a subprocess against temp-dir fixtures (never imports it). Helpers: `item()`, `prices_fixture()`, `run_case()`, `expect()`. ~10 cases cover all decisions + dedup + floor-gate blocking + fmt rounding. Run: `python3 test-decision.py` — must print `ALL 10 CASES PASSED`. Follow this subprocess-fixture pattern for any new test file.
