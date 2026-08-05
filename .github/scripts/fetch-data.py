"""Fetch the data for the Inferno reminder embed.

Pulls a random fact (uselessfacts) plus a matching Wikipedia image, then
captures the full bazaar picture for every relevant item: both price sides
(buy order / instabuy, instasell / sell order), daily and 7-day moving
volumes, the top of the order book, and per-item 7-day median/MAD/min/max
computed from Coflnet's hourly history. Writes a rich snapshot to
prices.json, appends a rich line to prices.jsonl, and writes the embed text
files into $RUNNER_TEMP. Every external source fails gracefully so the
reminder always sends.
"""

import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "inferno-reminder/1.0 (GitHub Actions daily reminder)"}
TMP = os.environ.get("RUNNER_TEMP", "/tmp")
NET_BUDGET = 360.0  # hard cap on total network time, keeps the job under GitHub's 10-minute workflow timeout
START = time.monotonic()
HY = "https://api.hypixel.net/skyblock/bazaar"
COFL = "https://sky.coflnet.com/api/bazaar"
WIKI = "https://en.wikipedia.org/w/api.php"
FACTS_URL = "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"
MIN_PCT = 10.0
MAD_MULT = 3.0
THIN_UNITS = 25
BUY_CHEAP_PCT = 5.0
GABAGOOL = "FUEL_GABAGOOL"

PROFIT = {
    "crude_per_day": 4030.66,
    "very_crude_per_day": 175,
    "crude_used_per_day": 600,
    "coal_per_day": 25,
    "distillate_per_day": 150,
    "fuel_block_per_day": 50,
    "fuel_blocks_from_bits": 26.67,
    "sell_tax": 0.0125,
}

FUEL_TAGS = ["SULPHURIC_COAL", "CRUDE_GABAGOOL_DISTILLATE", "INFERNO_FUEL_BLOCK"]
ALL_TAGS = FUEL_TAGS + [
    "CRUDE_GABAGOOL",
    "VERY_CRUDE_GABAGOOL",
    GABAGOOL,
    "HEAVY_GABAGOOL",
    "HYPERGOLIC_GABAGOOL",
    "BOOSTER_COOKIE",
]
SHORT_NAMES = {
    "SULPHURIC_COAL": "coal",
    "CRUDE_GABAGOOL_DISTILLATE": "distillate",
    "INFERNO_FUEL_BLOCK": "fuel block",
}
NAMES = {
    "SULPHURIC_COAL": "Sulphuric Coal",
    "CRUDE_GABAGOOL_DISTILLATE": "Gabagool Distillate",
    "INFERNO_FUEL_BLOCK": "Inferno Fuel Block",
    "CRUDE_GABAGOOL": "Crude Gabagool",
    "VERY_CRUDE_GABAGOOL": "Very Crude Gabagool",
    GABAGOOL: "Fuel Gabagool",
    "HEAVY_GABAGOOL": "Heavy Gabagool",
    "HYPERGOLIC_GABAGOOL": "Hypergolic Gabagool",
    "BOOSTER_COOKIE": "Booster Cookie",
}

