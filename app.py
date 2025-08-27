from flask import Flask, redirect, url_for, session, render_template
from authlib.integrations.flask_client import OAuth
from google.cloud import datastore 
from datetime import datetime, timezone 
from functools import wraps 
import os

from datastore_session import DatastoreSessionInterface 
from wallet_service import create_user_wallets, get_wallet_balances, get_recent_transactions 
from utils import generate_qr_code, format_usd 



# --- Flask App Setup ---
app = Flask(__name__)
# Secret key (use a strong random value in production!)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

# Use Google Cloud Datastore for session storage
app.session_interface = DatastoreSessionInterface(project_id="revenant1")

# Datastore client (for user accounts)
datastore_client = datastore.Client(project="revenant1")


# --- OAuth Setup (Google Sign-In) ---
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)


# --- Helpers ---
def login_required(f):
    """
    Decorator to protect routes that require login.
    Redirects to homepage if user is not signed in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user():
    """
    Makes the current signed-in user available in all templates
    as the `user` variable.
    """
    user = None
    if "user_id" in session:
        key = datastore_client.key("user", session["user_id"])
        user = datastore_client.get(key)
    return dict(user=user)


# --- Routes ---

@app.route("/")
def index():
    """Homepage: marketing landing page for guests, wallet for signed-in users."""
    if "user_id" in session:
        return redirect(url_for("wallet"))
    return render_template("index.html")


@app.route("/login")
def login():
    """Initiate Google OAuth login."""
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/callback")
def authorize():
    """
    OAuth callback from Google.
    - Fetches Google user profile
    - Creates Revenant account in Datastore if new
    - Saves only user_id in session
    - Redirects to Wallet
    """
    token = google.authorize_access_token()
    resp = google.get("userinfo")
    data = resp.json()

    # Some providers return {user: {...}}, others return {...}
    user_info = data.get("user", data)

    if not user_info or "id" not in user_info:
        return "Failed to fetch user info", 400

    user_id = user_info["id"]

    # Lookup user in Datastore
    key = datastore_client.key("user", user_id)
    user = datastore_client.get(key)

    if not user:
        # New user → create Revenant account
        user = datastore.Entity(key=key)
        user.update({
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "given_name": user_info.get("given_name"),
            "family_name": user_info.get("family_name"),
            "picture": user_info.get("picture"),
            "verified_email": user_info.get("verified_email"),
            "created_at": datetime.now(timezone.utc),
            "balance": 0.0,
            "tier": "free",
            "settings": {},
        })
        datastore_client.put(user)

        # 🔹 Create Circle wallets (mainnet + testnet)
        try:
            create_user_wallets(user, user_id, datastore_client)
        except Exception as exc:
            app.logger.exception("Wallet creation failed for user %s: %s", user_id, exc)
            user["wallet_creation_failed"] = True
            datastore_client.put(user)


    # Save only the ID in session (keeps cookie light + secure)
    session["user_id"] = user_id
    return redirect(url_for("wallet"))


@app.route("/logout")
def logout():
    """Clear session and return to homepage."""
    session.pop("user_id", None)
    return redirect(url_for("index"))


# --- Authenticated Pages ---
@app.route("/wallet")
@login_required
def wallet():
    key = datastore_client.key("user", session["user_id"])
    user = datastore_client.get(key)

    # Defaults
    formatted_balance = format_usd(0.0)
    deposit_address = None
    qr_code_base64 = None
    transactions = []
    funding_balance = 0.0
    hyperliquid_balance = 0.0
    # We’ll also precompute the donut values (no math in Jinja)
    donut = {
        "total": 0.0,
        "funding": 0.0,
        "hyper": 0.0,
        "funding_pct": 0.0,
        "hyper_pct": 0.0,
        "total_formatted": "$0.00",
    }

    if user and "wallets" in user:
        wallet_info = user["wallets"].get("ARB-SEPOLIA")
        if wallet_info and wallet_info.get("wallet_id"):
            wid = wallet_info["wallet_id"]
            deposit_address = wallet_info.get("address")

            try:
                balances = get_wallet_balances(wid)
                if balances:
                    # Assume USDC is first (or find it by symbol)
                    usdc = next((b for b in balances if (b.get("symbol") or "").upper() == "USDC"), balances[0])
                    chain_usdc_balance = float(usdc.get("amount") or 0.0)
                    formatted_balance = format_usd(chain_usdc_balance)

                    # Use any persisted split if you have it; otherwise default all to funding
                    funding_balance = float(user.get("funding_balance", chain_usdc_balance))
                    hyperliquid_balance = float(user.get("hyperliquid_balance", 0.0))

                    # Ensure the split never exceeds the on-chain total (soft guard)
                    # You can change this logic if you want to show “pending” too.
                    total = max(chain_usdc_balance, funding_balance + hyperliquid_balance)

                    donut["total"] = total
                    donut["funding"] = funding_balance
                    donut["hyper"] = hyperliquid_balance
                    donut["funding_pct"] = round((funding_balance / total) * 100, 4) if total > 0 else 0.0
                    donut["hyper_pct"] = round(100.0 - donut["funding_pct"], 4) if total > 0 else 0.0
                    donut["total_formatted"] = format_usd(total)

                transactions = get_recent_transactions(wid)
            except Exception as e:
                app.logger.error(f"Error fetching balances/transfers: {e}")

            if deposit_address:
                qr_code_base64 = generate_qr_code(deposit_address)

    return render_template(
        "wallet.html",
        page_title="Wallet",
        page_desc="Your balances and deposits",
        formatted_balance=formatted_balance,
        deposit_address=deposit_address,
        qr_code_base64=qr_code_base64,
        transactions=transactions,
        # donut/breakdown data (numbers only; no template math)
        funding_balance=funding_balance,
        hyperliquid_balance=hyperliquid_balance,
        donut=donut,
    )


@app.route("/account")
@login_required
def account():
    """User account management page."""
    return render_template("account.html", page_title="Account", page_desc="Manage your Revenant account")

@app.route("/notices")
@login_required
def notices():
    """System notices & alerts."""
    return render_template("notices.html", page_title="Notices", page_desc="Important updates and alerts")

@app.route("/strategies")
@login_required
def strategies():
    """AI-driven trading strategies page."""
    return render_template("strategies.html", page_title="Strategies", page_desc="AI-driven trading strategies")


# --- Run App ---
if __name__ == "__main__":
    app.run(debug=True)
