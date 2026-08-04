# inferno reminder

a discord webhook reminder that pings you every day to refuel your inferno minions on hypixel skyblock. runs on github actions for free, repo is public, and every secret lives in repo settings, not in the code.

## what you get

each day the message has:

- the refuel shopping list with live bazaar prices. crude gabagool is free, your minions make it. sulphuric coal shows instabuy and instasell, gabagool distillate and inferno fuel block show buy order and instabuy, plus a total at instabuy.
- the crafting steps for fuel gabagool.
- a random animal fact with a live wikipedia picture of that animal.
- a daily profit estimate: income at bazaar instasell and sell order, fuel at buy order and instabuy, net per day for both.

it's two embeds: one with the shopping list, crafting steps and profit numbers, and one with the animal fact and its picture.

the message deletes itself after 3 hours, and every new message wipes the old ones first, so the channel never piles up with reminders.

## setup

1. make a discord webhook in your server (server settings > integrations > webhooks).
2. add the url as a repo secret called `discord_webhook_url`.
3. add your discord user id as a repo secret called `discord_user_id` so the message pings you.
4. go to the actions tab, pick daily discord reminder, hit run workflow.

note: the secret names are uppercase in the workflow, `DISCORD_WEBHOOK_URL` and `DISCORD_USER_ID`. actions is picky about that.

## the profit numbers

it's a fixed model with live prices, based on herodirk's minion calculator for this exact setup (25x inferno t3, fuel gabagool grade, gabagool distillate, super compactor 3000, beacon v, postcard, offline). the harvest amounts are constants from the calculator, the prices refresh every run from the hypixel bazaar api.

it's an estimate, not a promise. prices move, and the income reads a bit lower than the calculator because it uses live instasell prices instead of the calculator's volume-averaged ones.

## files

- `.github/scripts/fetch-data.py` - facts, prices, shopping list, profit
- `.github/scripts/purge-messages.py` - deletes old messages before each send
- `.github/workflows/daily-reminder.yml` - the daily run
- `.github/workflows/delete-reminder.yml` - the 3 hour self-delete
- `.github/reminder-state.json` - message ids and a timestamp, safe for a public repo

## why it's free

public repos get unlimited actions minutes, and neither the hypixel bazaar api nor the wikipedia api needs a key. there's also a keepalive workflow so github doesn't pause the scheduled runs after a quiet spell.
