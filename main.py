# main.py
# Homework bot with Flask keep-alive, persistent JSON storage,
# multi-word subjects, permissioned add/remove, list, and clear.

import os
import json
import threading
from datetime import datetime, timedelta
import pytz
from dateutil import parser

import discord
from discord.ext import commands
from flask import Flask

# -------------------------
# Configuration
# -------------------------
HOMEWORK_FILE = "homework.json"
LOCAL_TZ = pytz.timezone("America/Los_Angeles")  # El Dorado Hills / Pacific
TOKEN = os.getenv("DISCORD_TOKEN")  # Must be set in Render as DISCORD_TOKEN

# -------------------------
# Allowed users (edit these IDs)
# -------------------------
# Put your Discord user ID and your friend's IDs here (integers).
# To get a Discord ID: enable Developer Mode in Discord, then right-click user -> "Copy ID".
ALLOWED_USERS = [
    1089268403463794858,  # <-- replace with YOUR Discord ID
    1093999272409706676,  # <-- replace with your friend's Discord ID
    # add more IDs separated by commas if needed
]

# -------------------------
# Tiny web server (keepalive for Render)
# -------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Homework bot is running."

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------------
# Persistence helpers
# -------------------------
def load_state():
    if not os.path.exists(HOMEWORK_FILE):
        state = {"homework": [], "last_updated": 0}
        save_state(state)
        return state
    try:
        with open(HOMEWORK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # normalize older formats
        if isinstance(data, list):
            data = {"homework": data, "last_updated": 0}
        if "homework" not in data:
            data["homework"] = []
        if "last_updated" not in data:
            data["last_updated"] = 0
        return data
    except Exception:
        state = {"homework": [], "last_updated": 0}
        save_state(state)
        return state

def save_state(state):
    with open(HOMEWORK_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def now_epoch():
    return int(datetime.now(tz=pytz.UTC).timestamp())

def epoch_from_dt(dt):
    return int(dt.astimezone(pytz.UTC).timestamp())

def dt_from_epoch(epoch):
    return datetime.fromtimestamp(int(epoch), tz=pytz.UTC).astimezone(LOCAL_TZ)

state = load_state()

# -------------------------
# Discord bot setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"Loaded {len(state['homework'])} homework items. last_updated={state.get('last_updated')}")

# -------------------------
# addhw: accepts multi-word subject and flexible date at the end
# Usage examples:
#   !addhw English Sadlier Unit 2 test / 2025-10-10 19:00
#   !addhw English Sadlier Unit 2 test 2025-10-10 19:00
#   !addhw English Sadlier Unit 2 test 10/10/25 7pm
# If no date supplied, default = today at 11:59pm local time.
# -------------------------
@bot.command(name="addhw")
async def addhw(ctx, *, text: str):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("🚫 You don't have permission to add homework.")
        return

    text = text.strip()
    subject = None
    due_str = None

    # Option A: explicit separator " / " -> subject / due
    if " / " in text:
        subject, due_str = text.split(" / ", 1)
    else:
        # Option B: try to guess date at end by testing last k tokens
        tokens = text.split()
        subject = text  # fallback: whole text is subject, no due
        due_str = None
        # try last 1..7 tokens as a date/time
        for k in range(1, min(8, len(tokens)+1)):
            candidate_due = " ".join(tokens[-k:])
            candidate_sub = " ".join(tokens[:-k]) or tokens[-k]
            try:
                # verify candidate_due is parseable as a date/time
                _ = parser.parse(candidate_due, fuzzy=False)
                subject = candidate_sub
                due_str = candidate_due
                break
            except Exception:
                continue

    # default due = tonight 11:59pm local
    now_local = datetime.now(LOCAL_TZ)
    if due_str:
        try:
            parsed = parser.parse(due_str, fuzzy=True)
            if parsed.tzinfo is None:
                parsed = LOCAL_TZ.localize(parsed)
            due_dt = parsed
        except Exception as e:
            await ctx.send("⚠️ Couldn't read the date/time. Try: `Subject / 2025-10-10 19:00` or `Subject 10/10/25 7pm`.")
            print("parse error:", e)
            return
    else:
        due_dt = now_local.replace(hour=23, minute=59, second=0, microsecond=0)

    # store as epoch seconds and add metadata
    epoch = epoch_from_dt(due_dt)
    entry = {
        "subject": subject.strip(),
        "due": epoch,
        "added_by": ctx.author.id,
        "added_at": now_epoch()
    }
    state["homework"].append(entry)
    state["last_updated"] = now_epoch()
    save_state(state)

    await ctx.send(f"✅ Added: **{subject.strip()}** — due <t:{epoch}:F> (<t:{epoch}:R>)")

# -------------------------
# hwlist: show grouped by subject but numbered so removal uses that number
# -------------------------
@bot.command(name="hwlist")
async def hwlist(ctx):
    if not state["homework"]:
        if state.get("last_updated"):
            await ctx.send(f"📭 No homework right now.\n_Last updated: <t:{state['last_updated']}:R>_")
        else:
            await ctx.send("📭 No homework right now.")
        return

    # build groups while keeping the original indices
    groups = {}
    for i, item in enumerate(state["homework"], start=1):
        subj = item.get("subject", "No Subject")
        groups.setdefault(subj, []).append((i, item))

    lines = ["📘 **Homework:**"]
    for subj, items in groups.items():
        lines.append(f"\n**{subj}**")
        for idx, it in items:
            due_epoch = it["due"]
            lines.append(f"{idx}. due <t:{due_epoch}:R> (<t:{due_epoch}:F>)")
    if state.get("last_updated"):
        lines.append(f"\n🕒 _Last updated: <t:{state['last_updated']}:R>_")
    await ctx.send("\n".join(lines))

# -------------------------
# done / removehw: remove by the numeric index shown in hwlist
# -------------------------
@bot.command(name="done")
async def done(ctx, idx: int):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("🚫 You don't have permission to remove homework.")
        return
    if idx < 1 or idx > len(state["homework"]):
        await ctx.send("⚠️ Invalid index. Use `!hwlist` to see the numbers.")
        return
    removed = state["homework"].pop(idx - 1)
    state["last_updated"] = now_epoch()
    save_state(state)
    await ctx.send(f"✅ Removed: **{removed.get('subject','unknown')}**")

# alias: remove by exact name (case-insensitive)
@bot.command(name="hwremove")
async def hwremove(ctx, *, name: str):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("🚫 You don't have permission to remove homework.")
        return
    name_lower = name.strip().lower()
    changed = False
    for hw in state["homework"][:]:
        if hw.get("subject", "").strip().lower() == name_lower or hw.get("subject", "").strip().lower().startswith(name_lower):
            state["homework"].remove(hw)
            changed = True
    if changed:
        state["last_updated"] = now_epoch()
        save_state(state)
        await ctx.send(f"🗑️ Removed homework matching: **{name}**")
    else:
        await ctx.send(f"⚠️ No homework found matching **{name}**. Use `!hwlist` to see exact names and numbers.")

# -------------------------
# clear all homework
# -------------------------
@bot.command(name="clearhw")
async def clearhw(ctx):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.send("🚫 You don't have permission to clear homework.")
        return
    state["homework"].clear()
    state["last_updated"] = now_epoch()
    save_state(state)
    await ctx.send("🗑️ All homework cleared.")

# -------------------------
# Run the bot
# -------------------------
if not TOKEN:
    print("ERROR: DISCORD_TOKEN environment variable not set. The bot will not start.")
else:
    bot.run(TOKEN)