FALLBACK_FACTS = [
    ("Octopus", "Octopuses have three hearts, blue blood, and can change colour and shape to blend into almost any surface."),
    ("Axolotl", "Axolotls can regenerate lost limbs, organs, and even parts of their brain - and never grow out of their larval stage."),
    ("Tardigrade", "Tardigrades can survive boiling water, deep space, and decades without food or water."),
    ("Mantis shrimp", "Mantis shrimp see four times more colours than humans and punch with the force of a bullet."),
    ("Naked mole-rat", "Naked mole-rats barely feel pain, rarely get cancer, and can live past 30 - far longer than any other rodent."),
    ("Wombat", "Wombats are the only animals in the world that produce cube-shaped droppings."),
    ("Wood frog", "Wood frogs freeze solid in winter - hearts stop, breathing stops - and thaw out alive in spring."),
    ("Honey badger", "Honey badgers fear nothing: they take on lions and snakes and shrug off most snake venom."),
    ("Cheetah", "A cheetah can reach 100 km/h in about three seconds - faster off the line than most sports cars."),
    ("Peregrine falcon", "Peregrine falcons are the fastest animals on Earth, hitting over 300 km/h in a dive."),
    ("Emperor penguin", "Emperor penguins are the only penguins that breed through the Antarctic winter, in temperatures down to -60 C."),
    ("Giraffe", "Giraffes have the same number of neck bones as humans, and a heart big enough to pump blood 2 metres up to the brain."),
    ("Kangaroo", "Female kangaroos can pause a pregnancy until the joey already in the pouch is ready to leave."),
    ("Fennec fox", "Fennec foxes use their giant ears as radiators to keep cool in the desert."),
    ("Polar bear", "A polar bear's skin is black and its fur is actually transparent - it only looks white."),
    ("Elephant", "Elephants pick up vibrations through their feet and can 'hear' other elephants from kilometres away."),
    ("Hippopotamus", "Hippos can't swim or float - they walk along the bottom of rivers and can hold their breath for five minutes."),
    ("Sperm whale", "Sperm whales dive over 2 km deep and can hold their breath for over an hour."),
    ("Narwhal", "The narwhal's 'horn' is actually a tooth that can grow up to 3 metres long."),
    ("Great white shark", "Great white sharks can smell a single drop of blood in 100 litres of water."),
    ("Hagfish", "Hagfish flood predators with litres of instant slime that clogs their gills."),
    ("Cuttlefish", "Cuttlefish change colour and texture in a blink, and have three hearts and blue-green blood."),
    ("Giant squid", "Giant squids have the largest eyes of any animal - about the size of dinner plates."),
    ("Bombardier beetle", "Bombardier beetles blast predators with a boiling-hot chemical spray from their abdomens."),
    ("Dung beetle", "Dung beetles roll dung balls far heavier than themselves, and some navigate by the Milky Way."),
    ("Leafcutter ant", "Leafcutter ants don't eat the leaves they cut - they use them to grow a fungus garden, which they eat."),
    ("Scorpion", "Scorpions glow blue-green under ultraviolet light."),
    ("Komodo dragon", "Komodo dragons have a venomous bite and can take down prey as large as water buffalo."),
    ("Chameleon", "Chameleons move each eye independently and can catch prey with their tongue in a fraction of a second."),
    ("Capybara", "Capybaras are the biggest rodents on Earth, weighing up to 66 kg, and are excellent swimmers."),
    ("Sea otter", "Sea otters hold hands while sleeping so they don't drift apart, and use rocks as tools."),
    ("Honey bee", "Honey bees tell hive-mates exactly where flowers are with a 'waggle dance'."),
    ("Ocean sunfish", "Ocean sunfish can lay up to 300 million eggs at once - more than any other vertebrate."),
    ("Horseshoe crab", "Horseshoe crabs have blue blood that medicine uses to test vaccines for contamination."),
    ("Pangolin", "Pangolins are the only mammals covered in scales, and roll into an armoured ball when threatened."),
    ("Aye-aye", "Aye-ayes tap on wood with a long skinny finger to find grubs, then hook them out - nature's woodpecker."),
]

STOP_WORDS = {
    "a", "an", "the", "is", "was", "are", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "about",
    "that", "this", "it", "its", "all", "has", "have", "had", "can",
    "not", "than", "or", "as", "if", "but", "so", "no", "more", "most",
    "some", "any", "each", "every", "both", "few", "many", "much", "such",
    "only", "other", "new", "old", "first", "last", "long", "great",
    "little", "own", "same", "right", "still", "just", "too", "very",
    "also", "even", "then", "now", "here", "there", "when", "where",
    "why", "how", "which", "who", "whom", "whose", "what", "one", "two",
    "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "will", "would", "could", "should", "may", "might", "must", "into",
    "over", "after", "before", "between", "under", "again", "once",
    "during", "above", "below", "up", "down", "out", "off", "away",
    "back", "ever", "never", "always", "often", "sometimes", "usually",
    "around", "through", "without", "within", "against", "because",
    "while", "since", "until", "though", "although", "even", "really",
    "actually", "almost", "nearly", "exactly", "about", "around",
    "approximately", "roughly", "usually", "generally", "probably",
    "literally", "basically", "extremely", "absolutely", "certainly",
    "apparently", "reportedly", "simply", "currently", "typically",
    "eventually", "occasionally", "frequently", "rarely", "especially",
    "particularly", "surprisingly", "interestingly", "commonly",
    "today", "yesterday", "tomorrow", "ever", "never", "always",
    "million", "millions", "billion", "billions", "thousand",
    "thousands", "hundred", "hundreds", "trillion", "dozen", "dozens",
}

