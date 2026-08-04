"""Fetch the data for the Inferno reminder embed.

- Animal: pick a random entry from a hand-curated pool of verified
  interesting facts (all sourced from Wikipedia content). The animal's
  picture is fetched live from the keyless Wikipedia summary API, so the
  image changes with the animal while the fact is guaranteed good.
- Prices: Hypixel Bazaar instant prices (no API key). Sulphuric Coal
  shows instabuy and instasell. Gabagool Distillate and Inferno Fuel Block
  show both the buy-order price and the instabuy price. Crude Gabagool is
  free (the minions produce it). The total uses instabuy prices.
- Price spike alert: robust heuristic on Coflnet's 7-day bazaar history
  (sky.coflnet.com/api/bazaar/{tag}/history/week). Baseline is the weekly
  median, normal noise is 3x the median absolute deviation, and an item
  must be both >=10% from the median and outside that noise band to fire
  (upward moves only - a drop is an opportunity, not a warning). The
  order book is checked for thinness to flag likely price painting.
- Stock-up signal: the same median + MAD rule applied to the daily fuel
  bill; fires when the bill is clearly below its weekly median (cheap day
  to stock up).
- Craft-vs-buy tip: watches the Fuel Gabagool bazaar price (the buyable
  intermediate - the finished fuel itself has no market) against its
  craft cost; fires only when buying is clearly cheaper.
- Snapshots: appends one raw line to prices.jsonl and rewrites
  prices.json (badge-friendly strings) in the repo working tree.
- Freshness: writes the fetch timestamp so the embed can show how many
  seconds ago the prices were pulled.

Writes animal-name.txt, animal-fact.txt, animal-image.txt,
shopping-list.txt and profit.txt into $RUNNER_TEMP. Never raises; every
source has a graceful failure path so the reminder always sends.
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
COFL = "https://sky.coflnet.com/api/bazaar"
MIN_PCT = 10.0
MAD_MULT = 3.0
THIN_UNITS = 25
GABAGOOL = "FUEL_GABAGOOL"
BUY_CHEAP_PCT = 5.0

PROFIT = {
    "crude_per_day": 4030.66,
    "very_crude_per_day": 175,
    "crude_used_per_day": 675,
    "coal_per_day": 25,
    "distillate_per_day": 150,
    "fuel_block_per_day": 50,
    "sell_tax": 0.01125,
}

FACTS = [
    ("Octopus", "Octopuses have three hearts, blue blood, and can change colour and shape to blend into almost any surface."),
    ("Axolotl", "Axolotls can regenerate lost limbs, organs, and even parts of their brain - and never grow out of their larval stage."),
    ("Platypus", "The platypus is one of the few mammals that lays eggs, and males have venomous spurs on their hind legs."),
    ("Tardigrade", "Tardigrades can survive boiling water, deep space, and decades without food or water."),
    ("Pistol shrimp", "The pistol shrimp snaps its claw so fast the collapsing bubble fires a shockwave almost as hot as the surface of the sun."),
    ("Mantis shrimp", "Mantis shrimp see four times more colours than humans and punch with the force of a bullet."),
    ("Archerfish", "Archerfish knock insects off branches by shooting jets of water from their mouths, up to 2 metres away."),
    ("Naked mole-rat", "Naked mole-rats barely feel pain, rarely get cancer, and can live past 30 - far longer than any other rodent."),
    ("Sloth", "Sloths can hold their breath for up to 40 minutes and only climb down from the trees about once a week."),
    ("Wombat", "Wombats are the only animals in the world that produce cube-shaped droppings."),
    ("Horned lizard", "Horned lizards scare off predators by squirting a stream of blood from their eyes."),
    ("Wood frog", "Wood frogs freeze solid in winter - hearts stop, breathing stops - and thaw out alive in spring."),
    ("Honey badger", "Honey badgers fear nothing: they take on lions and snakes and shrug off most snake venom."),
    ("Cheetah", "A cheetah can reach 100 km/h in about three seconds - faster off the line than most sports cars."),
    ("Peregrine falcon", "Peregrine falcons are the fastest animals on Earth, hitting over 300 km/h in a dive."),
    ("Hummingbird", "Hummingbirds are the only birds that can fly backwards, beating their wings up to 80 times a second."),
    ("Emperor penguin", "Emperor penguins are the only penguins that breed through the Antarctic winter, in temperatures down to -60 C."),
    ("Giraffe", "Giraffes have the same number of neck bones as humans, and a heart big enough to pump blood 2 metres up to the brain."),
    ("Kangaroo", "Female kangaroos can pause a pregnancy until the joey already in the pouch is ready to leave."),
    ("Koala", "Koala joeys eat their mother's droppings to get the bacteria they need to digest eucalyptus leaves."),
    ("Fennec fox", "Fennec foxes use their giant ears as radiators to keep cool in the desert."),
    ("Arctic fox", "Arctic foxes change colour with the seasons - white in winter, brown in summer."),
    ("Polar bear", "A polar bear's skin is black and its fur is actually transparent - it only looks white."),
    ("Elephant", "Elephants pick up vibrations through their feet and can 'hear' other elephants from kilometres away."),
    ("Hippopotamus", "Hippos can't swim or float - they walk along the bottom of rivers and can hold their breath for five minutes."),
    ("Rhinoceros", "Rhino horns are made of keratin, the same protein as human hair and fingernails."),
    ("Lion", "A lion's roar can be heard up to 8 km away, and lionesses do most of the hunting."),
    ("Sperm whale", "Sperm whales dive over 2 km deep and can hold their breath for over an hour."),
    ("Narwhal", "The narwhal's 'horn' is actually a tooth that can grow up to 3 metres long."),
    ("Beluga whale", "Belugas are so vocal they're called the canaries of the sea - they can even imitate human speech."),
    ("Great white shark", "Great white sharks can smell a single drop of blood in 100 litres of water."),
    ("Goblin shark", "Goblin sharks shoot their jaws out of their faces to grab prey."),
    ("Hagfish", "Hagfish flood predators with litres of instant slime that clogs their gills."),
    ("Sea cucumber", "Sea cucumbers eject their own internal organs at predators, then grow them back."),
    ("Sea star", "Sea stars can regrow lost arms, and some can grow a whole new body from a single arm."),
    ("Pufferfish", "Pufferfish puff into spiky balls when threatened, and most carry a poison deadlier than cyanide."),
    ("Cuttlefish", "Cuttlefish change colour and texture in a blink, and have three hearts and blue-green blood."),
    ("Vampire squid", "Vampire squids live in the darkest, most oxygen-starved parts of the ocean."),
    ("Giant squid", "Giant squids have the largest eyes of any animal - about the size of dinner plates."),
    ("Firefly", "Fireflies make light with a chemical reaction, and some species flash in perfect synchrony."),
    ("Bombardier beetle", "Bombardier beetles blast predators with a boiling-hot chemical spray from their abdomens."),
    ("Dung beetle", "Dung beetles roll dung balls far heavier than themselves, and some navigate by the Milky Way."),
    ("Leafcutter ant", "Leafcutter ants don't eat the leaves they cut - they use them to grow a fungus garden, which they eat."),
    ("Praying mantis", "Female praying mantises sometimes eat their mates right after mating."),
    ("Black widow spider", "Black widow venom is up to 15 times stronger than rattlesnake venom."),
    ("Scorpion", "Scorpions glow blue-green under ultraviolet light."),
    ("Komodo dragon", "Komodo dragons have a venomous bite and can take down prey as large as water buffalo."),
    ("Chameleon", "Chameleons move each eye independently and can catch prey with their tongue in a fraction of a second."),
    ("Tuatara", "Tuatara have a 'third eye' on top of their heads that senses light."),
    ("Kiwi", "Kiwi lay an egg up to a quarter of their own body weight - the biggest egg-to-body ratio of any bird."),
    ("Ostrich", "Ostriches can't fly but sprint at over 70 km/h, and their eyes are bigger than their brains."),
    ("Wandering albatross", "Wandering albatrosses can fly thousands of kilometres without flapping their wings once."),
    ("Snowy owl", "Snowy owls can turn their heads almost 270 degrees and hunt in total daylight."),
    ("Capybara", "Capybaras are the biggest rodents on Earth, weighing up to 66 kg, and are excellent swimmers."),
    ("Sea otter", "Sea otters hold hands while sleeping so they don't drift apart, and use rocks as tools."),
    ("Honey bee", "Honey bees tell hive-mates exactly where flowers are with a 'waggle dance'."),
    ("Cicada", "Some cicadas live 17 years underground as nymphs, then surface en masse for a few weeks."),
    ("Ocean sunfish", "Ocean sunfish can lay up to 300 million eggs at once - more than any other vertebrate."),
    ("Horseshoe crab", "Horseshoe crabs have blue blood that medicine uses to test vaccines for contamination."),
    ("Portuguese man o' war", "The Portuguese man o' war looks like a jellyfish but is actually four organisms working as one colony."),
    ("Pangolin", "Pangolins are the only mammals covered in scales, and roll into an armoured ball when threatened."),
    ("Aye-aye", "Aye-ayes tap on wood with a long skinny finger to find grubs, then hook them out - nature's woodpecker."),
]


def get(url, timeout=20, tries=2):
    """GET JSON with a retry; raises the last error when all tries fail.

    Rate-limited (429) responses honour Retry-After, capped at 10s, since
    Coflnet asks for ~1 request/sec and can throttle bursts.
    """
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            wait = 0.6 * (attempt + 1)
            if exc.code == 429 and exc.headers:
                ra = exc.headers.get("Retry-After")
                if ra:
                    try:
                        wait = min(float(ra), 10.0)
                    except ValueError:
                        pass
            time.sleep(wait)
        except Exception as exc:
            last = exc
            time.sleep(0.6 * (attempt + 1))
    raise last


def write_file(name, text):
    with open(os.path.join(TMP, name), "w", encoding="utf-8") as f:
        f.write(text)


def repo_write(name, text):
    """Write into the repo working tree (cwd is the repo root in Actions)."""
    with open(name, "w", encoding="utf-8") as f:
        f.write(text)


def repo_append(name, text):
    """Append into the repo working tree (cwd is the repo root in Actions)."""
    with open(name, "a", encoding="utf-8") as f:
        f.write(text)


def fetch_animal():
    entries = list(FACTS)
    random.shuffle(entries)
    facts_by_name = dict(entries)
    for animal, _ in entries[:10]:
        try:
            s = get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(animal)
            )
        except Exception:
            continue
        thumb = (s.get("thumbnail") or {}).get("source") or ""
        if not thumb:
            continue
        write_file("animal-name.txt", animal)
        write_file("animal-fact.txt", facts_by_name[animal])
        write_file("animal-image.txt", thumb)
        print("animal:", animal)
        return
    title, fact = entries[0]
    write_file("animal-name.txt", title)
    write_file("animal-fact.txt", fact)
    print("animal: %s (no image available)" % title)


def cofl_week_buy(tag):
    """List of instabuy prices (2-hourly, last 7 days) from Coflnet.

    The 'buy' field matches Hypixel's buyPrice (verified empirically).
    Returns None if the call fails or the history is empty.
    """
    try:
        h = get(COFL + "/" + tag + "/history/week", timeout=20)
    except Exception:
        return None
    if not isinstance(h, list):
        return None
    vals = [p.get("buy") for p in h if isinstance(p, dict) and p.get("buy")]
    return vals or None


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
        return s.rstrip("0").rstrip(".") + "K"
    return str(int(n))


def book_thin(tag):
    """True if the top of the sell order book is suspiciously thin - a
    likely price paint. One extra call, only used when an alert fires."""
    try:
        s = get(COFL + "/" + tag + "/snapshot", timeout=20)
    except Exception:
        return False
    asks = s.get("sellOrders") or []
    if not asks:
        return False
    asks = sorted(asks, key=lambda a: a.get("pricePerUnit") or 0)
    top = sum(a.get("amount") or 0 for a in asks[:3])
    return top < THIN_UNITS


def price_spikes(items, weeks):
    """items: (short name, bazaar tag, today's instabuy). weeks: dict of
    tag -> 7-day instabuy series (fetched once by the caller). Returns an
    alert line for items clearly ABOVE their normal 7-day range, or ''.

    Drops are not alerts - the stock-up signal covers those. Heuristics
    (median + MAD, robust to a manipulated window):
    - baseline = median of the week's instabuy series
    - normal noise = MAD_MULT * MAD around the median
    - an item alerts only if today is BOTH above that noise band
      (statistically abnormal) AND >= MIN_PCT above the median (big
      enough to matter), so a normal 5% wiggle never fires but a clear
      spike does.
    - the order book is checked for thinness to flag likely manipulation.
    """
    parts = []
    for name, tag, today in items:
        if today <= 0:
            continue
        week = weeks.get(tag) or []
        if len(week) < 3:
            continue
        med = median(week)
        if med <= 0:
            continue
        mad = median([abs(x - med) for x in week])
        noise = MAD_MULT * max(mad, med * 0.001)
        pct = (today - med) / med * 100.0
        if (today - med) >= noise and pct >= MIN_PCT:
            label = "%s %+.0f%%" % (name, pct)
            if book_thin(tag):
                label += " (thin)"
            parts.append(label)
    if not parts:
        return ""
    return "Price alert - %s vs 7d avg" % " | ".join(parts)


def bill_dip(weeks, today_bill, qtys):
    """'Stock up' line when today's fuel bill is clearly below its weekly
    median, or ''. today_bill is the daily bill at instabuy; qtys maps
    each bazaar tag to its daily quantity. The weekly bill series is
    rebuilt from the per-item instabuy histories (same median + MAD rule
    as price_spikes, applied to the bill as a whole).
    """
    if today_bill <= 0:
        return ""
    series = [
        w for w in (
            weeks.get("SULPHURIC_COAL"),
            weeks.get("CRUDE_GABAGOOL_DISTILLATE"),
            weeks.get("INFERNO_FUEL_BLOCK"),
        ) if w
    ]
    if len(series) < 3:
        return ""
    n = min(len(s) for s in series)
    if n < 3:
        return ""
    bills = [
        sum(qtys[tag] * (weeks[tag][i] or 0) for tag in qtys)
        for i in range(n)
    ]
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
    """'Buy instead of craft' tip for the fuel, or ''.

    The finished Inferno Minion Fuel has no market (not on the bazaar,
    nothing on the AH), so this watches the buyable intermediate, Fuel
    Gabagool, against its craft cost. Crafting one costs 27 Crude Gabagool
    (free from the minions) + 1 Sulphuric Coal, so the marginal craft cost
    is just the coal. Fires only when buying at the buy-order price beats
    that by BUY_CHEAP_PCT and there is real supply.
    """
    if gab_bo <= 0 or coal_ib <= 0:
        return ""
    if gab_vol < 25 * 7:
        return ""
    craft = coal_ib
    if gab_bo <= craft * (1.0 - BUY_CHEAP_PCT / 100.0):
        saved = (craft - gab_bo) * 25
        return "Fuel tip - buy Fuel Gabagool, save %s/day" % fmt(saved)
    return ""


def fetch_prices():
    products = {}
    bazaar_age = -1.0
    try:
        bz = get("https://api.hypixel.net/skyblock/bazaar", timeout=30)
        products = (bz or {}).get("products") or {}
        last = (bz or {}).get("lastUpdated") or 0
        if last:
            ms = last if last > 10 ** 11 else last * 1000.0
            bazaar_age = max(0.0, (time.time() * 1000 - ms) / 1000.0)
            print("bazaar snapshot age: %.0fs (fetched live this run)" % bazaar_age)
    except Exception:
        pass
    write_file("prices-fetched-at.txt", str(int(time.time())))

    def prices(tag):
        """Return (buy order price, instabuy price) for a bazaar item.

        The quick_status fields are the two sides of the order book and can
        flip around each other on thin items, so min/max is the robust way
        to label them: a buy order is always at or below the instabuy.
        """
        q = (products.get(tag) or {}).get("quick_status") or {}
        b = q.get("buyPrice") or 0
        s = q.get("sellPrice") or 0
        if b <= 0 and s <= 0:
            return 0, 0
        if b <= 0:
            return s, s
        if s <= 0:
            return b, b
        return min(b, s), max(b, s)

    def vol(tag):
        """7-day moving buy volume for a bazaar item, or 0."""
        q = (products.get(tag) or {}).get("quick_status") or {}
        return q.get("buyMovingWeek") or q.get("buyVolume") or 0

    def sellvol(tag):
        """7-day moving sell volume for a bazaar item, or 0."""
        q = (products.get(tag) or {}).get("quick_status") or {}
        return q.get("sellMovingWeek") or q.get("sellVolume") or 0

    def pair(bo, ib):
        if bo <= 0 or ib <= 0:
            return ""
        if round(bo) == round(ib):
            return fmt(ib)
        return "%s buy order / %s instabuy" % (fmt(bo), fmt(ib))

    coal_bo, coal_ib = prices("SULPHURIC_COAL")
    dist_bo, dist_ib = prices("CRUDE_GABAGOOL_DISTILLATE")
    fb_bo, fb_ib = prices("INFERNO_FUEL_BLOCK")
    gab_bo, gab_ib = prices(GABAGOOL)
    gab_q = (products.get(GABAGOOL) or {}).get("quick_status") or {}
    gab_vol = gab_q.get("buyMovingWeek") or gab_q.get("buyVolume") or 0

    lines = ["675x Crude Gabagool - free"]
    total = 0
    all_priced = True

    cp = pair(coal_bo, coal_ib)
    if cp:
        total += 25 * coal_ib
        lines.append("25x Sulphuric Coal - %s" % cp)
    else:
        all_priced = False
        lines.append("25x Sulphuric Coal")

    dp = pair(dist_bo, dist_ib)
    if dp:
        total += 150 * dist_ib
        lines.append("150x Gabagool Distillate - %s" % dp)
    else:
        all_priced = False
        lines.append("150x Gabagool Distillate")

    fp = pair(fb_bo, fb_ib)
    if fp:
        total += 50 * fb_ib
        lines.append("50x Inferno Fuel Block - %s" % fp)
    else:
        all_priced = False
        lines.append("50x Inferno Fuel Block")

    if all_priced and total > 0:
        total_bo = int(
            25 * coal_bo + 150 * dist_bo + 50 * fb_bo
        )
        lines.append(
            "Total - %s buy order | %s instabuy"
            % (fmt(total_bo), fmt(total))
        )

    write_file("shopping-list.txt", "\n".join(lines))
    print("prices: coal=%s dist=%s/%s fb=%s/%s total=%s" % (
        fmt(coal_ib), fmt(dist_bo), fmt(dist_ib), fmt(fb_bo), fmt(fb_ib),
        fmt(total)))

    crude_sell, crude_order = prices("CRUDE_GABAGOOL")
    very_sell, very_order = prices("VERY_CRUDE_GABAGOOL")
    cost_bo = cost_ib = 0.0
    if all_priced:
        cost_bo = (
            PROFIT["coal_per_day"] * coal_bo
            + PROFIT["distillate_per_day"] * dist_bo
            + PROFIT["fuel_block_per_day"] * fb_bo
        )
        cost_ib = (
            PROFIT["coal_per_day"] * coal_ib
            + PROFIT["distillate_per_day"] * dist_ib
            + PROFIT["fuel_block_per_day"] * fb_ib
        )
    weeks = {}
    for i, tag in enumerate(("SULPHURIC_COAL", "CRUDE_GABAGOOL_DISTILLATE", "INFERNO_FUEL_BLOCK")):
        if i:
            time.sleep(0.8)
        weeks[tag] = cofl_week_buy(tag)
    spike = price_spikes([
        ("coal", "SULPHURIC_COAL", coal_ib),
        ("distillate", "CRUDE_GABAGOOL_DISTILLATE", dist_ib),
        ("fuel block", "INFERNO_FUEL_BLOCK", fb_ib),
    ], weeks)
    stock = bill_dip(weeks, cost_ib, {
        "SULPHURIC_COAL": PROFIT["coal_per_day"],
        "CRUDE_GABAGOOL_DISTILLATE": PROFIT["distillate_per_day"],
        "INFERNO_FUEL_BLOCK": PROFIT["fuel_block_per_day"],
    })
    tip = craft_buy_tip(gab_bo, coal_ib, gab_vol)
    extras = [e for e in (spike, stock, tip) if e]
    if crude_sell > 0 and very_sell > 0 and all_priced:
        sold_crude = PROFIT["crude_per_day"] - PROFIT["crude_used_per_day"]
        income_sell = (
            sold_crude * crude_sell
            + PROFIT["very_crude_per_day"] * very_sell
        ) * (1.0 - PROFIT["sell_tax"])
        income_order = (
            sold_crude * crude_order
            + PROFIT["very_crude_per_day"] * very_order
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
        day = time.strftime("%Y-%m-%d", time.gmtime())
        coal_sub = int(PROFIT["coal_per_day"] * coal_ib)
        dist_sub = int(PROFIT["distillate_per_day"] * dist_ib)
        fb_sub = int(PROFIT["fuel_block_per_day"] * fb_ib)
        stock_pct = None
        spike_pct_map = {}
        if spike:
            for m in re.finditer(r"(\w[\w\s]*?)\s+([+-]?\d+)%", spike):
                spike_pct_map[m.group(1).strip()] = int(m.group(2))
        if stock:
            m = re.search(r"(\d+)%", stock)
            if m:
                stock_pct = int(m.group(1))
        crude_cost_sell = int(PROFIT["crude_used_per_day"] * crude_sell * (1.0 - PROFIT["sell_tax"]))
        crude_cost_order = int(PROFIT["crude_used_per_day"] * crude_order * (1.0 - PROFIT["sell_tax"]))
        write_file("stats-day.json", json.dumps({
            "date": day,
            "net_bo": int(net_bo), "net_ib": int(net_ib),
            "income_sell": int(income_sell), "income_order": int(income_order),
            "spent_bo": int(cost_bo), "spent_ib": int(cost_ib),
            "crude_cost_sell": crude_cost_sell,
            "crude_cost_order": crude_cost_order,
            "spike_fired": bool(spike), "spike_items": spike or None,
            "stockup_fired": bool(stock), "stockup_pct": stock_pct,
            "craftbuy_fired": bool(tip),
            "craftbuy_savings": int(round((coal_ib - gab_bo) * 25)) if tip and gab_bo > 0 and coal_ib > 0 else None,
        }))
        repo_write("prices.json", json.dumps({
            "date": day,
            "crude": "free",
            "coal": fmt(coal_ib) or "-",
            "distillate": fmt(dist_ib) or "-",
            "fuel_block": fmt(fb_ib) or "-",
            "fuel_bill": fmt(cost_ib) or "-",
            "income_sell": (fmt(income_sell) + "/day") if income_sell else "-",
            "income_order": (fmt(income_order) + "/day") if income_order else "-",
            "net_buy_order": (fmt(net_bo) + "/day") if net_bo else "-",
            "net_instabuy": (fmt(net_ib) + "/day") if net_ib else "-",
        }, indent=1))
        repo_append("prices.jsonl", json.dumps({
            "date": day,
            "ts": int(time.time()),
            "dow": int(time.strftime("%w", time.gmtime())),
            "bazaar_age_s": int(bazaar_age),
            "coal_bo": int(coal_bo), "coal_ib": int(coal_ib),
            "dist_bo": int(dist_bo), "dist_ib": int(dist_ib),
            "fb_bo": int(fb_bo), "fb_ib": int(fb_ib),
            "gab_bo": int(gab_bo), "gab_ib": int(gab_ib),
            "crude_sell": int(crude_sell),
            "crude_order": int(crude_order),
            "very_crude_ib": int(very_sell),
            "very_crude_order": int(very_order),
            "coal_subtotal": coal_sub, "dist_subtotal": dist_sub,
            "fb_subtotal": fb_sub,
            "bill_bo": int(cost_bo), "bill_ib": int(cost_ib),
            "income_sell": int(income_sell), "income_order": int(income_order),
            "crude_cost_sell": crude_cost_sell, "crude_cost_order": crude_cost_order,
            "net_bo": int(net_bo), "net_ib": int(net_ib),
            "spike_items": spike or None,
            "stockup_fired": bool(stock), "stockup_pct": stock_pct,
            "craftbuy_fired": bool(tip),
            "craftbuy_savings": int(round((coal_ib - gab_bo) * 25)) if tip and gab_bo > 0 and coal_ib > 0 else None,
            "spike_coal_pct": spike_pct_map.get("coal"),
            "spike_dist_pct": spike_pct_map.get("distillate"),
            "spike_fb_pct": spike_pct_map.get("fuel block"),
            "coal_vol": vol("SULPHURIC_COAL"),
            "dist_vol": vol("CRUDE_GABAGOOL_DISTILLATE"),
            "fb_vol": vol("INFERNO_FUEL_BLOCK"),
            "crude_vol": vol("CRUDE_GABAGOOL"),
            "gab_vol": int(gab_vol),
            "coal_sellvol": sellvol("SULPHURIC_COAL"),
            "dist_sellvol": sellvol("CRUDE_GABAGOOL_DISTILLATE"),
            "fb_sellvol": sellvol("INFERNO_FUEL_BLOCK"),
            "crude_sellvol": sellvol("CRUDE_GABAGOOL"),
            "gab_sellvol": sellvol(GABAGOOL),
        }) + "\n")
        print("profit: income_sell=%s income_order=%s cost_bo=%s cost_ib=%s net_bo=%s net_ib=%s extras=%s" % (
            fmt(income_sell), fmt(income_order), fmt(cost_bo), fmt(cost_ib),
            fmt(net_bo), fmt(net_ib), " | ".join(extras) or "-"))
    elif extras:
        write_file("profit.txt", "\n".join(extras))
        print("profit: unavailable, extras=%s" % " | ".join(extras))


def main():
    fetch_animal()
    fetch_prices()


if __name__ == "__main__":
    main()

