# inferno reminder

a discord webhook that pings you daily to refuel your inferno minions on hypixel skyblock. free, runs on github actions.

![net chart](chart.svg)

![reminder status](https://github.com/1901204818467/inferno/actions/workflows/daily-reminder.yml/badge.svg)
![fuel bill](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2F1901204818467%2Finferno%2Fmain%2Fprices.json&query=fuel_bill&label=fuel%20bill&color=orange)
![net](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2F1901204818467%2Finferno%2Fmain%2Fprices.json&query=net_buy_order&label=net%2Fday&color=green)
![refuels](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2F1901204818467%2Finferno%2Fmain%2Fstats.json&query=refuels&label=refuels&color=blue)
![total net](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2F1901204818467%2Finferno%2Fmain%2Fstats.json&query=total_net_disp&label=total%20net&color=purple)

each day: shopping list, crafting steps, an animal fact with picture, live profit. old messages delete themselves, newest after 3 hours.

live prices from the hypixel bazaar api, history from sky.coflnet.com. secrets: `DISCORD_WEBHOOK_URL`, `DISCORD_USER_ID`.
