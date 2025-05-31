from dotenv import load_dotenv
import os
import discord
from discord.ext import commands, tasks
import json
import asyncio

load_dotenv()
TOKEN = os.getenv("DEIN_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Wichtig für on_member_join

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# IDs anpassen:
SUPPORT_ROLES = [1376861514274836581, 1376872221749936138]
AUTO_ROLE_ID = 1378097824041799792
WELCOME_CHANNEL_ID = 1378330711819288638

CATEGORY_IDS = {
    "Technischer Support": 1378105582690631831,
    "Bug": 1378105647341502615,
    "Discord Hilfe": 1378105619579535510,
}

TEAM_ROLE_IDS = SUPPORT_ROLES

# --- Ticket-System Klassen und Commands ---
# (Dein kompletter Ticket-Code hier, wie du ihn hattest)
# Ich nehme an, den hast du schon und ich lasse ihn weg, um den Fokus auf neue Sachen zu behalten.

# --- Level-/XP-System ---
XP_FILE = "xp.json"
xp_data = {}

def load_xp():
    global xp_data
    try:
        with open(XP_FILE, "r") as f:
            xp_data = json.load(f)
    except FileNotFoundError:
        xp_data = {}

def save_xp():
    with open(XP_FILE, "w") as f:
        json.dump(xp_data, f)

def add_xp(user_id, amount):
    user_id_str = str(user_id)
    if user_id_str not in xp_data:
        xp_data[user_id_str] = {"xp": 0, "level": 0}
    xp_data[user_id_str]["xp"] += amount
    level_up = False
    current_level = xp_data[user_id_str]["level"]
    new_level = int(xp_data[user_id_str]["xp"] ** 0.5 // 1)  # Level = floor(sqrt(xp))
    if new_level > current_level:
        xp_data[user_id_str]["level"] = new_level
        level_up = True
    return level_up, new_level

@bot.event
async def on_ready():
    print(f"Bot ist eingeloggt als {bot.user}")
    load_xp()

@bot.event
async def on_member_join(member):
    guild = member.guild
    role = guild.get_role(AUTO_ROLE_ID)
    if role:
        await member.add_roles(role)
        print(f"Rolle {role.name} wurde an {member.name} vergeben.")

    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=f"Willkommen {member.name}!",
            description=(
                "Schön, dass du da bist! Bitte lies dir unsere Regeln durch:\n"
                "1. Sei respektvoll.\n"
                "2. Kein Spam oder Werbung.\n"
                "3. Keine Beleidigungen.\n"
                "4. Halte dich an die Discord Nutzungsbedingungen.\n"
            ),
            color=discord.Color.green(),
        )
        await welcome_channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # XP vergeben
    level_up, new_level = add_xp(message.author.id, 5)  # z.B. 5 XP pro Nachricht
    if level_up:
        await message.channel.send(f"🎉 {message.author.mention}, du bist jetzt Level {new_level}!")

    save_xp()

    await bot.process_commands(message)

# Hier kannst du dein restliches Ticket-System und andere Commands anhängen
# Zum Beispiel dein !ticket Command, !clear, !help, usw.

bot.run(TOKEN)
