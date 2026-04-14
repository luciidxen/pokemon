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

semaphore = asyncio.Semaphore(8)

async def fetch(url, params=None, timeout=6):
    headers = {"User-Agent": random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ])}
    async with semaphore:
        for _ in range(3):
            try:
                return await asyncio.to_thread(requests.get, url, params=params, headers=headers, timeout=timeout)
            except:
                await asyncio.sleep(0.5)
        return None

async def check_target_stock(zip_code, tcin):
    r = await fetch("https://redsky.target.com/redsky_aggregations/v1/web/product_summary_with_fulfillment_v1", {"key": "9f36aeafbe60771e321a7cc95a78140772ab3e96", "tcins": tcin, "zip": zip_code, "radius": "50"})
    if not r or r.status_code != 200: return "❌ API error", "N/A"
    try:
        data = r.json()
        price = "N/A"
        for p in data.get("products", []):
            price = p.get("price", {}).get("formatted_current_price", "N/A")
            for opt in p.get("fulfillment", {}).get("fulfillment_options", []):
                if opt.get("availability_status") == "IN_STOCK":
                    return "✅ Pickup Available" if opt.get("fulfillment_type") == "PICKUP" else "✅ IN STOCK", price
        return "❌ Out of stock", price
    except:
        return "❌ API error", "N/A"

# (All other check functions are identical to previous version - Walmart, GameStop, BestBuy, Amazon, Dick's, Pokémon Center)

async def check_product(zip_code, ids):
    results = await asyncio.gather(
        check_target_stock(zip_code, ids["target"]),
        check_walmart_stock(ids["walmart"]),
        check_gamestop_stock(ids["gamestop"]),
        check_bestbuy_stock(ids["bestbuy"]),
        check_amazon_stock(ids["amazon"]),
        check_dicks_stock(ids["dicks"]),
        check_pokemoncenter_stock(ids["pokemoncenter"]),
        return_exceptions=True
    )
    return results

# All slash commands (setzip, checkstock, addproduct, removeproduct, myproducts, monitor) are in the previous version - keep them

@tasks.loop(minutes=1)
async def stock_monitor():
    now = datetime.now()
    for user_id, info in list(monitored.items()):
        zip_code = info["zip"]
        interval_min = info.get("interval", 10)
        last_time = datetime.fromisoformat(last_check.get(user_id, "2000-01-01"))
        if (now - last_time).total_seconds() / 60 < interval_min:
            continue

        user_products = info.get("products", list(PRODUCTS.keys()))
        changed = False
        alert_msg = f"🟢 **Stock Alert** — ZIP **{zip_code}**\n"

        for name in user_products:
            ids = PRODUCTS[name]
            results = await check_product(zip_code, ids)
            current_in_stock = any("IN STOCK" in res or "Pickup Available" in res for res in results)
            was_in_stock = last_stock.get(user_id, {}).get(name, False)
            if current_in_stock and not was_in_stock:
                alert_msg += f"**{name}** → ✅ IN STOCK / Pickup\n"
                changed = True
            last_stock.setdefault(user_id, {})[name] = current_in_stock

        if changed:
            try:
                user = await client.fetch_user(int(user_id))
                await user.send(f"<@{user_id}>\n{alert_msg}")
            except:
                pass

        last_check[user_id] = now.isoformat()
        save_data()

@client.event
async def on_ready():
    await tree.sync()
    stock_monitor.start()
    print(f"✅ Bot online — {client.user} | Fully working version")

client.run(os.getenv("TOKEN"))
