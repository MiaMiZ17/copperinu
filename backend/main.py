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

# --- Use a more reliable, hardcoded RPC from Helius ---
# This avoids issues with environment variables and public RPC rate limits.
HELIUS_RPC_URL = "https://mainnet.helius-rpc.com/?api-key=1f847c92-b439-4494-8145-733c6969542a"
SOLANA_RPC_URL = os.getenv("SOLANA_MAINNET_RPC_URL", HELIUS_RPC_URL)

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
    print("--- [START] Fetching tokenomics data ---")
    print(f"Using RPC: {SOLANA_RPC_URL}")
    client = Client(SOLANA_RPC_URL)
    
    # --- 1. Get Total Supply ---
    total_supply = 0
    try:
        print("[LOG] Fetching total supply...")
        mint_public_key = PublicKey.from_string(COPPERINU_MINT_ADDRESS)
        supply_response = client.get_token_supply(mint_public_key)
        total_supply = supply_response.value.ui_amount or 0
        print(f"[SUCCESS] Total Supply: {total_supply}")
    except Exception as e:
        print(f"[ERROR] Getting total supply: {e}")
        total_supply = 0

    # --- 2. Get Burn Wallet Balance ---
    burned_amount = 0
    try:
        print("[LOG] Fetching burn wallet balance...")
        mint_key = PublicKey.from_string(COPPERINU_MINT_ADDRESS)
        burn_wallet_key = PublicKey.from_string(BURN_WALLET_ADDRESS)
        
        ata_address = get_associated_token_address(burn_wallet_key, mint_key)
        print(f"[LOG] Calculated ATA for burn wallet: {ata_address}")

        balance_response = client.get_token_account_balance(ata_address)
        burned_amount = balance_response.value.ui_amount or 0
        print(f"[SUCCESS] Burned Amount: {burned_amount}")
    except Exception as e:
        print(f"[INFO] Could not get burn wallet balance (this is normal if ATA does not exist): {e}")
        burned_amount = 0

    # --- 3. Calculate Circulating Supply ---
    circulating_supply = total_supply - burned_amount
    print(f"[LOG] Calculated Circulating Supply: {circulating_supply}")

    # --- 4. Get Price from CoinGecko ---
    price = 0
    if COINGECKO_API_KEY:
        try:
            print("[LOG] Fetching price from CoinGecko...")
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={COINGECKO_TOKEN_ID}&vs_currencies=usd"
            headers = {"x-cg-demo-api-key": COINGECKO_API_KEY}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            price = data.get(COINGECKO_TOKEN_ID, {}).get('usd', 0)
            print(f"[SUCCESS] Price: {price}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Getting price from CoinGecko: {e}")
            price = 0
    else:
        print("[WARN] COINGECKO_API_KEY not found in .env file.")

    # --- 5. Market Cap ---
    market_cap = circulating_supply * price
    print(f"[LOG] Calculated Market Cap: {market_cap}")

    # --- 6. Get Top Holders ---
    top_holders = []
    try:
        print("[LOG] Fetching top holders...")
        mint_public_key_for_holders = PublicKey.from_string(COPPERINU_MINT_ADDRESS)
        largest_accounts_response = client.get_token_largest_accounts(mint_public_key_for_holders)
        top_holders = [
            {"address": str(acc.address), "amount": acc.ui_amount_string}
            for acc in largest_accounts_response.value[:5]
        ]
        print(f"[SUCCESS] Fetched {len(top_holders)} Top Holders.")
    except Exception as e:
        print(f"[ERROR] Getting top holders: {e}")
        top_holders = []

    print("--- [END] Finished fetching tokenomics data ---")
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
