import os
import uuid
from google.cloud import datastore
from circle.web3 import utils as circle_utils
from circle.web3 import developer_controlled_wallets 
from dotenv import load_dotenv

load_dotenv()

# --- Circle Client Initialization ---
CIRCLE_API_KEY = os.getenv("CIRCLE_API_KEY")
CIRCLE_ENTITY_SECRET = os.getenv("CIRCLE_ENTITY_SECRET")
if not (CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET):
    raise RuntimeError("CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET must be set")

circle_client = circle_utils.init_developer_controlled_wallets_client(
    api_key=CIRCLE_API_KEY,
    entity_secret=CIRCLE_ENTITY_SECRET
)

wallets_api = developer_controlled_wallets.WalletsApi(circle_client)
walletsets_api = developer_controlled_wallets.WalletSetsApi(circle_client)
transactions_api = developer_controlled_wallets.TransactionsApi(circle_client)

# --- Ensure Wallet Set Exists ---
def get_or_create_wallet_set_id() -> str:
    """
    Fetch the first existing wallet set or create one if none exist.
    No need to set CIRCLE_WALLET_SET_ID manually.
    """
    resp = walletsets_api.get_wallet_sets()
    if resp.data and getattr(resp.data, "wallet_sets", None):
        ws = resp.data.wallet_sets[0].actual_instance
        return ws.id

    # none exist → create one
    req = developer_controlled_wallets.CreateWalletSetRequest.from_dict({
        "name": "revenant_developer_walletset"
    })
    created = walletsets_api.create_wallet_set(req)
    return created.data.wallet_set.actual_instance.id


# --- Create Wallets for a New User ---
def create_user_wallets(user_entity, user_id: str, datastore_client: datastore.Client):
    """
    Creates Arbitrum wallet (testnet only, ARB-SEPOLIA when using TEST API key).
    Updates the Datastore user entity with wallet metadata.
    """
    wallet_set_id = get_or_create_wallet_set_id()

    # Use testnet chain code when on TEST API key
    chain_targets = ["ARB-SEPOLIA"]

    wallets_created = {}
    for chain in chain_targets:
        idempotency_key = str(uuid.uuid4())
        req = developer_controlled_wallets.CreateWalletRequest.from_dict({
            "idempotency_key": idempotency_key,
            "accountType": "SCA",
            "blockchains": [chain],
            "count": 1,
            "walletSetId": wallet_set_id,
            "metadata": [{"ref_id": f"revenant:user:{user_id}:{chain}"}],
        })

        try:
            resp = wallets_api.create_wallet(create_wallet_request=req)
        except developer_controlled_wallets.ApiException as e:
            raise RuntimeError(f"Circle create_wallet failed for {chain}: {e}")

        wallet_obj = resp.data.wallets[0].actual_instance
        wallets_created[chain] = {
            "wallet_id": wallet_obj.id,
            "address": wallet_obj.address,
            "created_at": wallet_obj.create_date
        }

    # Save into Datastore
    user_entity.setdefault("wallets", {})
    user_entity["wallets"].update(wallets_created)
    datastore_client.put(user_entity)

    return wallets_created


# --- Balances ---
def get_wallet_balances(wallet_id: str):
    resp = wallets_api.list_wallet_balance(id=wallet_id)

    balances = []
    if resp.data and getattr(resp.data, "token_balances", None):
        for bal in resp.data.token_balances:
            token = bal.token
            balances.append({
                "symbol": token.symbol,
                "amount": bal.amount,
                "blockchain": token.blockchain,
                "token_address": token.token_address
            })
    return balances


# --- Transactions ---
def get_recent_transactions(wallet_id: str):
    """
    Fetch recent transactions for a wallet with optional filters.
    Only wallet_id filter is applied (do not pass blockchain at the same time).
    """
    resp = transactions_api.list_transactions(
        wallet_ids=wallet_id,
        operation="TRANSFER",
        page_size=5
        )

    txs = []
    if resp.data and getattr(resp.data, "transactions", None):
        for tx in resp.data.transactions:
            txs.append({
                "id": tx.id,
                "amounts": tx.amounts,
                "blockchain": tx.blockchain,
                "operation": tx.operation,
                "status": tx.state,
                "tx_hash": tx.tx_hash,
                "create_date": tx.create_date,
                "wallet_id": tx.wallet_id,
                "transaction_type": tx.transaction_type
            })
    return txs
