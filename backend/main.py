import os
import requests
from flask import Flask, jsonify
from flask_cors import CORS
from solana.rpc.api import Client
from solders.pubkey import Pubkey as PublicKey
from cachetools import cached, TTLCache
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Configuration ---
COPPERINU_MINT_ADDRESS = "61Wj56QgGyyB966T7YsMzEAKRLcMvJpDbPzjkrCZc4Bi"
BURN_WALLET_ADDRESS = "1nc1nerator11111111111111111111111111111111"
SOLANA_RPC_URL = os.getenv("SOLANA_MAINNET_RPC_URL", "https://api.mainnet-beta.solana.com")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
COINGECKO_TOKEN_ID = "copper-inu-2"

# --- Caching ---
cache = TTLCache(maxsize=100, ttl=300)

# --- Security Headers ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# --- API Logic ---
@cached(cache)
def get_tokenomics_data():
    client = Client(SOLANA_RPC_URL)
    
    # --- 1. Get Total Supply ---
    try:
        supply_response = client.get_token_supply(PublicKey(COPPERINU_MINT_ADDRESS))
        total_supply = supply_response.value.ui_amount
    except Exception as e:
        print(f"Error getting total supply: {e}")
        total_supply = 0

    # --- 2. Get Burn Wallet Balance ---
    burned_amount = 0
    try:
        token_accounts = client.get_token_accounts_by_owner(
            owner=PublicKey(BURN_WALLET_ADDRESS),
            opts={"encoding": "jsonParsed"}
        )
        for account in token_accounts.value:
            if account['account']['data']['parsed']['info']['mint'] == COPPERINU_MINT_ADDRESS:
                burned_amount = account['account']['data']['parsed']['info']['tokenAmount']['uiAmount']
                break
    except Exception as e:
        print(f"Error getting burn wallet balance: {e}")
        burned_amount = 0

    # --- 3. Calculate Circulating Supply ---
    circulating_supply = total_supply - burned_amount if total_supply > 0 else 0

    # --- 4. Get Price from CoinGecko ---
    price = 0
    if COINGECKO_API_KEY:
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={COINGECKO_TOKEN_ID}&vs_currencies=usd"
            headers = {"x-cg-demo-api-key": COINGECKO_API_KEY}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if COINGECKO_TOKEN_ID in data and 'usd' in data[COINGECKO_TOKEN_ID]:
                price = data[COINGECKO_TOKEN_ID]['usd']
        except requests.exceptions.RequestException as e:
            print(f"Error getting price from CoinGecko: {e}")
            price = 0
    else:
        print("COINGECKO_API_KEY not found in .env file.")

    # --- 5. Market Cap ---
    market_cap = circulating_supply * price if circulating_supply > 0 and price > 0 else 0

    # --- 6. Get Top Holders ---
    try:
        largest_accounts_response = client.get_token_largest_accounts(PublicKey(COPPERINU_MINT_ADDRESS))
        top_holders = [
            {"address": str(acc.address), "amount": acc.ui_amount_string}
            for acc in largest_accounts_response.value[:5] # Top 5
        ]
    except Exception as e:
        print(f"Error getting top holders: {e}")
        top_holders = []

    return {
        "totalSupply": total_supply,
        "burnedAmount": burned_amount,
        "circulatingSupply": circulating_supply,
        "topHolders": top_holders,
        "marketCap": market_cap,
        "price": price
    }

@app.route('/api/tokenomics')
def tokenomics_endpoint():
    data = get_tokenomics_data()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
