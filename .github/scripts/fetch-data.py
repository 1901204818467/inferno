#!/usr/bin/env python3
"""Fetch the data for the Inferno reminder embed.

- Animal: random Wikipedia article from animal categories, whole-paragraph
  intro as the fact, lead image, and article title.
- Prices: Hypixel Bazaar instant-buy (buyPrice) for Crude Gabagool and
  Sulphuric Coal; lowest Auction House BIN preferred for Gabagool
  Distillate and Inferno Fuel Block, with bazaar buyPrice as fallback.

Writes animal-name.txt, animal-fact.txt, animal-image.txt and
shopping-list.txt into $RUNNER_TEMP. Never raises; every source has a
graceful failure path so the reminder always sends.
"""

import json
import os
import random
import re
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "inferno-reminder/1.0 (GitHub Actions daily reminder)"}
TMP = os.environ.get("RUNNER_TEMP", "/tmp")


def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_file(name, text):
    with open(os.path.join(TMP, name), "w", encoding="utf-8") as f:
        f.write(text)


def fetch_animal():
    categories = [
        "Birds of prey", "Snakes", "Frogs", "Sharks", "Butterflies",
        "Owls", "Spiders", "Birds", "Amphibians", "Insects", "Carnivora",
    ]
    start = time.time()
    for cat in categories:
        if time.time() - start > 90:
            break
        try:
            enc = urllib.parse.quote(cat)
            data = get(
                "https://en.wikipedia.org/w/api.php?action=query&list=categorymembers"
                "&cmtitle=Category:%s&cmtype=page&cmnamespace=0&cmlimit=500&format=json" % enc
            )
            titles = [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
            random.shuffle(titles)
        except Exception:
            continue
        for title in titles[:10]:
            if time.time() - start > 90:
                break
            try:
                s = get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title))
                extract = (s.get("extract") or "").strip()
                thumb = (s.get("thumbnail") or {}).get("source") or ""
                if not extract or not thumb:
                    continue
                fact = re.sub(r"\s+", " ", extract).strip()[:1000]
                image = thumb.split("?")[0]
                name = s.get("title") or "Animal Fact"
                write_file("animal-name.txt", name)
                write_file("animal-fact.txt", fact)
                write_file("animal-image.txt", image)
                print("animal:", name)
                return
            except Exception:
                continue


def clean_name(name):
    """Strip Minecraft color codes and trailing symbol marks."""
    cleaned = re.sub("\u00a7.", "", name or "")
    cleaned = re.sub(r"[^A-Za-z0-9 '()-]+$", "", cleaned).strip()
    return cleaned


def fetch_prices():
    bazaar = {}
    try:
        bz = get("https://api.hypixel.net/skyblock/bazaar", timeout=30)
        products = bz.get("products", {})
        for tag in ("CRUDE_GABAGOOL", "SULPHURIC_COAL",
                    "CRUDE_GABAGOOL_DISTILLATE", "INFERNO_FUEL_BLOCK"):
            q = (products.get(tag) or {}).get("quick_status") or {}
            if q.get("buyPrice"):
                bazaar[tag] = q["buyPrice"]
    except Exception:
        pass

    # Lowest BIN on the Auction House for distillate + fuel block, with the
    # bazaar buy price as fallback. Exact name match so Heavy/Hypergolic
    # Distillates never count.
    ah_tags = {
        "CRUDE_GABAGOOL_DISTILLATE": "Gabagool Distillate",
        "INFERNO_FUEL_BLOCK": "Inferno Fuel Block",
    }
    found = {}
    try:
        start = time.time()
        page = 0
        while page < 5 and time.time() - start < 60:
            data = get("https://api.hypixel.net/skyblock/auctions?page=%d" % page, timeout=30)
            for a in data.get("auctions", []):
                if not a.get("bin"):
                    continue
                name = clean_name(a.get("item_name"))
                for tag, exact in ah_tags.items():
                    if name == exact:
                        sb = a.get("starting_bid") or 0
                        if sb > 0 and (tag not in found or sb < found[tag]):
                            found[tag] = sb
            page += 1
            if page >= (data.get("totalPages") or 0) or len(found) == 2:
                break
    except Exception:
        pass

    def unit_price(tag):
        if found.get(tag):
            return found[tag]
        return bazaar.get(tag, 0)

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

    items = [
        ("675x Crude Gabagool", 675, unit_price("CRUDE_GABAGOOL")),
        ("25x Sulphuric Coal", 25, unit_price("SULPHURIC_COAL")),
        ("150x Gabagool Distillate", 150, unit_price("CRUDE_GABAGOOL_DISTILLATE")),
        ("50x Inferno Fuel Block", 50, unit_price("INFERNO_FUEL_BLOCK")),
    ]
    lines = []
    total = 0
    for label, qty, unit in items:
        if unit > 0:
            cost = qty * unit
            total += cost
            lines.append("%s - %s" % (label, fmt(cost)))
        else:
            lines.append(label)
    out = "\n".join(lines)
    if total > 0:
        out += "\nTotal - %s" % fmt(total)
    write_file("shopping-list.txt", out)
    print("prices: crude=%s coal=%s distillate=%s fuelblock=%s" % (
        fmt(unit_price("CRUDE_GABAGOOL")),
        fmt(unit_price("SULPHURIC_COAL")),
        fmt(unit_price("CRUDE_GABAGOOL_DISTILLATE")),
        fmt(unit_price("INFERNO_FUEL_BLOCK")),
    ))


def main():
    fetch_animal()
    fetch_prices()


if __name__ == "__main__":
    main()