NOISE_VERBS = {
    "glows", "grows", "lives", "lived", "takes", "took", "taken", "makes",
    "made", "holds", "held", "found", "called", "known", "became",
    "becomes", "uses", "used", "eats", "ate", "eaten", "sleeps", "weighs",
    "reaches", "reached", "measures", "contains", "produces", "travels",
    "traveled", "gives", "gave", "given", "named", "built", "discovered",
    "invented", "created", "recorded", "says", "said", "seen", "saw",
    "spoils", "lasts", "died", "born", "killed", "fought", "won", "lost",
    "breaks", "sticks", "bends",    "flows", "falls", "rises",
    "feels", "turns", "causes", "comes", "goes", "gets", "become",
}

GENERIC_TIME = {
    "year", "years", "day", "days", "time", "times", "hour", "hours",
    "minute", "minutes", "second", "seconds", "percent", "percents",
    "century", "centuries", "decade", "decades", "week", "weeks",
    "month", "months", "date", "dates", "age", "ages", "era", "eras",
    "period", "periods", "moment", "moment",
}

SUPERLATIVES = {
    "youngest", "oldest", "largest", "biggest", "smallest", "longest",
    "shortest", "fastest", "slowest", "strongest", "weakest", "highest",
    "lowest", "most", "least", "greatest", "rarest", "commonest",
}

FACT_INFO = {"text": "", "image_title": "", "image_url": ""}


def get(url, timeout=20, tries=2):
    last = None
    for attempt in range(tries):
        remaining = NET_BUDGET - (time.monotonic() - START)
        if remaining <= 1.0:
            break
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=min(timeout, remaining)) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            wait = 0.8 * (attempt + 1)
            if exc.code == 429 and exc.headers:
                ra = exc.headers.get("Retry-After")
                if ra:
                    try:
                        wait = min(float(ra), 10.0)
                    except ValueError:
                        pass
            time.sleep(min(wait, max(0.0, remaining - 1.0)))
        except Exception as exc:
            last = exc
            time.sleep(min(0.8 * (attempt + 1), max(0.0, remaining - 1.0)))
    if last is None:
        last = TimeoutError("network budget exhausted")
    raise last


def write_file(name, text):
    with open(os.path.join(TMP, name), "w", encoding="utf-8") as f:
        f.write(text)


def repo_write(name, text):
    with open(name, "w", encoding="utf-8") as f:
        f.write(text)


def repo_append(name, text):
    with open(name, "a", encoding="utf-8") as f:
        f.write(text)


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def fmt(n):
    if n <= 0:
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


def wiki_lookup(term):
    url = (
        WIKI + "?action=query&format=json&generator=search&gsrsearch=%s&gsrlimit=1"
        "&prop=pageimages&piprop=thumbnail&pithumbsize=640" % urllib.parse.quote(term)
    )
    d = get(url, timeout=15)
    pages = (d or {}).get("query", {}).get("pages") or {}
    for pid in pages:
        p = pages[pid]
        thumb = (p.get("thumbnail") or {}).get("source") or ""
        if thumb:
            return p.get("title") or term, thumb
    return None, None


