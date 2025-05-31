import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True  # WICHTIG: Damit der Bot Nachrichten lesen kann

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot ist online als {bot.user}")

@bot.command()
async def test(ctx):
    await ctx.send("Das ist ein Test")

bot.run("DEIN_BOT_TOKEN_HIER")
