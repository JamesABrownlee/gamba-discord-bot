# Gamba-Style Discord.py Gambling Bot

Personal Discord gambling bot with:

- Persistent user accounts (`user_id`, `display_name`, `balance`)
- Shared balance across all games
- Separate game cogs:
  - Roulette
  - Slots
  - Blackjack
  - Poker
  - Minesweeper
  - Word Links
- DM + server support
- In-server responses are ephemeral
- Stake affordability checks before every settlement

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` from `.env.example` and set your bot token.

## Run

```bash
python bot.py
```

## Run with Docker

Build and run:

```bash
docker compose up --build -d
```

Stop:

```bash
docker compose down
```

## Commands

- `/balance`
- `/roulette stake:<decimal> pick:<red|black|green>`
- `/slots stake:<decimal>`
- `/blackjack`
- `/poker stake:<decimal>`
- `/minesweeper stake:<decimal> tile:<1-6>`
- `/wordlinks stake:<decimal> guess:<1-20>`

## Notes

- User records are auto-created on first interaction (`/command`, DM usage, or bot mention).
- Database is SQLite (`DATABASE_PATH`, default `./data/gamba.db`).
- Balances are stored as cent-units (`100000` = `1000.00` credits).
- Slash command propagation may take time globally on Discord.
- GitHub Actions workflow at `.github/workflows/docker-image.yml` builds image on push/PR and publishes to `ghcr.io/<owner>/<repo>` on non-PR events.
