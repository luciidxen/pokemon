import discord
from discord import app_commands
import requests
import json
import os
from datetime import datetime
from discord.ext import tasks
import asyncio
import random

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

DATA_FILE = "bot_data.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        user_zips = data.get("zips", {})
        monitored = data.get("monitored", {})
        last_stock = data.get("last_stock", {})
        last_check = data.get("last_check", {})
else:
    user_zips = {}
    monitored = {}
    last_stock = {}
    last_check = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"zips": user_zips, "monitored": monitored, "last_stock": last_stock, "last_check": last_check}, f)

PRODUCTS = {
    "Surging Sparks ETB": {"target": "1010148053", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "6574523", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85953"},
    "Surging Sparks Booster Bundle": {"target": "1010148060", "walmart": "18981958900", "gamestop": "20030149", "bestbuy": "6574526", "amazon": "B0D8K7L9P3", "dicks": "p-12345679", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85954"},
    "Surging Sparks Booster Box": {"target": "1010148061", "walmart": "18981958901", "gamestop": "20030150", "bestbuy": "6574527", "amazon": "B0D8K7L9P4", "dicks": "p-12345680", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85955"},
    "Prismatic Evolutions ETB": {"target": "95230445", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "6574524", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/100-10019"},
    "Prismatic Evolutions Booster Bundle": {"target": "1010148061", "walmart": "18981958901", "gamestop": "20030150", "bestbuy": "6574528", "amazon": "B0D8K7L9P4", "dicks": "p-12345680", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85955"},
    "Stellar Crown ETB": {"target": "1009318921", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "6574525", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/190-85923"},
    "Twilight Masquerade ETB": {"target": "1009318922", "walmart": "18981958892", "gamestop": "20030151", "bestbuy": "6574529", "amazon": "B0D8K7L9P5", "dicks": "p-12345681", "pokemoncenter": "https://www.pokemoncenter.com/product/190-85924"},
    "Paldea Evolved ETB": {"target": "1009318923", "walmart": "18981958893", "gamestop": "20030152", "bestbuy": "6574530", "amazon": "B0D8K7L9P6", "dicks": "p-12345682", "pokemoncenter": "https://www.pokemoncenter.com/product/190-85925"},
    "Pokémon Day 2026 Collection": {"target": "1009318921", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "6574527", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/10-10394-108"},
}

# Rotating User-Agents for better reliability
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
]

semaphore = asyncio.Semaphore(8)

async def fetch(url, params=None, timeout=6):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    async with semaphore:
        for attempt in range(3):  # retry up to 3 times
            try:
                r = await asyncio.to_thread(requests.get, url, params=params, headers=headers, timeout=timeout)
                if r.status_code == 200:
                    return r
                await asyncio.sleep(0.5)
            except:
                await asyncio.sleep(0.5)
        return None

# (All check functions remain the same as last working version - target, walmart, gamestop, bestbuy, amazon, dicks, pokemoncenter)

# ... [The rest of the code with /setzip, /checkstock, /addproduct, /removeproduct, /myproducts, /monitor, and stock_monitor is identical to the previous clean version]

@client.event
async def on_ready():
    await tree.sync()
    stock_monitor.start()
    print(f"✅ Bot online — {client.user} | Optimized without proxies")

client.run(os.getenv("TOKEN"))
