import discord
from discord.ext import commands
import os
from datetime import datetime
import pytz
from dateutil import parser

# ---- Bot setup ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Homework storage
homework = []

# Allowed user (only you can add/clear)
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

# Timezone for El Dorado Hills
LOCAL_TZ = pytz.timezone("America/Los_Angeles")


# ---- Events ----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


# ---- Commands ----
# Add homework with due date
@bot.command()
async def addhw(ctx, subject: str, *, due: str):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can add homework.")
        return

    try:
        # Parse due date
        due_dt = parser.parse(due, fuzzy=True)
        due_dt = LOCAL_TZ.localize(due_dt)

        homework.append({"subject": subject, "due": due_dt})

        await ctx.send(f"✅ Homework added: **{subject}** (due {discord.utils.format_dt(due_dt, 'F')}, {discord.utils.format_dt(due_dt, 'R')})")

    except Exception as e:
        await ctx.send("⚠️ Couldn't read the date/time! Try like `7pm` or `10/5/25 7pm`")
        print(e)


# List homework
@bot.command()
async def hwlist(ctx):
    now = datetime.now(LOCAL_TZ)

    if not homework:
        await ctx.send(f"📕 No homework right now! (Today: {now.strftime('%Y-%m-%d %I:%M %p')})")
        return

    msg = "📘 **Homework List:**\n"
    for i, hw in enumerate(homework, 1):
        msg += f"{i}. **{hw['subject']}** — due {discord.utils.format_dt(hw['due'], 'F')} ({discord.utils.format_dt(hw['due'], 'R')})\n"

    await ctx.send(msg)


# Clear homework
@bot.command()
async def clearhw(ctx):
    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("🚫 Only my creator can clear homework.")
        return

    homework.clear()
    await ctx.send("🗑️ Homework list cleared!")


# ---- Run ----
bot.run(os.getenv("TOKEN"))
