# === Keep Render Web Service alive (simple web server) ===
import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running and alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask, daemon=True).start()
# === End keep-alive ===

# === Bot code ===
import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import pytz
from dateutil import parser
import time

# ---- Config ----
HOMEWORK_FILE = "homework.json"
LOCAL_TZ = pytz.timezone("America/Los_Angeles")   # El Dorado Hills / Pacific Time
TOKEN = os.getenv("TOKEN")                        # Ensure this env var exists on Render
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---- Persistence helpers ----
def load_homework():
    if not os.path.exists(HOMEWORK_FILE):
        save_homework([])  # create file
        return []
    try:
        with open(HOMEWORK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # expect list of {"subject": str, "due": int(epoch_seconds_utc)}
            return data
    except Exception:
        return []

def save_homework(data):
    with open(HOMEWORK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

homework = load_homework()

# ---- Utilities ----
def epoch_from_dt(dt):
    # convert aware dt to UTC epoch seconds
    return int(dt.astimezone(pytz.UTC).timestamp())

def dt_from_epoch(epoch):
    # return aware datetime in local timezone
    return datetime.fromtimestamp(int(epoch), tz=pytz.UTC).astimezone(LOCAL_TZ)

# ---- Events ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"Loaded {len(homework)} homework items.")

# ---- Commands ----

@bot.command(name="addhw")
async def addhw(ctx, *, text: str):
    """Add homework. Use either:
       !addhw Task name / 10/3/25 6:30pm
       or try: !addhw Task name 10/3/25 6:30pm
       If no date/time provided, defaults to today 11:59pm.
    """
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can add homework.")
        return

    # split by " / " if present for explicit separation
    if " / " in text:
        subject, due_str = text.split(" / ", 1)
    else:
        # try to guess: try progressively larger suffixes as date/time
        tokens = text.split()
        subject = text
        due_str = None
        # try last 1..6 tokens as a date/time
        for k in range(1, min(7, len(tokens)+1)):
            candidate_due = " ".join(tokens[-k:])
            candidate_subject = " ".join(tokens[:-k]) or tokens[-k]  # fallback if nothing left
            try:
                parsed = parser.parse(candidate_due, fuzzy=False)
                subject = candidate_subject
                due_str = candidate_due
                break
            except Exception:
                continue

    # parse due
    now = datetime.now(LOCAL_TZ)
    if due_str:
        try:
            parsed = parser.parse(due_str, fuzzy=True)
            if parsed.tzinfo is None:
                parsed = LOCAL_TZ.localize(parsed)
            # if parsed < now, assume next day for time-only entries
            if parsed < now:
                if "/" not in due_str and any(ch.isdigit() for ch in due_str):
                    parsed += timedelta(days=1)
            due_dt = parsed
        except Exception:
            await ctx.send("⚠️ Couldn't read the date/time! Try: `Task / 10/3/25 6:30pm` or `Task 7pm`")
            return
    else:
        # default = tonight 11:59pm local
        due_dt = now.replace(hour=23, minute=59, second=0, microsecond=0)

    epoch = epoch_from_dt(due_dt)
    homework.append({"subject": subject.strip(), "due": epoch})
    save_homework(homework)
    await ctx.send(f"✅ Added: **{subject.strip()}** — due <t:{epoch}:R> (<t:{epoch}:F>)")

@bot.command(name="hwlist")
async def hwlist(ctx):
    now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %I:%M %p")
    if not homework:
        await ctx.send(f"📭 No homework right now! (Today: {now_str})")
        return
    lines = [f"📅 Today: {now_str}\n\n📘 **Homework:**"]
    for i, item in enumerate(homework, start=1):
        epoch = item["due"]
        lines.append(f"{i}. **{item['subject']}** — due <t:{epoch}:R> (<t:{epoch}:F>)")
    await ctx.send("\n".join(lines))

@bot.command(name="done")
async def done(ctx, idx: int):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can mark homework done.")
        return
    if 1 <= idx <= len(homework):
        removed = homework.pop(idx-1)
        save_homework(homework)
        await ctx.send(f"✅ Removed: **{removed['subject']}**")
    else:
        await ctx.send("⚠️ Invalid number. Use `!hwlist` to see indexes.")

@bot.command(name="clearhw")
async def clearhw(ctx):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can clear homework.")
        return
    homework.clear()
    save_homework(homework)
    await ctx.send("🗑️ All homework cleared!")

# ---- Run ----
if not TOKEN:
    print("ERROR: TOKEN environment variable not set. The bot will not start.")
else:
    bot.run(TOKEN)
