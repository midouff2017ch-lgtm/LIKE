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
ALLOWED_CHANNEL_ID = 1416458716147880111  # القناة المسموح بها فقط

@app.route("/")
def home():
    return f"Bot {bot_name} is operational"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Discord Bot Class ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.session = None

    async def setup_hook(self):
        # جلسة aiohttp واحدة
        self.session = aiohttp.ClientSession()

        # تشغيل Flask في Thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("🚀 Flask server started in background")

        # بدء المهام الدورية
        self.update_status.start()
        self.keep_alive.start()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    # --- Keep-Alive ---
    @tasks.loop(minutes=1)
    async def keep_alive(self):
        if self.session:
            try:
                url = "https://like-jwmt.onrender.com"
                async with self.session.get(url) as response:
                    print(f"💡 Keep-Alive ping status: {response.status}")
            except Exception as e:
                print(f"⚠️ Keep-Alive error: {e}")

    @keep_alive.before_loop
    async def before_keep_alive(self):
        await self.wait_until_ready()

    # --- تحديث الحالة ---
    @tasks.loop(minutes=5)
    async def update_status(self):
        try:
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers"
            )
            await self.change_presence(activity=activity)
        except Exception as e:
            print(f"⚠️ Status update failed: {e}")

    @update_status.before_loop
    async def before_status_update(self):
        await self.wait_until_ready()

    # --- السماح فقط للقناة المحددة + حذف الرسائل الغير أوامر ---
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.channel.id == ALLOWED_CHANNEL_ID:
            if not message.content.startswith("!like"):
                try:
                    await message.delete()
                    print(f"🗑️ Deleted non-command message from {message.author} in {message.channel}")
                except discord.Forbidden:
                    print(f"⚠️ Missing permissions to delete message in {message.channel}")
                except discord.HTTPException as e:
                    print(f"⚠️ Failed to delete message: {e}")
                return

        await self.process_commands(message)

# --- Bot Instance ---
bot = MyBot()

# --- Like Command ---
@bot.command(name="like")
async def like_command(ctx, server: str = None, uid: str = None):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        embed = discord.Embed(
            title="⚠️ Command Not Allowed",
            description=f"This command is only allowed in <#{ALLOWED_CHANNEL_ID}>",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    if not server or not uid or not uid.isdigit():
        await ctx.send(f"{ctx.author.mention} ❌ Usage: `!like <server_name> <uid>`")
        return

    api_url = f"https://like-api-nine.vercel.app/like?uid={uid}&server_name={server}&key=lumina"

    try:
        async with bot.session.get(api_url) as response:
            if response.status != 200:
                await ctx.send(f"{ctx.author.mention} ❌ API Error ({response.status})")
                return

            res_json = await response.json()

            likes_before = res_json.get("LikesbeforeCommand", "N/A")
            likes_after = res_json.get("LikesafterCommand", "N/A")
            nickname = res_json.get("PlayerNickname", "Unknown")
            remains = res_json.get("remains", "N/A")
            status = res_json.get("status", "N/A")

            embed = discord.Embed(
                title="⭐ Like Command Result",
                color=0x3498db,
                timestamp=ctx.message.created_at
            )
            embed.add_field(name="Player", value=nickname, inline=False)
            embed.add_field(name="UID", value=uid, inline=True)
            embed.add_field(name="Server", value=server, inline=True)
            embed.add_field(name="Likes Before", value=likes_before, inline=True)
            embed.add_field(name="Likes After", value=likes_after, inline=True)
            embed.add_field(name="Remains", value=remains, inline=True)
            embed.add_field(name="Status", value=status, inline=True)
            embed.set_footer(text="📌 Garena Free Fire | Like System")

            await ctx.send(embed=embed)

    except Exception as e:
        print(f"⚠️ Error in like_command: {e}")
        await ctx.send(f"{ctx.author.mention} ❌ Could not fetch like info. Please try again later.")

# --- Run Bot ---
async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Missing DISCORD_BOT_TOKEN in environment variables")
    asyncio.run(main())
