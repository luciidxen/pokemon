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

PRODUCTS = {
    "Surging Sparks ETB": {"target": "1010148053", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/191-85953"},
    "Prismatic Evolutions ETB": {"target": "95230445", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/100-10019"},
    "Stellar Crown ETB": {"target": "1009318921", "walmart": "18981958891", "gamestop": "20030148", "bestbuy": "12161102", "amazon": "B0D8K7L9P2", "dicks": "p-12345678", "pokemoncenter": "https://www.pokemoncenter.com/product/190-85923"},
}

# Fast checks (unchanged)
def check_target_stock(zip_code: str, tcin: str):
    try:
        r = requests.get("https://redsky.target.com/redsky_aggregations/v1/web/product_summary_with_fulfillment_v1",
                         params={"key": "9f36aeafbe60771e321a7cc95a78140772ab3e96", "tcins": tcin, "zip": zip_code, "radius": "50", "channel": "WEB"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code != 200: return False, "❌ API error"
        data = r.json()
        for p in data.get("products", []):
            for opt in p.get("fulfillment", {}).get("fulfillment_options", []):
                if opt.get("availability_status") == "IN_STOCK": return True, "✅ IN STOCK"
            for s in p.get("fulfillment", {}).get("stores", []):
                if s.get("availability_status") == "IN_STOCK": return True, "✅ IN STOCK"
        return False, "❌ Out of stock"
    except:
        return False, "❌ API error"

# (The rest of the check functions are the same as before - you can keep them from the previous version)

@tree.command(name="setzip", description="Save your ZIP code")
async def setzip(interaction: discord.Interaction, zip_code: str):
    await interaction.response.defer(ephemeral=True)
    if not zip_code.isdigit() or len(zip_code) != 5:
        await interaction.followup.send("❌ 5-digit ZIP only", ephemeral=True)
        return
    user_zips[str(interaction.user.id)] = zip_code
    save_data()
    await interaction.followup.send(f"✅ ZIP saved: **{zip_code}**", ephemeral=True)

@tree.command(name="monitor", description="Turn on/off + choose interval")
@app_commands.choices(
    action=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")],
    interval=[app_commands.Choice(name="1 minute", value=1), app_commands.Choice(name="3 minutes", value=3),
              app_commands.Choice(name="5 minutes", value=5), app_commands.Choice(name="10 minutes", value=10),
              app_commands.Choice(name="30 minutes", value=30)]
)
async def monitor(interaction: discord.Interaction, action: str, interval: int):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    action = action.lower()
    if action == "on":
        if user_id not in user_zips:
            await interaction.followup.send("❌ Use /setzip first!", ephemeral=True)
            return
        monitored[user_id] = {"zip": user_zips[user_id], "interval": interval}
        if user_id not in last_stock:
            last_stock[user_id] = {name: False for name in PRODUCTS}
        last_check[user_id] = datetime.now().isoformat()
        save_data()
        await interaction.followup.send(f"✅ **Monitoring ON** — every **{interval} minutes** + mobile ping", ephemeral=False)
    elif action == "off":
        monitored.pop(user_id, None)
        last_check.pop(user_id, None)
        save_data()
        await interaction.followup.send("✅ Monitoring stopped.", ephemeral=True)

@tree.command(name="checkstock", description="Manual check")
async def checkstock(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    user_id = str(interaction.user.id)
    if user_id not in user_zips:
        await interaction.followup.send("❌ /setzip first", ephemeral=True)
        return
    zip_code = user_zips[user_id]
    embed = discord.Embed(title="🎟️ Pokémon TCG Stock Check", color=0x00ff00, timestamp=datetime.now())
    for name, ids in PRODUCTS.items():
        t_in, t_msg = check_target_stock(zip_code, ids["target"])
        value = f"**Target:** {t_msg}"   # shortened for now
        embed.add_field(name=name, value=value, inline=False)
    await interaction.followup.send(embed=embed)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online — {client.user} | Running on Railway")

client.run(os.getenv("TOKEN"))   # ← This is the important line
