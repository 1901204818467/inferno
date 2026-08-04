# inferno

we love inferno minions

or do we?

## What this is

A Discord webhook reminder that pings you daily to refuel your Inferno Minions, running on GitHub Actions for free.

## How it works

- Every day at 21:30 UTC, a workflow sends a rich embed to your Discord webhook:
  - A ping with your user mention: "Refuel Inferno Minions"
  - Shopping list: 675x Crude Gabagool, 25x Sulphuric Coal, 150x Gabagool Distillate, 50x Inferno Fuel Block
  - Crafting steps: /recipe gabagool, 25x fuel gabagool supercraft, 25x rare inferno minion fuel supercraft
  - A random animal fact and picture pulled from Wikipedia
- A second workflow checks once an hour and deletes the reminder message once it is 3 hours old.
- Each send also deletes the previous day's message, so the channel never fills up.

## Setup

1. Create a Discord webhook in your server (Server Settings > Integrations > Webhooks).
2. Add the webhook URL as a repository secret `DISCORD_WEBHOOK_URL`.
3. Add your Discord user ID as a repository secret `DISCORD_USER_ID` (Settings > Secrets and variables > Actions).
4. Trigger a test run: Actions > Daily Discord Reminder > Run workflow.

The state file `.github/reminder-state.json` only stores a Discord message ID, which is not sensitive and is safe to keep in a public repo.

## Notes

- Runs are free: public repositories get unlimited GitHub Actions minutes.
- The monthly Keepalive workflow prevents GitHub from disabling scheduled workflows after 60 days of inactivity.
- No emojis, no bells, no whistles. Just refuel.
