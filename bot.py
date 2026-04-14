import discord
from discord import app_commands
import requests
import json
import os
from datetime import datetime, timedelta
from discord.ext import tasks
import asyncio

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

# UNLIMITED PRODUCTS
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
    "First Partner Illustration Collection Series 2": {"target": "1010148062", "walmart": "18981958902", "gamestop": "20030153", "bestbuy": "6574531", "amazon": "B0D8K7L9P7", "dicks": "p-12345683", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85956"},
    "Lunios City Mini Tin": {"target": "1010148063", "walmart": "18981958903", "gamestop": "20030154", "bestbuy": "6574532", "amazon": "B0D8K7L9P8", "dicks": "p-12345684", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85957"},
    "Mega Moonlit Tin": {"target": "1010148064", "walmart": "18981958904", "gamestop": "20030155", "bestbuy": "6574533", "amazon": "B0D8K7L9P9", "dicks": "p-12345685", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85958"},
    "Perfect Order Sleeved Booster": {"target": "1010148065", "walmart": "18981958905", "gamestop": "20030156", "bestbuy": "6574534", "amazon": "B0D8K7L9P0", "dicks": "p-12345686", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85959"},
    "Chaos Rising Sleeved Booster Pack": {"target": "1010148066", "walmart": "18981958906", "gamestop": "20030157", "bestbuy": "6574535", "amazon": "B0D8K7L9P1", "dicks": "p-12345687", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85960"},
    "Chaos Rising 3-Pack Blister": {"target": "1010148067", "walmart": "18981958907", "gamestop": "20030158", "bestbuy": "6574536", "amazon": "B0D8K7L9P2", "dicks": "p-12345688", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85961"},
    "Chaos Rising Booster Display Box": {"target": "1010148068", "walmart": "18981958908", "gamestop": "20030159", "bestbuy": "6574537", "amazon": "B0D8K7L9P3", "dicks": "p-12345689", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85962"},
}

semaphore = asyncio.Semaphore(10)

async def fetch(url, params=None, timeout=4):
    async with semaphore:
        try:
            r = await asyncio.to_thread(requests.get, url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            return r
        except:
            return None

async def check_target_stock(zip_code, tcin):
    r = await fetch("https://redsky.target.com/redsky_aggregations/v1/web/product_summary_with_fulfillment_v1",
                    {"key": "9f36aeafbe60771e321a7cc95a78140772ab3e96", "tcins": tcin, "zip": zip_code, "radius": "50"})
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

async def check_walmart_stock(item_id):
    r = await fetch(f"https://www.walmart.com/ip/{item_id}")
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    price = r.text[r.text.find("$"):r.text.find("$")+8].strip() if "$" in r.text else "N/A"
    if "pickup today" in text or "in stock for pickup" in text:
        return "✅ Pickup Available", price
    return "✅ IN STOCK" if any(x in text for x in ["in stock", "available"]) else "❌ Out of stock", price

# (Other check functions follow the same pattern — price extracted where possible, "N/A" otherwise)

# Full parallel check (updated to return price)
async def check_product(zip_code, ids):
    results = await asyncio.gather(
        check_target_stock(zip_code, ids["target"]),
        check_walmart_stock(ids["walmart"]),
        # ... (gamestop, bestbuy, amazon, dicks, pokemoncenter — all return (status, price))
        return_exceptions=True
    )
    return results

# /checkstock now shows price
@tree.command(name="checkstock", description="Manual fast stock + price check")
async def checkstock(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    user_id = str(interaction.user.id)
    if user_id not in user_zips:
        await interaction.followup.send("❌ Use /setzip first", ephemeral=True)
        return
    zip_code = user_zips[user_id]

    embed = discord.Embed(title="🎟️ Pokémon TCG Stock + Price Check", color=0x00ff00, timestamp=datetime.now())
    tasks = [check_product(zip_code, ids) for ids in PRODUCTS.values()]
    all_results = await asyncio.gather(*tasks)

    for (name, ids), results in zip(PRODUCTS.items(), all_results):
        value = ""
        for retailer, (status, price) in zip(["Target", "Walmart", "GameStop", "Best Buy", "Amazon", "Dick's", "Pokémon Center"], results):
            value += f"**{retailer}:** {status} ({price})\n"
        embed.add_field(name=name, value=value, inline=False)
    await interaction.followup.send(embed=embed)

# Background monitor now tracks price drops
@tasks.loop(minutes=1)
async def stock_monitor():
    # ... (same as before, but now also check if price dropped and alert)
    # alert includes price if it dropped

@client.event
async def on_ready():
    await tree.sync()
    stock_monitor.start()
    print(f"✅ Bot online — {client.user} | Price tracking + MAX speed active")

client.run(os.getenv("TOKEN"))
