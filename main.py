import discord
from discord.ext import commands
import os
import json
from datetime import datetime
import pytz
from dateutil import parser
from flask import Flask

# ---- Flask server for Render uptime ----
app = Flask(__name__)

@app.route('/')
def home():
    return "Homework Bot is running!"

# ---- Bot setup ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Homework file
HOMEWORK_FILE = "homework.json"

# Allowed user (only you can add/clear)
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

# Timezone for El Dorado Hills
LOCAL_TZ = pytz.timezone("America/Los_Angeles")


# ---- Helper functions ----
def load_homework():
    try:
        with open(HOMEWORK_FILE, "r") as f:
            data = json.load(f)
        return data
    except Exception:
        return {"homework": [], "last_updated": 0}

def save_homework(data):
    with open(HOMEWORK_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---- Events ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


# ---- Commands ----
@bot.command()
async def addhw(ctx, subject: str, *, due: str):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can add homework.")
        return

    data = load_homework()
    homework = data.get("homework", [])

    try:
        due_dt = parser.parse(due, fuzzy=True)
        due_dt = LOCAL_TZ.localize(due_dt)

        homework.append({"subject": subject, "due": due_dt.isoformat()})
        data["homework"] = homework
        data["last_updated"] = datetime.now().timestamp()
        save_homework(data)

        await ctx.send(f"✅ Added **{subject}** (due {discord.utils.format_dt(due_dt, 'F')}, {discord.utils.format_dt(due_dt, 'R')})")

    except Exception as e:
        await ctx.send("⚠️ Couldn't read the date/time! Try like `7pm` or `10/5/25 7pm`")
        print(e)


@bot.command()
async def hwlist(ctx):
    data = load_homework()
    homework = data.get("homework", [])
    last_updated = data.get("last_updated", 0)
    now = datetime.now(LOCAL_TZ)

    if not homework:
        await ctx.send(f"📕 No homework right now! (Checked: {now.strftime('%Y-%m-%d %I:%M %p')})")
        return

    msg = "📘 **Homework List:**\n"
    for i, hw in enumerate(homework, 1):
        due_dt = datetime.fromisoformat(hw["due"])
        msg += f"{i}. **{hw['subject']}** — due {discord.utils.format_dt(due_dt, 'F')} ({discord.utils.format_dt(due_dt, 'R')})\n"

    if last_updated:
        last_updated_dt = datetime.fromtimestamp(last_updated, LOCAL_TZ)
        msg += f"\n🕒 *Last updated: {last_updated_dt.strftime('%Y-%m-%d %I:%M %p')}*"

    await ctx.send(msg)


@bot.command()
async def clearhw(ctx):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can clear homework.")
        return

    data = {"homework": [], "last_updated": datetime.now().timestamp()}
    save_homework(data)
    await ctx.send("🗑️ Homework list cleared!")


# ---- Run both Flask + Discord ----
if __name__ == "__main__":
    import threading

    def run_flask():
        app.run(host="0.0.0.0", port=10000)

    threading.Thread(target=run_flask).start()
    bot.run(os.getenv("TOKEN"))
