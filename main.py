import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from flask import Flask
import threading

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =======================
# Flask web server setup
# =======================
app = Flask(__name__)

@app.route('/')
def home():
    return "Homework Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web).start()

# =======================
# Homework JSON handling
# =======================
def load_homework():
    if not os.path.exists("homework.json"):
        with open("homework.json", "w") as f:
            json.dump([], f)
    with open("homework.json", "r") as f:
        return json.load(f)

def save_homework(homework):
    with open("homework.json", "w") as f:
        json.dump(homework, f, indent=4)

# =======================
# Discord bot commands
# =======================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game("Tracking Homework"))

# Add homework
@bot.command()
async def addhw(ctx, *, args):
    parts = args.rsplit(" ", 2)
    if len(parts) < 2:
        await ctx.send("⚠️ Please include a task and due date! Example:\n`!addhw English essay 10/10/25`")
        return

    task = parts[0].strip()
    due_date_str = parts[-1].strip()

    try:
        due_date = datetime.strptime(due_date_str, "%m/%d/%y")
    except ValueError:
        await ctx.send("⚠️ Couldn't read the date! Use format like `10/5/25`.")
        return

    homework = load_homework()
    homework.append({
        "task": task,
        "due": due_date_str,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_homework(homework)
    await ctx.send(f"✅ **Added:** {task} — due {due_date.strftime('%A, %B %d, %Y')}")

# List homework
@bot.command()
async def hwlist(ctx):
    homework = load_homework()
    if not homework:
        await ctx.send("📭 No homework right now.")
        return

    msg = "📘 **Homework:**\n"
    for i, item in enumerate(homework, 1):
        due_date = datetime.strptime(item["due"], "%m/%d/%y")
        days_left = (due_date - datetime.now()).days
        msg += f"{i}. **{item['task']}** — due {due_date.strftime('%A, %B %d, %Y')} ({days_left} days left)\n"

    last_updated = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    msg += f"\n🕒 *Last updated: {last_updated}*"
    await ctx.send(msg)

# Remove homework
@bot.command()
async def hwremove(ctx, *, name):
    name = name.strip().lower()
    homework = load_homework()

    found = False
    for item in homework:
        if item["task"].lower() == name:
            homework.remove(item)
            found = True
            break

    if found:
        save_homework(homework)
        await ctx.send(f"🗑️ Removed **{name}** from homework list.")
    else:
        await ctx.send(f"⚠️ No homework found with the name **{name}**.")

# =======================
# Run bot
# =======================
bot.run(os.getenv("DISCORD_TOKEN"))
