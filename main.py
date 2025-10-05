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
def load_state():
    """Return dict: { 'homework': [ {subject, due}, ... ], 'last_updated': epoch_int }"""
    if not os.path.exists(HOMEWORK_FILE):
        state = {"homework": [], "last_updated": 0}
        save_state(state)
        return state
    try:
        with open(HOMEWORK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Backwards-compat: if the file contains a list (old format), convert it
            if isinstance(data, list):
                return {"homework": data, "last_updated": 0}
            # ensure keys exist
            if "homework" not in data:
                data["homework"] = []
            if "last_updated" not in data:
                data["last_updated"] = 0
            return data
    except Exception:
        # if corrupt, reset
        state = {"homework": [], "last_updated": 0}
        save_state(state)
        return state

def save_state(state):
    with open(HOMEWORK_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

state = load_state()  # state['homework'] and state['last_updated']

# ---- Utilities ----
def epoch_from_dt(dt):
    # convert aware dt to UTC epoch seconds
    return int(dt.astimezone(pytz.UTC).timestamp())

def dt_from_epoch(epoch):
    # return aware datetime in local timezone
    return datetime.fromtimestamp(int(epoch), tz=pytz.UTC).astimezone(LOCAL_TZ)

def now_epoch():
    return int(datetime.now(tz=pytz.UTC).timestamp())

# ---- Events ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"Loaded {len(state['homework'])} homework items.")
    if state.get("last_updated"):
        print(f"Last updated (epoch): {state['last_updated']}")

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
    now_local = datetime.now(LOCAL_TZ)
    if due_str:
        try:
            parsed = parser.parse(due_str, fuzzy=True)
            if parsed.tzinfo is None:
                parsed = LOCAL_TZ.localize(parsed)
            # if parsed < now, assume next day for time-only entries
            if parsed < now_local:
                if "/" not in due_str and any(ch.isdigit() for ch in due_str):
                    parsed += timedelta(days=1)
            due_dt = parsed
        except Exception:
            await ctx.send("⚠️ Couldn't read the date/time! Try: `Task / 10/3/25 6:30pm` or `Task 7pm`")
            return
    else:
        # default = tonight 11:59pm local
        due_dt = now_local.replace(hour=23, minute=59, second=0, microsecond=0)

    epoch = epoch_from_dt(due_dt)
    state["homework"].append({"subject": subject.strip(), "due": epoch})
    # update last_updated to current UTC epoch
    state["last_updated"] = now_epoch()
    save_state(state)
    await ctx.send(f"✅ Added: **{subject.strip()}** — due <t:{epoch}:R> (<t:{epoch}:F>)")

@bot.command(name="hwlist")
async def hwlist(ctx):
    now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %I:%M %p")
    if not state["homework"]:
        # show last updated if exists
        if state.get("last_updated"):
            lu = state["last_updated"]
            await ctx.send(f"📭 No homework right now! (Today: {now_str})\n_Last updated: <t:{lu}:R> (<t:{lu}:F>)_")
        else:
            await ctx.send(f"📭 No homework right now! (Today: {now_str})\n_No updates yet._")
        return
    lines = [f"📅 Today: {now_str}\n\n📘 **Homework:**"]
    for i, item in enumerate(state["homework"], start=1):
        epoch = item["due"]
        lines.append(f"{i}. **{item['subject']}** — due <t:{epoch}:R> (<t:{epoch}:F>)")
    # last updated footer
    if state.get("last_updated"):
        lines.append(f"\n_Last updated: <t:{state['last_updated']}:R> (<t:{state['last_updated']}:F>)_")
    await ctx.send("\n".join(lines))

@bot.command(name="done")
async def done(ctx, idx: int):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can mark homework done.")
        return
    if 1 <= idx <= len(state["homework"]):
        removed = state["homework"].pop(idx-1)
        state["last_updated"] = now_epoch()
        save_state(state)
        await ctx.send(f"✅ Removed: **{removed['subject']}**")
    else:
        await ctx.send("⚠️ Invalid number. Use `!hwlist` to see indexes.")

@bot.command(name="clearhw")
async def clearhw(ctx):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can clear homework.")
        return
    state["homework"].clear()
    state["last_updated"] = now_epoch()
    save_state(state)
    await ctx.send("🗑️ All homework cleared!")

# ---- Run ----
if not TOKEN:
    print("ERROR: TOKEN environment variable not set. The bot will not start.")
else:
    bot.run(TOKEN)