def fact_candidates(fact):
    clean = re.sub(r"[^A-Za-z ]+", " ", fact)
    words = clean.split()
    if not words:
        return []

    def title_case(w):
        return len(w) >= 2 and w[0].isupper() and w[1:].islower()

    cands = []
    i = 0
    n = len(words)
    while i < n:
        if title_case(words[i]):
            j = i
            while j < n and title_case(words[j]):
                j += 1
            part = words[i:j]
            if part and part[0].lower() in {"a", "an", "the", "this", "that", "these", "those"}:
                part = part[1:]
            if part:
                phrase = " ".join(part)
                if phrase.lower() not in STOP_WORDS and len(phrase) >= 3:
                    cands.append((90 + len(phrase), phrase))
            i = j
            continue
        i += 1

    for idx, w in enumerate(words):
        lw = w.lower()
        if len(w) < 4 or lw in STOP_WORDS or lw in NOISE_VERBS or lw in GENERIC_TIME or lw in SUPERLATIVES:
            continue
        score = min(len(w), 14)
        if w[0].isupper() and idx > 0 and words[idx - 1].lower() not in {"a", "an", "the", "this", "that", "these", "those"}:
            score += 15
        if idx > 0 and words[idx - 1].lower() in {"of", "in", "on", "for", "from", "with", "at", "by"}:
            score += 6
        if lw.endswith("s") and len(lw) >= 5:
            score += 3
        cands.append((score, w))

    cands.sort(key=lambda t: t[0], reverse=True)
    out = []
    seen = set()
    for _, c in cands:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
        if len(out) >= 3:
            break
    return out


def find_image_for_fact(fact):
    first = True
    for term in fact_candidates(fact):
        try:
            if not first:
                time.sleep(0.9)
            first = False
            title, thumb = wiki_lookup(term)
        except Exception:
            continue
        if thumb:
            return title or term, thumb
    return None, None


def fetch_fact():
    try:
        r = get(FACTS_URL, timeout=15)
        fact = (r or {}).get("text", "").strip()
        if fact:
            FACT_INFO["text"] = fact
            write_file("animal-fact.txt", fact)
            title, thumb = find_image_for_fact(fact)
            if thumb:
                FACT_INFO["image_title"] = title
                FACT_INFO["image_url"] = thumb
                write_file("animal-name.txt", title)
                write_file("animal-image.txt", thumb)
                print("fact: uselessfacts \"%s\" -> image=%s" % (fact[:60], title))
            else:
                write_file("animal-name.txt", "Random Fact")
                print("fact: uselessfacts \"%s\" (no image)" % fact[:60])
            return
    except Exception:
        pass
    fetch_fallback_fact()


def fetch_fallback_fact():
    entries = list(FALLBACK_FACTS)
    random.shuffle(entries)
    first = True
    for animal, fact in entries[:4]:
        try:
            if not first:
                time.sleep(0.9)
            first = False
            title, thumb = wiki_lookup(animal)
        except Exception:
            continue
        if thumb:
            FACT_INFO["text"] = fact
            FACT_INFO["image_title"] = title or animal
            FACT_INFO["image_url"] = thumb
            write_file("animal-name.txt", title or animal)
            write_file("animal-fact.txt", fact)
            write_file("animal-image.txt", thumb)
            print("fact: fallback animal=%s" % animal)
            return
    title, fact = entries[0]
    FACT_INFO["text"] = fact
    write_file("animal-name.txt", title)
    write_file("animal-fact.txt", fact)
    print("fact: fallback animal=%s (no image)" % title)


def side_prices(d):
    b = d.get("buyPrice") or 0
    s = d.get("sellPrice") or 0
    if b <= 0 and s <= 0:
        return 0.0, 0.0
    if b <= 0:
        return s, s
    if s <= 0:
        return b, b
    return min(b, s), max(b, s)


def cofl_snapshot(tag):
    try:
        return get(COFL + "/" + tag + "/snapshot", timeout=20)
    except Exception:
        return {}


def cofl_week(tag):
    try:
        h = get(COFL + "/" + tag + "/history/week", timeout=20)
    except Exception:
        return []
    if not isinstance(h, list):
        return []
    return [p for p in h if isinstance(p, dict)]


def series_metrics(week, key):
    vals = [p.get(key) for p in week if p.get(key)]
    if not vals:
        return {}
    m = median(vals)
    mad = median([abs(x - m) for x in vals])
    return {
        "median": round(m, 1),
        "avg": round(sum(vals) / len(vals), 1),
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
        "mad": round(mad, 1),
        "points": len(vals),
    }


