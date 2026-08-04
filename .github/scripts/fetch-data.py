#!/usr/bin/env python3
"""Fetch the data for the Inferno reminder embed.

- Animal: pick a random entry from a hand-curated pool of verified
  interesting facts (all sourced from Wikipedia content). The animal's
  picture is fetched live from the keyless Wikipedia summary API, so the
  image changes with the animal while the fact is guaranteed good.
- Prices: Hypixel Bazaar instant prices (no API key). Sulphuric Coal is
  shown at instabuy. Gabagool Distillate and Inferno Fuel Block show both
  the buy-order price and the instabuy price. Crude Gabagool is unpriced.
  The total uses instabuy prices.

Writes animal-name.txt, animal-fact.txt, animal-image.txt and
shopping-list.txt into $RUNNER_TEMP. Never raises; every source has a
graceful failure path so the reminder always sends.
"""

import json
import os
import random
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "inferno-reminder/1.0 (GitHub Actions daily reminder)"}
TMP = os.environ.get("RUNNER_TEMP", "/tmp")

# Profit model constants, from Herodirk's Minion Calculator for this exact
# setup (25x Inferno T3, Fuel Gabagool grade, Gabagool Distillate, SC3000,
# Minion Expander, Beacon V + Scorched Power Crystal, Postcard, Force
# Rising Celsius, offline). Re-run the calculator to refresh these if the
# layout ever changes.
PROFIT = {
    "crude_per_day": 4030.66,      # raw crude after per-minion SC3000 compacting
    "very_crude_per_day": 175,     # SC3000-compacted stacks (192 crude each)
    "crude_used_per_day": 675,     # 25 Fuel Gabagool cores x 27 crude - deducted
    "coal_per_day": 25,            # one Inferno Minion Fuel per minion, 24h each
    "distillate_per_day": 150,     # 6 Gabagool Distillate per fuel
    "fuel_block_per_day": 50,      # 2 Inferno Fuel Blocks per fuel
    "sell_tax": 0.01125,           # bazaar tax, flipper 1 (1.25% - 0.125%), mayor none
}

# (animal title for the Wikipedia picture, verified interesting fact).
# All facts are one short sentence, no emojis, sourced from Wikipedia.
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
    """GET JSON with a retry; raises the last error when all tries fail."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(0.6 * (attempt + 1))
    raise last


def write_file(name, text):
    with open(os.path.join(TMP, name), "w", encoding="utf-8") as f:
        f.write(text)


def fetch_animal():
    entries = list(FACTS)
    random.shuffle(entries)
    facts_by_name = dict(entries)
    # The fact itself never depends on the network; only the picture does.
    # Find the first entry with a working picture and write it all at once.
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
    # No picture available - still send the fact (embed shows text only).
    title, fact = entries[0]
    write_file("animal-name.txt", title)
    write_file("animal-fact.txt", fact)
    print("animal: %s (no image available)" % title)


def fetch_prices():
    products = {}
    try:
        bz = get("https://api.hypixel.net/skyblock/bazaar", timeout=30)
        products = (bz or {}).get("products") or {}
    except Exception:
        pass

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

    def pair(bo, ib):
        if bo <= 0 or ib <= 0:
            return ""
        if round(bo) == round(ib):
            return fmt(ib)
        return "%s buy order / %s instabuy" % (fmt(bo), fmt(ib))

    coal_bo, coal_ib = prices("SULPHURIC_COAL")
    dist_bo, dist_ib = prices("CRUDE_GABAGOOL_DISTILLATE")
    fb_bo, fb_ib = prices("INFERNO_FUEL_BLOCK")

    lines = ["675x Crude Gabagool"]
    total = 0
    all_priced = True

    if coal_ib > 0:
        total += 25 * coal_ib
        lines.append("25x Sulphuric Coal - %s" % fmt(25 * coal_ib))
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
        lines.append("Total - %s" % fmt(total))

    write_file("shopping-list.txt", "\n".join(lines))
    print("prices: coal=%s dist=%s/%s fb=%s/%s total=%s" % (
        fmt(coal_ib), fmt(dist_bo), fmt(dist_ib), fmt(fb_bo), fmt(fb_ib),
        fmt(total)))

    # Daily profit. Income = the minions' crude + very crude gabagool sold at
    # bazaar instasell (prices()[0] is the min side = instasell level), minus
    # the 675 crude/day consumed by the fuel cores (it becomes fuel, it is not
    # sold), taxed. Cost = the daily fuel bill (coal + distillate + fuel
    # blocks) at buy-order and instabuy prices. Note: income reads ~20% below
    # Herodirk's calculator because we use quick_status instasell rather than
    # its volume-averaged sell prices.
    crude_sell, _ = prices("CRUDE_GABAGOOL")
    very_sell, _ = prices("VERY_CRUDE_GABAGOOL")
    if crude_sell > 0 and very_sell > 0 and all_priced:
        sold_crude = PROFIT["crude_per_day"] - PROFIT["crude_used_per_day"]
        income = (
            sold_crude * crude_sell
            + PROFIT["very_crude_per_day"] * very_sell
        ) * (1.0 - PROFIT["sell_tax"])
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
        net = income - cost_bo
        plines = [
            "Income - %s (bazaar instasell)" % fmt(income),
            "Fuel - %s buy order / %s instabuy" % (fmt(cost_bo), fmt(cost_ib)),
            "Net - %s/day (buy order refuel)" % fmt(net),
        ]
        write_file("profit.txt", "\n".join(plines))
        print("profit: income=%s cost_bo=%s cost_ib=%s net=%s" % (
            fmt(income), fmt(cost_bo), fmt(cost_ib), fmt(net)))


def main():
    fetch_animal()
    fetch_prices()


if __name__ == "__main__":
    main()
