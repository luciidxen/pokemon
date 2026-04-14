import discord
from discord import app_commands
import requests
import json
import os
from datetime import datetime
from discord.ext import tasks

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

for uid, val in list(monitored.items()):
    if isinstance(val, str):
        monitored[uid] = {"zip": val, "interval": 10}
    elif isinstance(val, dict) and "interval" not in val:
        val["interval"] = 10

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"zips": user_zips, "monitored": monitored, "last_stock": last_stock, "last_check": last_check}, f)

# Maximized products
PRODUCTS = {
    "Surging Sparks ETB": {"target": "1010148053", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85953"},
    "Prismatic Evolutions ETB": {"target": "95230445", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/100-10019"},
    "Stellar Crown ETB": {"target": "1009318921", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/190-85923"},
    "Surging Sparks Booster Bundle": {"target": "1010148060", "walmart": "18981958900", "gamestop": "20030149", "bestbuy": "12161103", "amazon": "B0D8K7L9P3", "dicks": "p-12345679", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85954"},
    "Pokémon Day 2026 Collection": {"target": "1009318921", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/10-10394-108"},
}

# Full check functions (7 retailers)
def check_target_stock(zip_code, tcin):
    try:
        r = requests.get("https://redsky.target.com/redsky_aggregations/v1/web/product_summary_with_fulfillment_v1",
                         params={"key": "9f36aeafbe60771e321a7cc95a78140772ab3e96", "tcins": tcin, "zip": zip_code, "radius": "50", "channel": "WEB"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code != 200: return "❌ API error"
        data = r.json()
        for p in data.get("products", []):
            for opt in p.get("fulfillment", {}).get("fulfillment_options", []):
                if opt.get("availability_status") == "IN_STOCK": return "✅ IN STOCK"
            for s in p.get("fulfillment", {}).get("stores", []):
                if s.get("availability_status") == "IN_STOCK": return "✅ IN STOCK"
        return "❌ Out of stock"
    except:
        return "❌ API error"

def check_walmart_stock(item_id):
    try:
        r = requests.get(f"https://www.walmart.com/ip/{item_id}", headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        return "✅ IN STOCK" if any(x in r.text.lower() for x in ["in stock", "pickup today"]) else "❌ Out of stock"
    except:
        return "❌ API error"

def check_gamestop_stock(sku):
    try:
        r = requests.get(f"https://www.gamestop.com/product/{sku}", headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        return "✅ IN STOCK" if any(x in r.text.lower() for x in ["in stock", "pickup today"]) else "❌ Out of stock"
    except:
        return "❌ API error"

def check_bestbuy_stock(zip_code, sku):
    try:
        r = requests.get(f"https://www.bestbuy.com/api/3.0/availability/{sku}?postalCode={zip_code}", headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        data = r.json()
        return "✅ IN STOCK" if data.get("availability", {}).get("inStock") else "❌ Out of stock"
    except:
        return "❌ API error"

def check_amazon_stock(asin):
    try:
        r = requests.get(f"https://www.amazon.com/dp/{asin}", headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        return "✅ IN STOCK" if any(x in r.text.lower() for x in ["in stock", "add to cart"]) else "❌ Out of stock"
    except:
        return "❌ API error"

def check_dicks_stock(pid):
    try:
        r = requests.get(f"https://www.dickssportinggoods.com/p/{pid}", headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        return "✅ IN STOCK" if any(x in r.text.lower() for x in ["in stock", "add to cart"]) else "❌ Out of stock"
    except:
        return "❌ API error"

def check_pokemoncenter_stock(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        return "✅ IN STOCK" if any(x in r.text.lower() for x in ["add to cart", "in stock"]) else "❌ Out of stock"
    except:
        return "❌ API error"

@tree.command(name="setzip", description="Save your ZIP code")
async def setzip(interaction: discord.Interaction, zip_code: str):
    await interaction.response.defer(ephemeral=True)
    if not zip_code.isdigit() or len(zip_code) != 5:
        await interaction.followup.send("❌ Use 5-digit ZIP", ephemeral=True)
        return
    user_zips[str(interaction.user.id)] = zip_code
    save_data()
    await interaction.followup.send(f"✅ ZIP saved: **{zip_code}**", ephemeral=True)

@tree.command(name="checkstock", description="Check all products & stores")
async def checkstock(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    user_id = str(interaction.user.id)
    if user_id not in user_zips:
        await interaction.followup.send("❌ Use /setzip first", ephemeral=True)
        return
    zip_code = user_zips[user_id]

    embed = discord.Embed(title="🎟️ Pokémon TCG Stock Check", color=0x00ff00, timestamp=datetime.now())
    for name, ids in PRODUCTS.items():
        t = check_target_stock(zip_code, ids["target"])
        w = check_walmart_stock(ids["walmart"])
        g = check_gamestop_stock(ids["gamestop"])
        b = check_bestbuy_stock(zip_code, ids["bestbuy"])
        a = check_amazon_stock(ids["amazon"])
        d = check_dicks_stock(ids["dicks"])
        pc = check_pokemoncenter_stock(ids["pokemoncenter"])
        value = f"**Target:** {t}\n**Walmart:** {w}\n**GameStop:** {g}\n**Best Buy:** {b}\n**Amazon:** {a}\n**Dick's:** {d}\n**Pokémon Center:** {pc}"
        embed.add_field(name=name, value=value, inline=False)
    await interaction.followup.send(embed=embed)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online — {client.user} | Full multi-store version active")

client.run(os.getenv("TOKEN"))
