# inferno

we love inferno minions

or do we?

## What this is

A Discord webhook reminder that pings you daily to refuel your Inferno Minions, running on GitHub Actions for free.

## How it works

- Every day at 21:30 UTC, a workflow pings your user mention and posts two embeds:
  - Refuel embed: Shopping List with live prices (Bazaar instant-buy for Crude Gabagool and Sulphuric Coal; lowest Auction House BIN preferred for Gabagool Distillate and Inferno Fuel Block, falling back to Bazaar instant-buy; plus a total) and the crafting steps (/recipe gabagool, 25x fuel gabagool supercraft, 25x rare inferno minion fuel supercraft).
  - Animal Fact embed: a random animal fact and picture from Wikipedia, titled with the animal's name.
- A second workflow checks once an hour and deletes the reminder message once it is 3 hours old.
- Each send also deletes the previous day's message, so the channel never fills up.

## Setup

1. Create a Discord webhook in your server (Server Settings > Integrations > Webhooks).
2. Add the webhook URL as a repository secret `DISCORD_WEBHOOK_URL`.
3. Add your Discord user ID as a repository secret `DISCORD_USER_ID` (Settings > Secrets and variables > Actions).
4. Trigger a test run: Actions > Daily Discord Reminder > Run workflow.

Price data comes from the public Hypixel Bazaar and Auction House APIs (no API key needed). The data fetching lives in `.github/scripts/fetch-data.py`. The state file `.github/reminder-state.json` only stores a Discord message ID, which is not sensitive and is safe to keep in a public repo.

## Notes

- Runs are free: public repositories get unlimited GitHub Actions minutes.
- The monthly Keepalive workflow prevents GitHub from disabling scheduled workflows after 60 days of inactivity.
- No emojis, no bells, no whistles. Just refuel.
