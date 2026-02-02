import os
import requests
from flask import Flask, jsonify
from flask_cors import CORS
from solana.rpc.api import Client
from solders.pubkey import Pubkey as PublicKey
from spl.token.instructions import get_associated_token_address
from cachetools import cached, TTLCache
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Configuration ---
COPPERINU_MINT_ADDRESS = "61Wj56QgGyyB966T7YsMzEAKRLcMvJpDbPzjkrCZc4Bi"
BURN_WALLET_ADDRESS = "1nc1nerator11111111111111111111111111111111"
# Use a more reliable RPC, but fall back to the public one.
SOLANA_RPC_URL = os.getenv("SOLANA_MAINNET_RPC_URL", "https://api.mainnet-beta.solana.com")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
COINGECKO_TOKEN_ID = "copper-inu-2"

# --- Caching ---
# Cache for 2 minutes to allow for semi-real-time updates
cache = TTLCache(maxsize=100, ttl=120)

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
    print(f"--- Fetching tokenomics data using RPC: {SOLANA_RPC_URL} ---")
    client = Client(SOLANA_RPC_URL)
    
    # --- 1. Get Total Supply ---
    total_supply = 0
    try:
        supply_response = client.get_token_supply(PublicKey(COPPERINU_MINT_ADDRESS))
        if supply_response.value.ui_amount is not None:
            total_supply = supply_response.value.ui_amount
        print(f"Successfully fetched Total Supply: {total_supply}")
    except Exception as e:
        print(f"Error getting total supply: {e}")
        total_supply = 0

    # --- 2. Get Burn Wallet Balance ---
    burned_amount = 0
    try:
        mint_key = PublicKey(COPPERINU_MINT_ADDRESS)
        burn_wallet_key = PublicKey(BURN_WALLET_ADDRESS)
        
        # Get the associated token account address for the burn wallet
        ata_address = get_associated_token_address(burn_wallet_key, mint_key)
        print(f"Calculated ATA for burn wallet: {ata_address}")

        # Get the balance of that specific token account
        balance_response = client.get_token_account_balance(ata_address)
        if balance_response.value.ui_amount is not None:
            burned_amount = balance_response.value.ui_amount
        print(f"Successfully fetched Burned Amount: {burned_amount}")
    except Exception as e:
        # This can fail if the ATA doesn't exist (i.e., no tokens ever burned), which is fine.
        print(f"Could not get burn wallet balance (this is normal if no tokens are burned yet): {e}")
        burned_amount = 0

    # --- 3. Calculate Circulating Supply ---
    circulating_supply = total_supply - burned_amount
    print(f"Calculated Circulating Supply: {circulating_supply}")

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
            print(f"Successfully fetched Price: {price}")
        except requests.exceptions.RequestException as e:
            print(f"Error getting price from CoinGecko: {e}")
            price = 0
    else:
        print("COINGECKO_API_KEY not found in .env file.")

    # --- 5. Market Cap ---
    market_cap = circulating_supply * price
    print(f"Calculated Market Cap: {market_cap}")

    # --- 6. Get Top Holders ---
    top_holders = []
    try:
        largest_accounts_response = client.get_token_largest_accounts(PublicKey(COPPERINU_MINT_ADDRESS))
        top_holders = [
            {"address": str(acc.address), "amount": acc.ui_amount_string}
            for acc in largest_accounts_response.value[:5] # Top 5
        ]
        print(f"Successfully fetched {len(top_holders)} Top Holders.")
    except Exception as e:
        print(f"Error getting top holders: {e}")
        top_holders = []

    print("--- Finished fetching tokenomics data ---")
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
    # clear_cache() # Use this for debugging if you need to force a refresh
    data = get_tokenomics_data()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
