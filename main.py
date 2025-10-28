import discord
from discord.ext import commands
import json
import os
from datetime import datetime
import pytz
from flask import Flask
import threading

# --- ALLOWED USERS ---
ALLOWED_USERS = [
    1089268403463794858,  # Laurence
    1093999272409706676   # Friend
]

# --- Timezone ---
PACIFIC = pytz.timezone("US/Pacific")

# --- Flask Keep-alive ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"
def run():
    app.run(host='0.0.0.0', port=8080)
threading.Thread(target=run).start()

# --- Load or Create Homework File ---
def load_homework():
    if not os.path.exists("homework.json"):
        with open("homework.json", "w") as f:
            json.dump([], f)
    with open("homework.json", "r") as f:
        return json.load(f)

def save_homework(data):
    with open("homework.json", "w") as f:
        json.dump(data, f, indent=4)

homework_data = load_homework()

# --- Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Add Homework ---
@bot.command()
async def hwadd(ctx, *, details=None):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("You don’t have permission to add homework.")
        return

    if not details:
        await ctx.send("Please enter homework like: `!hwadd subject | assignment | due date | time (HH:MM)`")
        return

    parts = [p.strip() for p in details.split("|")]
    if len(parts) < 3:
        await ctx.send("❌ Format error. Use: `!hwadd Subject | Description | Due Date (MM/DD/YY) | Time (HH:MM optional)`")
        return

    subject, assignment, due_date = parts[0], parts[1], parts[2]
    due_time = parts[3] if len(parts) > 3 else None

    # --- Validate Date ---
    try:
        datetime.strptime(due_date, "%m/%d/%y")
    except ValueError:
        await ctx.send("❌ Invalid date format. Use `MM/DD/YY`.")
        return

    # --- Validate Time (Ask if missing) ---
    if not due_time:
        await ctx.send("⏰ Please provide a time in `HH:MM` (24-hour) format.")
        return
    else:
        try:
            datetime.strptime(due_time, "%H:%M")
        except ValueError:
            await ctx.send("❌ Invalid time format. Use `HH:MM` (24-hour).")
            return

    timestamp = datetime.now(PACIFIC).strftime("%m/%d/%y %I:%M %p")

    homework_data.append({
        "subject": subject,
        "assignment": assignment,
        "due_date": due_date,
        "due_time": due_time,
        "added_by": ctx.author.name,
        "timestamp": timestamp
    })
    save_homework(homework_data)

    await ctx.send(f"✅ Added homework for **{subject}**: {assignment} (Due {due_date} at {due_time})")

# --- Remove Homework ---
@bot.command()
async def hwremove(ctx, *, assignment_name=None):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("You don’t have permission to remove homework.")
        return

    if not assignment_name:
        await ctx.send("Please specify the exact assignment name to remove. Example: `!hwremove Unit 2 Test`")
        return

    found = False
    for hw in homework_data:
        if hw["assignment"].lower() == assignment_name.lower():
            homework_data.remove(hw)
            save_homework(homework_data)
            await ctx.send(f"🗑️ Removed homework: **{assignment_name}**")
            found = True
            break

    if not found:
        await ctx.send(f"⚠️ No homework found named: `{assignment_name}`")

# --- List Homework ---
@bot.command()
async def hwlist(ctx):
    if not homework_data:
        await ctx.send("🎉 No homework listed!")
        return

    msg = "**📚 Homework List:**\n"
    for hw in homework_data:
        msg += (
            f"**Subject:** {hw['subject']}\n"
            f"**Assignment:** {hw['assignment']}\n"
            f"**Due:** {hw['due_date']} at {hw['due_time']}\n"
            f"**Added by:** {hw['added_by']} | {hw['timestamp']}\n\n"
        )

    await ctx.send(msg)

# --- Bot Ready ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- Run Bot ---
bot.run(os.getenv("DISCORD_TOKEN"))
