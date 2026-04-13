import os, time
from flask import Flask, jsonify
import utility
import datetime

# Add background scheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# Define global variables
counter = {
    "avg_buy_price": float(0.0),
    "total_sessions": 0,
    "buy_size_usdc": float(10.0),
    "buy_count": 0,
    "total_buy_trades": 0,
    "total_volume_usdc": float(0.0)
}

BASE_ASSET = "HYPE"
QUOTE_ASSET = "USDC"

@app.route('/')
def home():
    return jsonify(counter)


@app.route("/execute")
def execute():

    # Initialize status
    status = ""

    # Fetch current market data, update AUM
    quote_balance, base_balance = utility.get_balances(BASE_ASSET, QUOTE_ASSET)
    price = utility.get_price(BASE_ASSET)
    AUM = float(quote_balance) + (float(base_balance) * float(price))

    # Save balances
    counter["base_balance"] = base_balance
    counter["quote_balance"] = quote_balance
    counter["price"] = price
    counter["AUM"] = AUM

    # Start/continue trading
    # Check if sell condition is met.
    sell_condition_is_met = False

    if float(price) >= float(counter["avg_buy_price"]) * 0.03 and float(counter["avg_buy_price"]) != float(0):
        sell_condition_is_met = True

    # if sell condition is met, liquidate hype position, end session, and start a new session. else keep buying.
    if sell_condition_is_met:
        # liquidate hype position (sell all of hype balance)
        sell = utility.execute_sell(BASE_ASSET, QUOTE_ASSET, base_balance)

        # get fill price and calculate pnl in usdc
        time.sleep(5)

        most_recent_fill = utility.get_most_recent_fill()

        avg_fill_price = most_recent_fill["px"]
        pnl_usdc = (float(avg_fill_price) - float(counter["avg_buy_price"])) * float(counter["base_balance"]) # (avg fill price - avg buy price) * total hype bought

        # update counter
        counter["pnl_usdc"] = pnl_usdc
        counter["total_sessions"] += 1
        counter["total_volume_usdc"] += (float(base_balance) * float(avg_fill_price))
        counter["last_trade"] = datetime.datetime.now(datetime.UTC)

        status = "Sell condition met, HYPE holdings sold."
    else:
        # keep buying with a constant size of $10
        buy_size_usdc = counter["buy_size_usdc"]

        # Execute buy if buy size is less than or equal to the available balance
        if buy_size_usdc <= quote_balance:
            
            # execute buy
            buy = utility.execute_buy(BASE_ASSET, QUOTE_ASSET, float(buy_size_usdc))

            # wait 5 seconds, get most recent fill details
            time.sleep(5)

            most_recent_fill = utility.get_most_recent_fill()
            avg_fill_price = most_recent_fill["px"]

            if float(counter["avg_buy_price"]) == float(0):
                counter["avg_buy_price"] = float(avg_fill_price)
            else:
                counter["avg_buy_price"] = (float(counter["avg_buy_price"]) + float(avg_fill_price))/2
            

            # Update counter
            counter["buy_count"] += 1
            counter["total_buy_trades"] += 1
            counter["total_volume_usdc"] += float(buy_size_usdc)
            counter["last_trade"] = datetime.datetime.now(datetime.UTC)

            status =  "Sell condition not met, buy executed."
            
        else:
            status  = "Sell condition not met, balance low." # buy nothing when balance low, wait for next 15 minutes

    return jsonify(status) 

# ── Background Scheduler (runs automatically every hour) ──
scheduler = BackgroundScheduler()

def scheduled_execute():
    """Wrapper that runs the trading cycle from the background job."""
    with app.app_context():
        execute()

scheduler.add_job(
    scheduled_execute,
    trigger='interval',
    hours=1,
    id='revenant_dca_cycle',
    replace_existing=True
)
scheduler.start()

# Gracefully shut down scheduler when the app exits
atexit.register(lambda: scheduler.shutdown(wait=False))

# Optional: only used when running locally with `python app.py`
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)