import os
import eth_account
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

# Load private key from environment variable (required for DigitalOcean)
HL_PRIVATE_KEY = os.getenv("HL_PRIVATE_KEY")
if not HL_PRIVATE_KEY:
    raise ValueError("HL_PRIVATE_KEY environment variable is not set!")

# Authentication
wallet = eth_account.Account.from_key(HL_PRIVATE_KEY)
address = wallet.address

# Initialize exchange for placing orders
exchange = Exchange(
    wallet,
    base_url=constants.MAINNET_API_URL,
    account_address=address
)

# Initialize info client for reading data (REST only)
info = Info(constants.MAINNET_API_URL, skip_ws=True)

# Get USDC and HYPE balances (available balance = total - hold)
def get_balances(BASE_ASSET, QUOTE_ASSET):
    state = info.spot_user_state(wallet.address)
    balances = state.get("balances", [])

    quote_balance = 0.0
    base_balance = 0.0

    for balance in balances:
        if balance["coin"] == QUOTE_ASSET:
            quote_balance = float(balance["total"]) - float(balance["hold"])
        if balance["coin"] == BASE_ASSET:
            base_balance = float(balance["total"]) - float(balance["hold"])

    return quote_balance, base_balance

# Get current HYPE price from mid price
def get_price(BASE_ASSET):
    all_mids = info.all_mids()
    price = all_mids.get(BASE_ASSET)
    return float(price) if price else None

# Execute market sell of HYPE
def execute_sell(BASE_ASSET, QUOTE_ASSET, base_balance: float):
    sell = exchange.market_open(
        name=f"{BASE_ASSET}/{QUOTE_ASSET}",
        is_buy=False,
        sz=round(base_balance, 2),
        slippage=0.002
    )
    return sell

# Execute market buy of HYPE with USDC amount
def execute_buy(BASE_ASSET, QUOTE_ASSET,buy_size_usdc: float):
    if get_price(BASE_ASSET) is None:
        raise ValueError(f"Could not fetch {BASE_ASSET} price")
    
    size = buy_size_usdc / get_price(BASE_ASSET)
    buy = exchange.market_open(
        name=f"{BASE_ASSET}/{QUOTE_ASSET}",
        is_buy=True,
        sz=round(size, 2),
        slippage=0.002
    )
    return buy

# Get the most recent fill (useful for logging/tracking)
def get_most_recent_fill():
    fills = info.user_fills(address)
    if not fills:
        return None
    return fills[0]