import discord
from discord.ext import commands, tasks
from flask import Flask
import threading
import os
import asyncio
import aiohttp

# --- Flask Keep-Alive ---
app = Flask(__name__)
bot_name = "Loading..."

@app.route("/")
def home():
    return f"Bot {bot_name} is operational"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Discord Bot Setup ---
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Missing DISCORD_BOT_TOKEN in environment variables")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DEFAULT_LANG = "en"
user_languages = {}
session = None  # جلسة aiohttp واحدة لجميع الطلبات

# --- Keep-Alive & Global Session Setup ---
@tasks.loop(minutes=1)
async def keep_alive():
    """Ping Render URL كل دقيقة لضمان البوت لا ينام"""
    global session
    if session:
        try:
            url = "https://info-1-rngw.onrender.com"
            async with session.get(url) as response:
                print(f"💡 Keep-Alive ping status: {response.status}")
        except Exception as e:
            print(f"⚠️ Keep-Alive error: {e}")

@keep_alive.before_loop
async def before_keep_alive():
    await bot.wait_until_ready()

# --- Check Ban Function (باستخدام نفس الجلسة) ---
async def check_ban(uid):
    global session
    if not session:
        print("⚠️ Session not initialized for check_ban")
        return None
    api_url = f"https://rawthug.onrender.com/check_ban/{uid}"
    try:
        async with session.get(api_url) as response:
            if response.status != 200:
                return None
            res_json = await response.json()
            if res_json.get("status") != 200:
                return None
            info = res_json.get("data", {})
            return {
                "is_banned": info.get("is_banned", 0),
                "nickname": info.get("nickname", ""),
                "period": info.get("period", 0),
                "region": info.get("region", "N/A")
            }
    except Exception as e:
        print(f"⚠️ Error in check_ban: {e}")
        return None

# --- Bot Events ---
@bot.event
async def on_ready():
    global bot_name, session
    bot_name = str(bot.user)
    print(f"✅ Bot connected as {bot.user} ({len(bot.guilds)} servers)")

    # إنشاء جلسة aiohttp واحدة
    if not session:
        session = aiohttp.ClientSession()

    # Start Flask server
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🚀 Flask server started in background")

    # Start periodic status update and Keep-Alive
    update_status.start()
    keep_alive.start()

# --- Bot Commands ---
@bot.command(name="lang")
async def change_language(ctx, lang_code: str):
    lang_code = lang_code.lower()
    if lang_code not in ["en", "fr"]:
        await ctx.send("❌ Invalid language. Available: `en`, `fr`")
        return
    user_languages[ctx.author.id] = lang_code
    message = "✅ Language set to English." if lang_code == 'en' else "✅ Langue définie sur le français."
    await ctx.send(f"{ctx.author.mention} {message}")

@bot.command(name="ID")
async def check_ban_command(ctx):
    user_id = ctx.message.content[3:].strip()
    lang = user_languages.get(ctx.author.id, DEFAULT_LANG)

    if not user_id.isdigit():
        msg = {
            "en": f"{ctx.author.mention} ❌ **Invalid UID!**",
            "fr": f"{ctx.author.mention} ❌ **UID invalide !**"
        }
        await ctx.send(msg[lang])
        return

    ban_status = await check_ban(user_id)
    if not ban_status:
        msg = {
            "en": f"{ctx.author.mention} ❌ Could not get information. Please try again later.",
            "fr": f"{ctx.author.mention} ❌ Impossible d'obtenir les informations. Veuillez réessayer plus tard."
        }
        await ctx.send(msg[lang])
        return

    is_banned = int(ban_status.get("is_banned", 0))
    period = ban_status.get("period", "N/A")
    nickname = ban_status.get("nickname", "NA")
    region = ban_status.get("region", "N/A")

    embed = discord.Embed(
        color=0xFF0000 if is_banned else 0x00FF00,
        timestamp=ctx.message.created_at
    )

    if is_banned:
        embed.title = "**▌ Banned Account 🛑 **" if lang == "en" else "**▌ Compte banni 🛑 **"
        embed.description = (
            f"**• {'Reason' if lang=='en' else 'Raison'}:** This account used cheats.\n"
            f"**• {'Duration' if lang=='en' else 'Durée'}:** {period}\n"
            f"**• {'Nickname' if lang=='en' else 'Pseudo'}:** {nickname}\n"
            f"**• {'Region' if lang=='en' else 'Région'}:** {region}"
        )
        embed.set_image(url="https://i.ibb.co/4gj5P7DH/banned.gif")
    else:
        embed.title = "**▌ Clean Account ✅ **" if lang == "en" else "**▌ Compte non banni ✅ **"
        embed.description = (
            f"**• {'Status' if lang=='en' else 'Statut'}:** No evidence of cheats.\n"
            f"**• {'Nickname' if lang=='en' else 'Pseudo'}:** {nickname}\n"
            f"**• {'Region' if lang=='en' else 'Région'}:** {region}"
        )
        embed.set_image(url="https://i.ibb.co/SwKrD67z/notbanned.gif")

    embed.set_footer(text="📌 Garena Free Fire")
    embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    await ctx.send(embed=embed)

# --- Periodic Bot Status ---
@tasks.loop(minutes=5)
async def update_status():
    try:
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{len(bot.guilds)} servers")
        await bot.change_presence(activity=activity)
    except Exception as e:
        print(f"⚠️ Status update failed: {e}")

# --- Run Bot ---
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