def build_item(tag, products, snap, week):
    q = (products.get(tag) or {}).get("quick_status") or {}
    raw_b = q.get("buyPrice") or 0
    raw_s = q.get("sellPrice") or 0
    if raw_b <= 0 or raw_s <= 0:
        bo, ib = side_prices(snap)
    else:
        bo, ib = side_prices(q)
    bvol = q.get("buyVolume") or 0
    svol = q.get("sellVolume") or 0
    bmw = q.get("buyMovingWeek") or 0
    smw = q.get("sellMovingWeek") or 0
    if snap:
        bvol = bvol or snap.get("buyVolume") or 0
        svol = svol or snap.get("sellVolume") or 0
        bmw = bmw or snap.get("buyMovingWeek") or 0
        smw = smw or snap.get("sellMovingWeek") or 0
    bos = sorted(
        (snap.get("buyOrders") or []),
        key=lambda o: o.get("pricePerUnit") or 0,
        reverse=True,
    )[:3]
    sos = sorted(
        (snap.get("sellOrders") or []),
        key=lambda o: o.get("pricePerUnit") or 0,
    )[:3]
    top3_units = sum(o.get("amount") or 0 for o in sos)
    wb = series_metrics(week, "buy")
    ws = series_metrics(week, "sell")
    pct = None
    if ib > 0 and wb.get("median"):
        pct = round((ib - wb["median"]) / wb["median"] * 100.0, 2)
    return {
        "tag": tag,
        "name": NAMES.get(tag, tag),
        "buy_order": int(round(bo)),
        "instabuy": int(round(ib)),
        "instasell": int(round(bo)),
        "sell_order": int(round(ib)),
        "buy_volume_day": int(bvol),
        "sell_volume_day": int(svol),
        "buy_moving_week": int(bmw),
        "sell_moving_week": int(smw),
        "week": {"buy": wb, "sell": ws},
        "order_book": {
            "top_buy_orders": [[int(o.get("pricePerUnit") or 0), int(o.get("amount") or 0)] for o in bos],
            "top_sell_orders": [[int(o.get("pricePerUnit") or 0), int(o.get("amount") or 0)] for o in sos],
            "top3_sell_units": int(top3_units),
            "thin": bool(sos) and top3_units < THIN_UNITS,
        },
        "today_vs_week_median_buy_pct": pct,
    }


def spike_pct(item):
    wb = item["week"]["buy"]
    med = wb.get("median")
    mad = wb.get("mad")
    ib = item["instabuy"]
    if wb.get("points", 0) < 3 or not med or mad is None:
        return None
    noise = MAD_MULT * max(mad, med * 0.001)
    pct = (ib - med) / med * 100.0
    if (ib - med) >= noise and pct >= MIN_PCT:
        return round(pct, 1)
    return None


def bill_dip(weeks, today_bill, qtys):
    if today_bill <= 0:
        return ""
    tags = list(qtys)
    series = []
    for tag in tags:
        vals = [p.get("buy") for p in (weeks.get(tag) or []) if p.get("buy")]
        series.append(vals)
    if len(series) < 3:
        return ""
    n = min(len(s) for s in series)
    if n < 3:
        return ""
    bills = [sum(qtys[tags[k]] * series[k][i] for k in range(len(tags))) for i in range(n)]
    med = median(bills)
    if med <= 0:
        return ""
    mad = median([abs(x - med) for x in bills])
    noise = MAD_MULT * max(mad, med * 0.001)
    pct = (med - today_bill) / med * 100.0
    if (med - today_bill) >= noise and pct >= MIN_PCT:
        return "Stock up - fuel bill %d%% below 7d avg" % int(pct)
    return ""


def craft_buy_tip(gab_bo, coal_ib, gab_vol):
    if gab_bo <= 0 or coal_ib <= 0:
        return ""
    if gab_vol < 25 * 7:
        return ""
    craft = coal_ib
    if gab_bo <= craft * (1.0 - BUY_CHEAP_PCT / 100.0):
        saved = (craft - gab_bo) * 25
        return "Fuel tip - buy Fuel Gabagool, save %s/day" % fmt(saved)
    return ""


