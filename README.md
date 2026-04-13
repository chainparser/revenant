# Revenant

**Revenant** is a lightweight, open-source DCA (Dollar-Cost Averaging) spot trading bot for the [Hyperliquid](https://app.hyperliquid.xyz/trade) decentralized exchange, written entirely in Python.

It automatically buys **$10 USDC** worth of **HYPE** every hour, continuously averages your entry price, and sells the entire position when the price reaches **3%** your average buy price, locking in profit and starting a new session.

Designed for simplicity and zero maintenance, Revenant deploys in minutes as a managed web service on [**DigitalOcean App Platform**](https://cloud.digitalocean.com/). No servers, Docker, or cron jobs required.

---

## Features

- Fully automated hourly DCA on **HYPE/USDC** spot
- 3% average buy price take-profit logic
- Real-time balance, price, AUM, and PnL tracking
- Background scheduler (APScheduler) runs inside the app
- Secure authentication via environment variable
- Live JSON status endpoint (`/`)
- Manual trigger endpoint (`/execute`) for testing
- Minimal, clean Flask + Hyperliquid SDK setup

---

## Quick Deploy on DigitalOcean App Platform (Recommended)

1. **Fork or clone** this repository.
2. Create a new app on [DigitalOcean App Platform](https://cloud.digitalocean.com/apps).
3. Connect your GitHub repo and select the `main` branch.
4. App Platform will auto-detect the Python app.
5. In the **Web Service** settings, set the **Run command** to: `gunicorn --worker-tmp-dir /dev/shm --preload --workers=1 app:app`
6. Add the following environment variable:
- **Key**: `HL_PRIVATE_KEY`
- **Value**: Your Hyperliquid wallet private key (starts with `0x...`)
7. Click **Create App**.

Your bot will be live within minutes and will start trading automatically every hour.

Live status: `https://your-app-name.ondigitalocean.app/`

---

## Local Development

```bash
git clone https://github.com/chainparser/revenant.git
cd revenant
python -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (or export the variable):
```bash
HL_PRIVATE_KEY=0xYourHyperliquidPrivateKeyHere
```

Run locally:
```bash
python app.py
```
Visit `http://localhost:8080/` to see the live status JSON.

---

## Configuration
You can easily tweak these values directly in `app.py`:
- `buy_size_usdc` — amount of USDC to buy per cycle (default: 10)
- Scheduler interval — currently set to 1 hour (hours=1)

Persistent storage and more configuration options (via environment variables) are planned for future releases.

---

## How It Works
Every hour the bot:
- Fetches current USDC & HYPE balances + HYPE price
- Checks if price ≥ 3% average buy price → if yes, sells everything and records PnL
- Otherwise, executes a $10 USDC market buy
- Updates average entry price and session stats

All trades are executed via the official Hyperliquid Python SDK.

---

## Security Notes
- Never commit your `HL_PRIVATE_KEY` to Git.
- The key is only read from the `HL_PRIVATE_KEY` environment variable.
- Use a dedicated sub-account/wallet with limited funds for trading.

---

## Disclaimer
This is an open-source trading bot provided as-is. Trading cryptocurrencies involves substantial risk of loss. Use at your own risk. The author is not responsible for any financial losses incurred while using Revenant.

---

## License
MIT License — see LICENSE for details.

---

Want to contribute? Open an issue or PR. Improvements, new features, and documentation are always welcome!