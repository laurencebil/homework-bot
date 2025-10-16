import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import pytz
import os
from flask import Flask

# Flask app to keep Render alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# Start Flask in background
import threading
def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="!", intents=intents)

# Homework file
HOMEWORK_FILE = "homework.json"

# Load homework
def load_homework():
    try:
        with open(HOMEWORK_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Save homework
def save_homework(data):
    with open(HOMEWORK_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Convert string to date
def parse_date(date_str):
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None

# Add homework command
@client.command()
async def addhw(ctx, *, args):
    parts = args.split()
    if len(parts) < 2:
        await ctx.send("⚠️ Usage: `!addhw [name] [due date]`")
        return

    name = " ".join(parts[:-1])
    date = parse_date(parts[-1])
    if not date:
        await ctx.send("⚠️ Couldn't read the date/time! Try like `10/5/25` or `10/5/2025`")
        return

    data = load_homework()
    data.append({
        "task": name,
        "due": date.strftime("%Y-%m-%d %H:%M:%S"),
        "added": datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d %H:%M:%S")
    })
    save_homework(data)
    await ctx.send(f"✅ Added: **{name}** — due {date.strftime('%A, %B %d, %Y')}")

# List homework
@client.command()
async def hwlist(ctx):
    data = load_homework()
    if not data:
        await ctx.send("📭 No homework right now.")
        return

    message = "📘 **Homework:**\n"
    for i, hw in enumerate(data, start=1):
        due_date = datetime.strptime(hw["due"], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        delta = due_date - now
        message += f"{i}. **{hw['task']}** — due in {delta.days} day(s) ({due_date.strftime('%A, %B %d, %Y')})\n"

    last_update = datetime.now(pytz.timezone("US/Pacific")).strftime("%B %d, %Y %I:%M %p")
    message += f"\n🕒 *Last updated: {last_update}*"
    await ctx.send(message)

# Remove homework
@client.command()
async def hwremove(ctx, *, name):
    data = load_homework()
    new_data = [hw for hw in data if hw["task"].lower() != name.lower()]
    if len(new_data) == len(data):
        await ctx.send("⚠️ No homework found with that name.")
    else:
        save_homework(new_data)
        await ctx.send(f"🗑️ Removed **{name}** from the list.")

# Run bot
client.run(os.getenv("DISCORD_TOKEN"))
