import discord
from discord import app_commands
import requests
import json
import os
from datetime import datetime
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

semaphore = asyncio.Semaphore(10)

async def fetch(url, params=None, timeout=4):
    async with semaphore:
        try:
            return await asyncio.to_thread(requests.get, url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        except:
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

async def check_walmart_stock(item_id):
    r = await fetch(f"https://www.walmart.com/ip/{item_id}")
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    price = "N/A"
    if "$" in r.text:
        price = r.text[r.text.find("$"):r.text.find("$")+8].strip()
    if "pickup today" in text or "in stock for pickup" in text:
        return "✅ Pickup Available", price
    return "✅ IN STOCK" if any(x in text for x in ["in stock", "available"]) else "❌ Out of stock", price

async def check_gamestop_stock(sku):
    r = await fetch(f"https://www.gamestop.com/product/{sku}")
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    return "✅ IN STOCK" if any(x in text for x in ["in stock", "pickup today"]) else "❌ Out of stock", "N/A"

async def check_bestbuy_stock(sku):
    r = await fetch(f"https://www.bestbuy.com/site/{sku}.p")
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    return "✅ IN STOCK" if any(x in text for x in ["add to cart", "in stock"]) else "❌ Out of stock", "N/A"

async def check_amazon_stock(asin):
    r = await fetch(f"https://www.amazon.com/dp/{asin}")
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    return "✅ IN STOCK" if any(x in text for x in ["in stock", "add to cart"]) else "❌ Out of stock", "N/A"

async def check_dicks_stock(pid):
    r = await fetch(f"https://www.dickssportinggoods.com/p/{pid}")
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    return "✅ IN STOCK" if any(x in text for x in ["in stock", "add to cart"]) else "❌ Out of stock", "N/A"

async def check_pokemoncenter_stock(url):
    r = await fetch(url)
    if not r: return "❌ API error", "N/A"
    text = r.text.lower()
    return "✅ IN STOCK" if any(x in text for x in ["add to cart", "in stock"]) else "❌ Out of stock", "N/A"

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

@tree.command(name="setzip", description="Save your ZIP code")
async def setzip(interaction: discord.Interaction, zip_code: str):
    await interaction.response.defer(ephemeral=True)
    if not zip_code.isdigit() or len(zip_code) != 5:
        await interaction.followup.send("❌ 5-digit ZIP only", ephemeral=True)
        return
    user_zips[str(interaction.user.id)] = zip_code
    save_data()
    await interaction.followup.send(f"✅ ZIP saved: **{zip_code}**", ephemeral=True)

@tree.command(name="checkstock", description="Manual stock + price check")
async def checkstock(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    user_id = str(interaction.user.id)
    if user_id not in user_zips:
        await interaction.followup.send("❌ Use /setzip first", ephemeral=True)
        return
    zip_code = user_zips[user_id]

    embed = discord.Embed(title="🎟️ Pokémon TCG Stock + Price", color=0x00ff00, timestamp=datetime.now())
    tasks = [check_product(zip_code, ids) for ids in PRODUCTS.values()]
    all_results = await asyncio.gather(*tasks)

    for (name, _), results in zip(PRODUCTS.items(), all_results):
        value = ""
        for retailer, (status, price) in zip(["Target", "Walmart", "GameStop", "Best Buy", "Amazon", "Dick's", "Pokémon Center"], results):
            value += f"**{retailer}:** {status} ({price})\n"
        embed.add_field(name=name, value=value, inline=False)
    await interaction.followup.send(embed=embed)

@tree.command(name="addproduct", description="Add a product to your personal monitor list")
@app_commands.choices(product=[app_commands.Choice(name=name, value=name) for name in PRODUCTS.keys()])
async def addproduct(interaction: discord.Interaction, product: str):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    if user_id not in monitored:
        await interaction.followup.send("❌ Use /monitor on first!", ephemeral=True)
        return
    if "products" not in monitored[user_id]:
        monitored[user_id]["products"] = []
    if product not in monitored[user_id]["products"]:
        monitored[user_id]["products"].append(product)
        save_data()
        await interaction.followup.send(f"✅ Added **{product}** to monitoring", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ Already monitoring **{product}**", ephemeral=True)

@tree.command(name="removeproduct", description="Remove a product from your monitor list")
@app_commands.choices(product=[app_commands.Choice(name=name, value=name) for name in PRODUCTS.keys()])
async def removeproduct(interaction: discord.Interaction, product: str):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    if user_id not in monitored or "products" not in monitored[user_id]:
        await interaction.followup.send("❌ Nothing to remove", ephemeral=True)
        return
    if product in monitored[user_id]["products"]:
        monitored[user_id]["products"].remove(product)
        save_data()
        await interaction.followup.send(f"✅ Removed **{product}**", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ **{product}** not in your list", ephemeral=True)

@tree.command(name="myproducts", description="Show your selected products")
async def myproducts(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    if user_id not in monitored or not monitored[user_id].get("products"):
        await interaction.followup.send("❌ No products selected yet.\nUse /addproduct", ephemeral=True)
        return
    await interaction.followup.send("**Your monitored products:**\n" + "\n".join(f"• {p}" for p in monitored[user_id]["products"]), ephemeral=True)

@tree.command(name="monitor", description="Turn monitoring on/off + interval")
@app_commands.choices(
    action=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")],
    interval=[app_commands.Choice(name="1 min", value=1), app_commands.Choice(name="3 min", value=3),
              app_commands.Choice(name="5 min", value=5), app_commands.Choice(name="10 min", value=10),
              app_commands.Choice(name="30 min", value=30)]
)
async def monitor(interaction: discord.Interaction, action: str, interval: int):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    if action == "on":
        if user_id not in user_zips:
            await interaction.followup.send("❌ Use /setzip first!", ephemeral=True)
            return
        monitored[user_id] = {"zip": user_zips[user_id], "interval": interval, "products": []}
        save_data()
        await interaction.followup.send(f"✅ Monitoring **ON** — every **{interval} minutes**", ephemeral=False)
    else:
        monitored.pop(user_id, None)
        save_data()
        await interaction.followup.send("✅ Monitoring **OFF**", ephemeral=True)

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
    print(f"✅ Bot online — {client.user} | All commands + price tracking + per-product selection")

client.run(os.getenv("TOKEN"))
