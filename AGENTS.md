# PROJECT KNOWLEDGE BASE

**Generated:** 2026-08-06 (single source of truth; former `IFURANAIREADTHISNOW.md` spec was merged here then deleted)
**Branch:** main
**Repo:** github.com/1901204818467/inferno

## OVERVIEW

GitHub Actions + stdlib-only Python 3.12 automation: a daily Discord webhook reminder for refueling 25x Inferno T3 minions in Hypixel Skyblock. Targets 21:50 UTC (00:50 GMT+3) daily — enforced by a watchdog (GitHub's cron scheduler can fire 30-120 min late, see NOTES), sends a Discord embed with a shopping list, crafting steps, live bazaar prices, daily profit estimate, a random fact + picture, and price anomaly alerts. Computes a craft-vs-sell decision, then commits state back to the repo. Free tier, public repo, zero API keys.

## STRUCTURE

```
Inferno/
├── .github/
│   ├── workflows/          # CI: daily-reminder.yml (THE pipeline), reminder-watchdog.yml (delivery watchdog), keepalive.yml
│   ├── scripts/            # ALL app logic — 6 standalone Python scripts → see .github/scripts/AGENTS.md
│   ├── reminder-state.json # sent Discord message IDs (purge source)
│   └── last-alive.txt      # keepalive timestamp
├── prices.json             # overwritten daily snapshot (badges + full per-item detail)
├── prices.jsonl            # append-only daily history (chart + history source)
├── stats.json              # lifetime stats, first-run-per-day dedup
├── stockpile-state.json    # decision ledger (very crude produced/consumed, margins)
├── chart.svg               # generated README sparkline
├── AGENTS.md               # THIS FILE — single source of truth (spec + conventions)
└── README.md               # public one-liner + badges
```

Outside the repo (reference material, not part of the reminder): `Minion_Calculator-1.2.1.0/` (Herodirk's calculator, source of PROFIT constants) and `HUNTAXEPETPROFIT.md` (Hypixel/Coflnet API docs).

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Recipes, profit model, data model, decision rules | THIS FILE — sections below | Recipes section is the source of truth for every quantity |
| Pipeline wiring / entry point | `.github/workflows/daily-reminder.yml` | cron `50 21 * * *` UTC + workflow_dispatch; delivery enforced by `reminder-watchdog.yml` |
| Prices, facts, PROFIT constants | `.github/scripts/fetch-data.py` | largest script (~800 lines) |
| Craft-vs-sell decision logic | `.github/scripts/decision.py` | RECIPES + GATES dicts |
| Tests | `.github/scripts/test-decision.py` | only test in repo; manual, not CI |
| Lifetime stats | `.github/scripts/update-stats.py` | folds daily snapshot into stats.json |
| Chart | `.github/scripts/generate-chart.py` | raw SVG, zero deps |
| Discord cleanup | `.github/scripts/purge-messages.py` | deletes previous message via webhook |
| State files | repo root `*.json` | committed data, not code |

## CODE MAP

No LSP codemap (Python scripts, no toolchain). Pipeline contract instead:

| Stage | Script | Reads → Writes |
|-------|--------|----------------|
| 0 Purge | purge-messages.py | reminder-state.json → DELETE webhook msgs |
| 1 Fetch | fetch-data.py | Hypixel bazaar + Coflnet + uselessfacts → prices.json, prices.jsonl, $RUNNER_TEMP/*.txt |
| 2 Decide | decision.py | prices.json + stockpile-state.json → $RUNNER_TEMP/decision.txt, stockpile-state.json |
| 3 Send | (inline YAML) | jq embed build + curl → webhook; message ID → reminder-state.json |
| 4 Stats | update-stats.py | $RUNNER_TEMP/stats-day.json → stats.json |
| 5 Chart | generate-chart.py | prices.jsonl → chart.svg |
| 6 Commit | (inline YAML) | git add/commit/push 6 data files |

## DATA MODEL

### prices.jsonl (append-only, one line per successful run)

Each line is a full, rich snapshot:

| Field | Type | Description |
|---|---|---|
| `date` | str | GMT+3 date string (e.g. `2026-08-05`) |
| `ts`, `dow` | int | Unix epoch + day of week (0=Sun) |
| `bazaar_age_s` | int | Age of Hypixel bazaar snapshot in seconds (-1 if unavailable) |
| `prices_source` | str | `hypixel.net quick_status` or `coflnet snapshot` fallback |
| `items` | obj | Per-bazaar-item detail, keyed by tag (see below) |
| `qty` | obj | Daily quantities per fuel tag (INFERNO_FUEL_BLOCK uses 23.33 bazaar qty) |
| `subtotals` | obj | Per-fuel-item daily cost at both price sides |
| `bill_buy_order`, `bill_instabuy` | int | Total daily fuel bill |
| `income_instasell`, `income_sell_order` | int | Daily income after tax |
| `crude_opportunity_cost` | obj | 600 crude burned for fuel (25 Fuel Gabagool x 24 crude), valued at both sell sides |
| `net_buy_order`, `net_instabuy` | int | Daily net profit |
| `alerts` | obj | Spike (text + per-item pct), stockup, craftbuy signals |
| `cookie` | obj | Booster Cookie bazaar price (buy_order / instabuy / week_median_buy) |
| `fact` | obj | The random fact text + matched Wikipedia image title/url |

Item tags: SULPHURIC_COAL, CRUDE_GABAGOOL_DISTILLATE, INFERNO_FUEL_BLOCK, CRUDE_GABAGOOL, VERY_CRUDE_GABAGOOL, FUEL_GABAGOOL, HEAVY_GABAGOOL, HYPERGOLIC_GABAGOOL, BOOSTER_COOKIE.

Each `items` entry:

| Field | Description |
|---|---|
| `buy_order`, `instabuy`, `instasell`, `sell_order` | int — all four price sides (two distinct bazaar prices, named per use case) |
| `buy_volume_day`, `sell_volume_day` | int — daily volume both sides |
| `buy_moving_week`, `sell_moving_week` | int — 7-day moving volume both sides |
| `week.buy` / `week.sell` | obj — from Coflnet hourly history: median, avg, min, max, MAD, point count |
| `order_book` | obj — top 3 buy/sell orders `[[price, amount]]`, top3 units, `thin` flag (manipulation heuristic) |
| `today_vs_week_median_buy_pct` | float/null — today's instabuy vs its 7-day median |

### stats.json (overwritten each run)

`refuels` (first run per GMT+3 day counts), `fuel_blocks` (50/refuel), `total_net_bo/ib`, `total_income_sell/order`, `total_spent_bo/ib`, `total_crude_opp_sell/order`, `best_day_net_bo/ib` + date, `worst_day_net_ib` + date, `best_day_income_sell` + date, `avg_net_bo/ib`, `avg_income_sell/order`, `avg_spent_bo/ib`, `avg_crude_opp_sell`, `spike_days`/`stockup_days`/`craftbuy_days`, `last_spike`/`last_stockup_pct`/`last_craftbuy_savings`, `days_hyper`/`days_gabagool`/`days_sell`/`days_hold`, `hyper_rec_total`, `best_margin_hyper` + date, `last_margin_hyper`, `*_disp` formatted badge strings, `first_day`, `last_day`, `days_tracked`.

### prices.json (overwritten daily)

Top-level badge strings the README consumes (`fuel_bill`, `net_buy_order`, `coal`, `distillate`, `fuel_block`, `income_sell`, `income_order`, `net_instabuy`, `crude`), then the full rich snapshot under `items` (same structure as a prices.jsonl line's `items`) plus `qty`, `subtotals`, `bill`, `income`, `net`, `alerts`, `generated_at_utc`, `prices_source`.

## PROFIT MODEL

Constants in `fetch-data.py` > `PROFIT` dict, sourced from Herodirk's Minion Calculator for this exact setup: 25x Inferno T3 minions, Fuel Gabagool grade, Gabagool Distillate, Force Rising Celsius, Super Compactor 3000, Minion Expander, Large Storage, Beacon V + Scorched Power Crystal, Postcard, offline (no AFK). If the layout changes, re-run the calculator at `https://herodirk.github.io/minion/calculator/main.html` and update the `PROFIT` constants.

```
sold_crude = crude_per_day - crude_used_per_day  (4030.66 - 600 = 3430.66)
income = (sold_crude * crude_price + very_crude_per_day * very_crude_price) * (1 - sell_tax)
```

Crude price uses instasell for the `income_sell` side or sell order for `income_order`. `sell_tax = 0.0125` (1.25%, no Bazaar Flipper perk); tax applies to ALL bazaar sales including sell offers, so both income sides are taxed equally.

```
blocks_from_bits = 6000 bits/cookie / 4 days / (3600 bits per 64 blocks) = 26.67/day
blocks_from_bazaar = max(0, 50 - 26.67) = 23.33/day
cost = 25 * coal_price + 150 * distillate_price + 23.33 * fuel_block_price
```

The user buys booster cookies continuously for 24/7 uptime, so bits are a free sunk byproduct. ~26.7 of the 50 daily Inferno Fuel Blocks come from bits (Elizabeth's shop, 64 for 3600 bits); only the ~23.3 shortfall is priced at bazaar. Buy order side uses `_bo` prices, instabuy side uses `_ib` prices.

```
net_bo = income_sell - cost_bo    (sell instantly, buy patiently)
net_ib = income_sell - cost_ib    (sell instantly, buy instantly)
```

## OFFICIAL RECIPES (user-confirmed — do not hallucinate)

Confirmed verbatim by the owner on 2026-08-05. Source of truth for every quantity in the profit model, cost formula, and decision engine. If any calculation disagrees with this list, the LIST is right and the calculation is wrong. Also hardcoded in `decision.py` > `RECIPES` — keep the two in sync.

| Inputs | Outputs | Used for |
|---|---|---|
| 192 Crude Gabagool | 1 Very Crude Gabagool | Super Compactor 3000 auto-compaction (33,600 crude/day → 175 very/day) |
| 24 Crude Gabagool + 1 Sulphuric Coal | 1 Fuel Gabagool | Daily fuel (25/day burned = 600 crude + 25 coal) |
| 8 Sulphuric Coal + 1 Very Crude Gabagool | 8 Fuel Gabagool | Decision play B (1 very → 8 gabagool) |
| 24 Fuel Gabagool + 1 Sulphuric Coal | 1 Heavy Gabagool | Hypergolic chain intermediate |
| 12 Heavy Gabagool + 1 Sulphuric Coal | 1 Hypergolic Gabagool | Decision play C end product |

### Derived quantities (already checked — do not re-derive)

- **1 Hypergolic = 36 Very Crude + 301 Sulphuric Coal** (12 heavy → 288 Fuel Gabagool + 12 coal, + 1 coal final step = 288 FG + 13 coal; 288 FG = 36 very + 288 coal via the 8-coal recipe; total = 36 very + 301 coal). Used in `hyper_margin` and the daily craft decision.
- **1 Hypergolic = 288 Fuel Gabagool + 13 Sulphuric Coal** (chain form).
- **25 Fuel Gabagool (daily fuel burn) = 600 Crude + 25 Sulphuric Coal** (`crude_used_per_day = 600`, NOT 675).
- **175 Very Crude/day = 33,600 Crude compacted** at 192:1 — forced by the Super Compactor 3000, not a choice.
- **1,400 Fuel Gabagool = 175 Very + 1,400 Sulphuric Coal** (full day of play B).

### What is NOT a recipe

Inferno Minion Fuel itself has NO bazaar market (verified across Hypixel items API, bazaar, Coflnet AH, and NEU repo). It is crafted in-game via supercraft from Fuel Gabagool + Gabagool Distillate + Inferno Fuel Block; the exact in-game fuel ratios are not part of these recipes and were never confirmed — do not invent them.

## PRICE ALERTS

Three signals run each day using Coflnet's 7-day bazaar history:

- **Price spike (upward only)**: per item, if today's instabuy is >= 10% above the 7-day median AND outside the 3xMAD noise band. Only upward moves (a drop is an opportunity, not a warning). Order-book thinness (top 3 asks < 25 units = likely price painting) flagged as "(thin)".
- **Stock-up signal**: same median+MAD logic on the total daily fuel bill; fires when the bill is clearly below its weekly median — cheap day to stock up.
- **Craft-vs-buy tip**: finished Inferno Minion Fuel has no market, so this watches Fuel Gabagool (the buyable intermediate). Compares buy-order price vs craft cost (just the coal — crude is free from minions). Fires only when buying is >= 5% cheaper with real supply.

## DAILY CRAFT DECISION (decision.py)

Every run compares three uses of the day's 175 very crude (fixed by the Super Compactor 3000 — the split is not a choice): sell raw (baseline), craft into Fuel Gabagool (8 coal + 1 very = 8 gabagool), craft into Hypergolic (36 very + 301 coal = 1 hypergolic via the full chain).

### Price-side convention (IMPORTANT)

All margins use ONE consistent side convention: **patient everywhere** — inputs at buy order, outputs at sell order, and the very-crude opportunity cost at its sell order (if you're patient enough to sell-order the crafted product, you're patient enough to sell-order the raw very). The instasell "floor" margin is computed separately as a hard gate.

```
hyper_margin = hyper_anchor * 0.9875 - 36 * very_sell_order * 0.9875 - 301 * coal_buy_order
gab_margin   = 8 * gab_anchor * 0.9875 - 8 * coal_buy_order - very_sell_order * 0.9875
```

### Output price anchoring

A single spot sell_order from the bazaar book can be painted. The expected output price is anchored instead:

```
anchor = median(spot_sell_order, week_median_sell, week_median_sell * 0.9)
```

Falls to the spot quote in a crash, caps a pump at the week median, uses the median in normal markets.

### Decision gates (checked in order)

1. **Liquidity**: Hypergolic needs buy volume >= 50/day (we sell <= 5/day, cap). Fuel Gabagool needs buy volume >= 28,000/day (we'd sell 1,400/day = 5%).
2. **Crash gate**: if an output's instasell < 0.85 x its week-median sell, that output is falling — do not craft into it. If very crude itself is falling, the default becomes HOLD, not sell raw (holding is free).
3. **ROI threshold**: craft Hypergolic only when `hyper_margin >= 0.10 * hyper_anchor` AND the instasell-floor margin >= 0 (can never lose money even if forced to dump). Fuel Gabagool needs `gab_margin >= 15,000`/very and a non-negative floor. A missing/zero instasell makes the floor uncomputable — that blocks the craft (fail closed, never fail open).
4. **Priority**: Hypergolic > Fuel Gabagool > sell raw, with HOLD replacing sell raw whenever very crude is falling.

### Whole-number crafting + stockpile

You can't craft 4.86 hypergolics — only whole ones. 175 very makes 4 with 31 rolled over. `stockpile-state.json` is a **recommendation ledger** (the bot can't observe what you actually do in-game): cumulative `very_produced` and `very_consumed` flows, derived `very_held = produced - consumed`, plus a 7-day margin history. Updates are date-guarded (first decision per GMT+3 day only), so a failed send that never gets committed self-heals on the next run — the same-day rerun re-adds exactly once. Manual edits allowed for drift correction; the embed shows the estimate.

### decision.txt (the embed field)

Plain text, no emojis, `|` separators. Example (HOLD day):

```
Decision - Hold - market falling
very crude 28% below 7d avg | hypergolic 23% below 7d avg
Craft trigger: hypergolic sell order > 4.65M | margin +438.1K now
Margins vs sell raw: Hypergolic +438.1K/unit | Gabagool +17.6K/very | sell very 66.8K/very
Stockpile - 175 very held | sell raw if you need coins
```

The `(thin)` flag on Gabagool means its liquidity gate blocked it — highest margin on paper, least executable.

## FACT SYSTEM

Facts come from the **uselessfacts API** (`uselessfacts.jsph.pl`) — keyless, random facts (history, science, pop culture, animals, world events). A Wikipedia image is matched with a single API call per candidate (`generator=search` + `prop=pageimages` returns the top article AND its thumbnail in one request, so rate limits stay low):

1. Candidate keywords ranked: proper-noun phrases (consecutive Title-Case words, e.g. "Great Wall") first, then capitalized proper nouns, then longest nouns. Noise filtered: stop words, verbs (glows, weighs, found...), generic time words (year, day, hour...), superlatives (youngest, biggest...).
2. Up to 3 candidates tried, one lookup each with ~1s spacing.
3. A candidate wins only if the article has a lead thumbnail — disambiguation pages and bad matches fall through to the next candidate.
4. No image found → fact shown without image.
5. uselessfacts down → falls back to 36 curated animal facts with guaranteed images.

The chosen fact + matched image title/url are logged in the prices.jsonl line.

## CONVENTIONS

- **Python 3.12+, stdlib only** — no requirements.txt, no venv, no pip install anywhere
- **Scripts are standalone** — zero shared imports; data flows through files, never function calls
- **Comments stripped** — code self-documents via function names; docstrings carry purpose/I-O/failure behavior
- **No emojis anywhere** — embed text, animal facts, code
- **Separators**: `|` between buy order/instabuy pairs; `/` only in `/day` (meaning "per day")
- **Prices format**: `buy order | instabuy` for shopping list items and fuel cost, `instasell | sell order` for income
- **Crude Gabagool** always shown as "free" in the shopping list (minions produce it); opportunity cost logged in data but not shown
- **Fuel block line** shows only the bazaar-purchased quantity (bits-free portion not mentioned): `50x Inferno Fuel Block - 23x @ 56.7K buy order | 60.6K instabuy`
- **Discord embed is plain text** — no markup, no footer (a timestamp there was deemed clutter)
- **Stats dedup**: only the FIRST run per GMT+3 calendar day increments `stats.json`; reruns/testing won't inflate refuel count
- **Chart dedup**: `generate-chart.py` plots only the FIRST data point per date; chart also draws a dashed 7-day moving average (blue) with a legend in the top-right
- **Price-side convention**: patient everywhere (see Daily craft decision section)
- **JSON**: snake_case keys, `indent=1`, `encoding="utf-8"` everywhere; prices.jsonl append-only
- **Secrets**: env only, never hardcoded/echoed (see Secrets section)
- Pre-push gate: `python3 -m py_compile .github/scripts/*.py`

## ANTI-PATTERNS (THIS PROJECT)

- **Hallucinating recipe quantities** — the Official recipes section is the source of truth; if a calculation disagrees, the LIST is right
- **Re-deriving derived quantities** (1 Hypergolic = 36 very crude + 301 coal, etc.) — already checked, use as-is
- **Inventing in-game fuel ratios** — never confirmed, do not invent
- **Comments in code; shared imports between scripts**
- **Hardcoding/echoing secrets**
- **Emojis, markup, or footer in embeds**
- **External dependencies** (stdlib only)
- Manual edits to data files — only `stockpile-state.json` drift correction is allowed
- **Divergence between RECIPES (decision.py) and the Official recipes section** — keep in sync

## UNIQUE STYLES

- **Self-modifying CI**: workflow commits data files back to main; merge-then-checkout trick guarantees bot snapshot wins, so manual data commits can never break a run
- **Error-tolerant pipeline**: every Python step `|| echo "fallback"` — a script failing never fails the job
- **Orchestration is split-brain**: data in Python, embed+commit logic inline in YAML shell (jq + curl)
- **Workflow itself is the entry point** — no runtime entry, cron IS the trigger
- Commit messages lowercase + short ("update reminder state and price snapshots", "keepalive")

## SECRETS

Set in GitHub repo Settings > Secrets and variables > Actions:
- `DISCORD_WEBHOOK_URL` — the webhook URL
- `DISCORD_USER_ID` — your Discord user ID (for the @mention)

These are NEVER hardcoded, never echo'd to logs. GitHub automatically masks them in Actions output.

## COMMANDS

```bash
# syntax gate (before any push)
python3 -m py_compile .github/scripts/*.py

# the only test in the repo (offline, ~10 fixture cases)
python3 .github/scripts/test-decision.py

# E2E local run (from repo root; then reset data files to placeholders before committing)
export RUNNER_TEMP=/tmp/e2e && mkdir -p $RUNNER_TEMP
python3 .github/scripts/fetch-data.py   # check $RUNNER_TEMP/shopping-list.txt, profit.txt, stats-day.json
python3 .github/scripts/decision.py     # check $RUNNER_TEMP/decision.txt + repo stockpile-state.json
python3 .github/scripts/update-stats.py # check stats.json
python3 .github/scripts/generate-chart.py # check chart.svg
python3 .github/scripts/test-decision.py

# then reset placeholders: prices.json, prices.jsonl, stats.json, chart.svg, stockpile-state.json

# manual CI trigger
gh workflow run daily-reminder.yml
```

## NOTES

- **This dev machine shell is PowerShell 5.1**: no `&&` (use `;` or `if ($?) {}`), no bash `set VAR="x"` (use `$env:VAR = "x"`), skip Linux-only env vars entirely — plain commands work fine
- **AGENT GOTCHA — never call git/bash directly in this environment**: the command wrapper injects a bash-style prefix (`set CI="true" && set DEBIAN_FRONTEND=... && git ...`) into any command containing git, which PowerShell 5.1 rejects at parse time ("The token '&&' is not a valid statement separator"). This happens for ANY command that contains the string `git`, including `python -c "...git..."`. The reliable workaround is to drive git through a Python subprocess wrapper script (e.g. a temp file that calls `subprocess.run(["git", ...])` with `cwd` set), or use plain `python <script>.py` for anything non-git. `python -m py_compile`, `python <script>.py`, and `cmdkey /list` all work fine un-wrapped; `git ...` and `python -c "...git..."` do not
- Checkout lives at repo root (`C:\Users\1\Desktop\Inferno`) — an older version of this doc claimed a nested `...\Inferno\inferno` path; the root is correct
- **Auto-commit merge**: the workflow merges `origin/main` then forces its own snapshot of the 6 data files to win (`git checkout HEAD --` on reminder-state.json, prices.json, prices.jsonl, stats.json, chart.svg, stockpile-state.json), so manual commits to data files or late deliveries can never break the run — the new message ID always lands in the repo
- **Chart SVG colors are hardcoded** — visible on light mode GitHub, invisible on dark mode (would need `@media (prefers-color-scheme: dark)`)
- **shields.io badges have ~5 min cache** — won't update immediately after push; Discord embed footers don't support markdown links (raw URLs auto-link but can't be masked)
- **GitHub cron runs late**: the Actions scheduler routinely fires `schedule` jobs 30-120 min after the cron minute (observed 2026-08-05: 02:55 Moscow vs 00:45 target). This is platform behavior, not a repo bug. Real timing guarantee comes from `reminder-watchdog.yml`: ticks at 21:50 and every 10 min 22:00-23:50 UTC, and re-dispatches `daily-reminder.yml` unless `reminder-state.json`'s `sent_at` is already today (Moscow). The guard step at the top of daily-reminder.yml (`steps.guard.outputs.skip`) skips the whole job when today's reminder already sent, so overlapping triggers (cron + watchdog + manual dispatch) can't double-send; the watchdog throttles re-dispatches to one per 30 min via `.github/dispatch-marker.json` (committed by the watchdog). Known accepted tradeoff: if a run sends but its git push fails, the next watchdog tick re-dispatches -> rare duplicate embed.
- **Moscow timezone** is UTC+3 fixed (no DST): workflows use `TZ='Etc/GMT-3'` — works even without tzdata on the runner (the `Europe/Moscow` zone name silently degrades to UTC if tzdata is missing, which would break the sent-today dedup)
- **Hypixel bazaar age** compares remote API timestamp to local VM clock — clock drift can produce slightly inaccurate age values
- **Wikipedia rate limits**: keyless API can 429 on bursts; lookups spaced ~1s apart, Retry-After backoff, 3-candidate cap — worst case is a fact with no image, never a failure
- **Coflnet asks for ~1 req/sec** — snapshot + history fetches spaced out; every cofl call is individually optional so one failure can't kill the run
- **Fetch network budget**: `fetch-data.py` caps total network time at 360s (`NET_BUDGET` + `START` in `get()`), so even an everything-hangs day degrades to missing prices instead of exceeding the workflow's 10-min job timeout — worst case is a thin reminder, never no reminder
- `.sisyphus/` and `log.txt` contain agent session tooling — not project code; now covered by `.gitignore` (`__pycache__/`, `*.pyc`, `.sisyphus/`, `log.txt`) so `git add -A` can never sweep them in
- **Data reset 2026-08-06**: `stats.json`, `prices.json`, `prices.jsonl`, `stockpile-state.json`, and `chart.svg` were wiped to fresh placeholders (stats all-zero, empty history, empty ledger, chart placeholder) — lifetime stats and the chart start clean from that date. The next successful run repopulates everything; `chart.svg` needs 2+ days of data to draw again

## MINION CALCULATOR REFERENCE

The `Minion_Calculator-1.2.1.0/` directory contains Herodirk's calculator source — reference material, NOT part of the reminder. The `PROFIT` constants in `fetch-data.py` were derived by plugging the specific minion layout into the calculator. To verify or update: open `https://herodirk.github.io/minion/calculator/main.html` and input the layout from the Profit model section.

Minion layout ID: `1.2.2!W2!25!@237351000!1!012401004!0!00000!0!!0!!0!!0!!0!!0!0!0!4!0!000!0!!0!4!0!4!0!40000110!1!20!1!20`

Note: the user has 25 minions down, not 29 (the layout ID says 29, but the calculator was configured with amount=25).