def pair(bo, ib):
    if bo <= 0 or ib <= 0:
        return ""
    if round(bo) == round(ib):
        return fmt(ib)
    return "%s buy order | %s instabuy" % (fmt(bo), fmt(ib))


def fetch_prices():
    products = {}
    bazaar_age = -1.0
    prices_source = "coflnet snapshot"
    try:
        bz = get(HY, timeout=30)
        products = (bz or {}).get("products") or {}
        last = (bz or {}).get("lastUpdated") or 0
        if last:
            ms = last if last > 10 ** 11 else last * 1000.0
            bazaar_age = max(0.0, (time.time() * 1000 - ms) / 1000.0)
            prices_source = "hypixel.net quick_status"
            print("bazaar snapshot age: %.0fs (fetched live this run)" % bazaar_age)
    except Exception:
        pass

    snaps = {}
    for i, tag in enumerate(ALL_TAGS):
        if i:
            time.sleep(0.7)
        snaps[tag] = cofl_snapshot(tag)

    weeks = {}
    for i, tag in enumerate(ALL_TAGS):
        if i:
            time.sleep(0.7)
        weeks[tag] = cofl_week(tag)

    items = {}
    for tag in ALL_TAGS:
        items[tag] = build_item(tag, products, snaps[tag], weeks[tag])

    coal = items["SULPHURIC_COAL"]
    dist = items["CRUDE_GABAGOOL_DISTILLATE"]
    fb = items["INFERNO_FUEL_BLOCK"]
    crude = items["CRUDE_GABAGOOL"]
    very = items["VERY_CRUDE_GABAGOOL"]
    gab = items[GABAGOOL]

    coal_bo, coal_ib = coal["buy_order"], coal["instabuy"]
    dist_bo, dist_ib = dist["buy_order"], dist["instabuy"]
    fb_bo, fb_ib = fb["buy_order"], fb["instabuy"]
    gab_bo = gab["buy_order"]
    gab_vol = gab["buy_moving_week"]
    crude_bo, crude_ib = crude["buy_order"], crude["instabuy"]
    very_bo, very_ib = very["buy_order"], very["instabuy"]

    fb_bazaar = max(0.0, PROFIT["fuel_block_per_day"] - PROFIT["fuel_blocks_from_bits"])
    fb_buy = int(round(fb_bazaar))

    lines = ["600x Crude Gabagool - free"]
    total = 0
    all_priced = True

    cp = pair(coal_bo, coal_ib)
    if cp:
        total += PROFIT["coal_per_day"] * coal_ib
        lines.append("25x Sulphuric Coal - %s" % cp)
    else:
        all_priced = False
        lines.append("25x Sulphuric Coal")

    dp = pair(dist_bo, dist_ib)
    if dp:
        total += PROFIT["distillate_per_day"] * dist_ib
        lines.append("150x Gabagool Distillate - %s" % dp)
    else:
        all_priced = False
        lines.append("150x Gabagool Distillate")

    fp = pair(fb_bo, fb_ib)
    if fp:
        total += fb_bazaar * fb_ib
        lines.append("50x Inferno Fuel Block - %dx @ %s" % (fb_buy, fp))
    else:
        all_priced = False
        lines.append("50x Inferno Fuel Block")

    total_bo = 0
    if all_priced and total > 0:
        total_bo = int(
            PROFIT["coal_per_day"] * coal_bo
            + PROFIT["distillate_per_day"] * dist_bo
            + fb_bazaar * fb_bo
        )
        lines.append("Total - %s buy order | %s instabuy" % (fmt(total_bo), fmt(total)))

    write_file("shopping-list.txt", "\n".join(lines))
    print("prices: coal=%s dist=%s/%s fb=%s/%s total=%s" % (
        fmt(coal_ib), fmt(dist_bo), fmt(dist_ib), fmt(fb_bo), fmt(fb_ib),
        fmt(total)))

    cost_bo = cost_ib = 0.0
    if all_priced:
        cost_bo = (
            PROFIT["coal_per_day"] * coal_bo
            + PROFIT["distillate_per_day"] * dist_bo
            + fb_bazaar * fb_bo
        )
        cost_ib = (
            PROFIT["coal_per_day"] * coal_ib
            + PROFIT["distillate_per_day"] * dist_ib
            + fb_bazaar * fb_ib
        )

    spikes = {}
    spike = ""
    parts = []
    for tag in FUEL_TAGS:
        p = spike_pct(items[tag])
        spikes[tag] = p
        if p is None:
            continue
        label = "%s %+.0f%%" % (SHORT_NAMES[tag], p)
        if items[tag]["order_book"]["thin"]:
            label += " (thin)"
        parts.append(label)
    if parts:
        spike = "Price alert - %s vs 7d avg" % " | ".join(parts)

    stock = bill_dip(weeks, cost_ib, {
        "SULPHURIC_COAL": PROFIT["coal_per_day"],
        "CRUDE_GABAGOOL_DISTILLATE": PROFIT["distillate_per_day"],
        "INFERNO_FUEL_BLOCK": fb_bazaar,
    })
    tip = craft_buy_tip(gab_bo, coal_ib, gab_vol)
    extras = [e for e in (spike, stock, tip) if e]

    stock_pct = None
    if stock:
        m = re.search(r"(\d+)%", stock)
        if m:
            stock_pct = int(m.group(1))

    subtotals = {
        "SULPHURIC_COAL": {
            "qty": PROFIT["coal_per_day"],
            "buy_order": int(PROFIT["coal_per_day"] * coal_bo),
            "instabuy": int(PROFIT["coal_per_day"] * coal_ib),
        },
        "CRUDE_GABAGOOL_DISTILLATE": {
            "qty": PROFIT["distillate_per_day"],
            "buy_order": int(PROFIT["distillate_per_day"] * dist_bo),
            "instabuy": int(PROFIT["distillate_per_day"] * dist_ib),
        },
        "INFERNO_FUEL_BLOCK": {
            "qty": round(fb_bazaar, 2),
            "buy_order": int(fb_bazaar * fb_bo),
            "instabuy": int(fb_bazaar * fb_ib),
        },
    }
    qty_map = {
        "SULPHURIC_COAL": PROFIT["coal_per_day"],
        "CRUDE_GABAGOOL_DISTILLATE": PROFIT["distillate_per_day"],
        "INFERNO_FUEL_BLOCK": fb_bazaar,
    }
    alerts = {
        "spike": spike or None,
        "spike_pct": spikes,
        "stockup": stock or None,
        "stockup_pct": stock_pct,
        "craftbuy": tip or None,
        "craftbuy_savings": int(round((coal_ib - gab_bo) * 25)) if tip and gab_bo > 0 and coal_ib > 0 else None,
    }

    day = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 3 * 3600))
    income_available = crude_ib > 0 and very_ib > 0 and all_priced
    if income_available:
        sold_crude = PROFIT["crude_per_day"] - PROFIT["crude_used_per_day"]
        income_sell = (
            sold_crude * crude_bo
            + PROFIT["very_crude_per_day"] * very_bo
        ) * (1.0 - PROFIT["sell_tax"])
        income_order = (
            sold_crude * crude_ib
            + PROFIT["very_crude_per_day"] * very_ib
        ) * (1.0 - PROFIT["sell_tax"])
        net_bo = income_sell - cost_bo
        net_ib = income_sell - cost_ib
        plines = [
            "Income - %s instasell | %s sell order"
            % (fmt(income_sell), fmt(income_order)),
            "Fuel - %s buy order | %s instabuy" % (fmt(cost_bo), fmt(cost_ib)),
            "Net - %s/day buy order | %s/day instabuy"
            % (fmt(net_bo), fmt(net_ib)),
        ] + extras
        write_file("profit.txt", "\n".join(plines))
        crude_cost_sell = int(PROFIT["crude_used_per_day"] * crude_bo * (1.0 - PROFIT["sell_tax"]))
        crude_cost_order = int(PROFIT["crude_used_per_day"] * crude_ib * (1.0 - PROFIT["sell_tax"]))
        write_file("stats-day.json", json.dumps({
            "date": day,
            "net_bo": int(net_bo),
            "net_ib": int(net_ib),
            "income_sell": int(income_sell),
            "income_order": int(income_order),
            "spent_bo": int(cost_bo),
            "spent_ib": int(cost_ib),
            "crude_cost_sell": crude_cost_sell,
            "crude_cost_order": crude_cost_order,
            "spike_fired": bool(spike),
            "spike_items": spike or None,
            "stockup_fired": bool(stock),
            "stockup_pct": stock_pct,
            "craftbuy_fired": bool(tip),
            "craftbuy_savings": int(round((coal_ib - gab_bo) * 25)) if tip and gab_bo > 0 and coal_ib > 0 else None,
        }))
        print("profit: income_sell=%s income_order=%s cost_bo=%s cost_ib=%s net_bo=%s net_ib=%s extras=%s" % (
            fmt(income_sell), fmt(income_order), fmt(cost_bo), fmt(cost_ib),
            fmt(net_bo), fmt(net_ib), " | ".join(extras) or "-"))
    elif extras:
        write_file("profit.txt", "\n".join(extras))
        print("profit: unavailable, extras=%s" % " | ".join(extras))

    repo_write("prices.json", json.dumps({
        "date": day,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bazaar_age_s": int(bazaar_age),
        "prices_source": prices_source,
        "history_source": "sky.coflnet.com",
        "crude": "free",
        "coal": fmt(coal_ib) or "-",
        "distillate": fmt(dist_ib) or "-",
        "fuel_block": fmt(fb_ib) or "-",
        "fuel_bill": fmt(cost_ib) or "-",
        "income_sell": (fmt(income_sell) + "/day") if income_available and income_sell else "-",
        "income_order": (fmt(income_order) + "/day") if income_available and income_order else "-",
        "net_buy_order": (fmt(net_bo) + "/day") if income_available and net_bo else "-",
        "net_instabuy": (fmt(net_ib) + "/day") if income_available and net_ib else "-",
        "items": items,
        "qty": qty_map,
        "subtotals": subtotals,
        "bill": {"buy_order": int(cost_bo), "instabuy": int(cost_ib)},
        "income": {"instasell": int(income_sell), "sell_order": int(income_order)} if income_available else {},
        "net": {"buy_order": int(net_bo), "instabuy": int(net_ib)} if income_available else {},
        "alerts": alerts,
        "cookie": {
            "buy_order": items["BOOSTER_COOKIE"]["buy_order"],
            "instabuy": items["BOOSTER_COOKIE"]["instabuy"],
            "week_median_buy": (items["BOOSTER_COOKIE"]["week"].get("buy") or {}).get("median"),
        },
    }, indent=1))

    repo_append("prices.jsonl", json.dumps({
        "date": day,
        "ts": int(time.time()),
        "dow": int(time.strftime("%w", time.gmtime(time.time() + 3 * 3600))),
        "bazaar_age_s": int(bazaar_age),
        "prices_source": prices_source,
        "items": items,
        "qty": qty_map,
        "subtotals": subtotals,
        "bill_buy_order": int(cost_bo),
        "bill_instabuy": int(cost_ib),
        "income_instasell": int(income_sell) if income_available else None,
        "income_sell_order": int(income_order) if income_available else None,
        "crude_opportunity_cost": {
            "instasell": crude_cost_sell,
            "sell_order": crude_cost_order,
        } if income_available else {},
        "net_buy_order": int(net_bo) if income_available else None,
        "net_instabuy": int(net_ib) if income_available else None,
        "alerts": alerts,
        "cookie": {
            "buy_order": items["BOOSTER_COOKIE"]["buy_order"],
            "instabuy": items["BOOSTER_COOKIE"]["instabuy"],
            "week_median_buy": (items["BOOSTER_COOKIE"]["week"].get("buy") or {}).get("median"),
        },
        "fact": {
            "text": FACT_INFO.get("text") or "",
            "image_title": FACT_INFO.get("image_title") or "",
            "image_url": FACT_INFO.get("image_url") or "",
        },
    }) + "\n")


def main():
    fetch_fact()
    fetch_prices()


if __name__ == "__main__":
    main()
