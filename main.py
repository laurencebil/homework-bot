import discord
from discord.ext import commands
import os
import json
from datetime import datetime
import pytz
from dateutil import parser

# ---- Setup ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Timezone for El Dorado Hills
LOCAL_TZ = pytz.timezone("America/Los_Angeles")
HOMEWORK_FILE = "homework.json"

# Load/save helpers
def load_homework():
    try:
        with open(HOMEWORK_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_homework(data):
    with open(HOMEWORK_FILE, "w") as f:
        json.dump(data, f, indent=2)

homework = load_homework()

# ---- Events ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ---- Commands ----
@bot.command()
async def addhw(ctx, subject: str, *, due: str):
    """Add homework with due date"""
    try:
        due_dt = parser.parse(due, fuzzy=True)
        due_dt = LOCAL_TZ.localize(due_dt)

        homework.append({"subject": subject, "due": due_dt.isoformat()})
        save_homework(homework)

        await ctx.send(f"✅ Added: **{subject}** (due {discord.utils.format_dt(due_dt, 'F')}, {discord.utils.format_dt(due_dt, 'R')})")

    except Exception as e:
        await ctx.send("⚠️ Couldn't read the date/time. Try formats like `10/5/25 7pm` or `Oct 5 7pm`.")
        print(e)

@bot.command()
async def hwlist(ctx):
    """List all homework"""
    if not homework:
        await ctx.send("📘 No homework currently!")
        return

    msg = "📚 **Homework List:**\n"
    for i, hw in enumerate(homework, 1):
        due_dt = parser.parse(hw["due"])
        msg += f"{i}. **{hw['subject']}** — due {discord.utils.format_dt(due_dt, 'F')} ({discord.utils.format_dt(due_dt, 'R')})\n"

    await ctx.send(msg)

@bot.command()
async def hwremove(ctx, *, subject: str):
    """Remove a homework item by exact subject name"""
    global homework
    found = False
    new_homework = []
    for hw in homework:
        if hw["subject"].lower() == subject.lower():
            found = True
        else:
            new_homework.append(hw)

    if found:
        homework[:] = new_homework
        save_homework(homework)
        await ctx.send(f"🗑️ Removed homework: **{subject}**")
    else:
        await ctx.send(f"❌ No homework found named **{subject}**")

# ---- Run ----
bot.run(os.getenv("TOKEN"))
