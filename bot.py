from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
from discord.utils import get
from PIL import Image, ImageDraw, ImageFont
import io
import random
import json

load_dotenv()
TOKEN = os.getenv("DEIN_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Wichtig für on_member_join

bot = commands.Bot(command_prefix="!", intents=intents)

# IDs anpassen:
SUPPORT_ROLES = [1376861514274836581, 1376872221749936138]
AUTO_ROLE_ID = 1378097824041799792
WELCOME_CHANNEL_ID = 1376862356760049152  # Willkommenskanal

CATEGORY_IDS = {
    "Technischer Support": 1378105582690631831,
    "Bug": 1378105647341502615,
    "Discord Hilfe": 1378105619579535510,
}

TEAM_ROLE_IDS = SUPPORT_ROLES

# XP / Level System - Daten laden und speichern
XP_FILE = "xp_data.json"

def load_xp_data():
    try:
        with open(XP_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_xp_data(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f)

xp_data = load_xp_data()

def add_xp(user_id, amount=10):
    user_id = str(user_id)
    if user_id not in xp_data:
        xp_data[user_id] = {"xp": 0, "level": 1}
    xp_data[user_id]["xp"] += amount
    level = xp_data[user_id]["level"]
    xp = xp_data[user_id]["xp"]
    # Level up alle 100 XP
    while xp >= level * 100:
        xp -= level * 100
        level += 1
    xp_data[user_id]["xp"] = xp
    xp_data[user_id]["level"] = level
    save_xp_data(xp_data)

def get_xp(user_id):
    user_id = str(user_id)
    return xp_data.get(user_id, {"xp": 0, "level": 1})

# Ticket-System und andere Klassen (ProblemModal, TicketView etc.) hier  (1:1 wie vorher, siehe unten)

class ProblemModal(discord.ui.Modal):
    def __init__(self, ticket_type, user):
        super().__init__(title=f"Ticket: {ticket_type}")
        self.ticket_type = ticket_type
        self.user = user
        self.problem = discord.ui.TextInput(
            label="Beschreibe dein Problem",
            style=discord.TextStyle.paragraph,
            placeholder="Schreibe hier, was dein Problem ist...",
            required=True,
            max_length=500,
        )
        self.add_item(self.problem)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category_id = CATEGORY_IDS.get(self.ticket_type)
        category = discord.utils.get(guild.categories, id=category_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for role_id in SUPPORT_ROLES:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"ticket-{self.user.name}".lower()
        ticket_channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title=f"Ticket: {self.ticket_type}",
            description=f"{self.user.mention} hat ein Ticket geöffnet.\n\n**Problem:**\n{self.problem.value}",
            color=discord.Color.blue(),
        )

        view = TicketView(self.user)
        ping_roles = " ".join(f"<@&{role_id}>" for role_id in SUPPORT_ROLES)
        await ticket_channel.send(content=ping_roles, embed=embed, view=view)
        await interaction.response.send_message(f"Dein Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self, ticket_owner):
        super().__init__(timeout=None)
        self.is_taken = False
        self.taker = None
        self.ticket_owner = ticket_owner

    async def is_team_member(self, user):
        guild = user.guild
        for role_id in TEAM_ROLE_IDS:
            role = guild.get_role(role_id)
            if role in user.roles:
                return True
        return False

    @discord.ui.button(label="Ticket übernehmen", style=discord.ButtonStyle.green)
    async def take_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_team_member(interaction.user):
            await interaction.response.send_message("Nur Teammitglieder dürfen Tickets übernehmen.", ephemeral=True)
            return
        if self.is_taken:
            await interaction.response.send_message(f"Das Ticket wurde bereits von {self.taker.mention} übernommen.", ephemeral=True)
            return
        self.is_taken = True
        self.taker = interaction.user
        button.disabled = True
        self.release_button.disabled = False
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"Dieses Ticket wurde von {interaction.user.mention} übernommen!")

    @discord.ui.button(label="Ticket abgeben", style=discord.ButtonStyle.gray, disabled=True)
    async def release_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_team_member(interaction.user):
            await interaction.response.send_message("Nur Teammitglieder dürfen Tickets verwalten.", ephemeral=True)
            return
        if not self.is_taken or self.taker != interaction.user:
            await interaction.response.send_message("Du hast dieses Ticket nicht übernommen.", ephemeral=True)
            return
        self.is_taken = False
        self.taker = None
        button.disabled = True
        self.take_ticket.disabled = False
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"Das Ticket wurde von {interaction.user.mention} wieder freigegeben!")

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.red)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_team_member(interaction.user):
            await interaction.response.send_message("Nur Teammitglieder dürfen Tickets schließen.", ephemeral=True)
            return
        modal = CloseModal(self.ticket_owner)
        await interaction.response.send_modal(modal)

class CloseModal(discord.ui.Modal):
    def __init__(self, ticket_owner):
        super().__init__(title="Ticket schließen - Begründung")
        self.ticket_owner = ticket_owner
        self.reason = discord.ui.TextInput(
            label="Begründung",
            style=discord.TextStyle.paragraph,
            placeholder="Bitte gib einen Grund für das Schließen des Tickets an.",
            required=True,
            max_length=300,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.channel
        await channel.delete()

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Technischer Support", description="Hilfe bei technischen Problemen"),
            discord.SelectOption(label="Bug", description="Fehler melden"),
            discord.SelectOption(label="Discord Hilfe", description="Fragen zum Discord Server"),
        ]
        super().__init__(placeholder="Wähle den Ticket-Typ", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        modal = ProblemModal(self.values[0], interaction.user)
        await interaction.response.send_modal(modal)

class TicketMenu(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(TicketDropdown())

@bot.command()
@commands.has_permissions(administrator=True)
async def ticket(ctx):
    """Starte das Ticket-Menü (nur Admins)"""
    view = TicketMenu()
    await ctx.send("Bitte wähle den Ticket-Typ aus dem Dropdown-Menü:", view=view)

@ticket.error
async def ticket_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.message.delete()
        await ctx.send("Du hast keine Berechtigung, diesen Command zu nutzen.", delete_after=5)

@bot.command()
async def clear(ctx, amount: int = 5):
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("Du hast keine Berechtigung zum Löschen.", delete_after=5)
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"{len(deleted)-1} Nachrichten gelöscht.", delete_after=5)

@bot.command()
async def rules(ctx):
    rules_text = (
        "**Discord Regeln:**\n"
        "1. Sei respektvoll.\n"
        "2. Kein Spam oder Werbung.\n"
        "3. Keine Beleidigungen.\n"
        "4. Halte dich an die Discord Nutzungsbedingungen.\n"
    )
    await ctx.send(rules_text)

@bot.command()
async def help(ctx):
    help_text = (
        "**Verfügbare Commands:**\n"
        "`!ticket` - Öffnet das Ticket-Menü (Admins only)\n"
        "`!clear [Anzahl]` - Löscht Nachrichten\n"
        "`!rules` - Zeigt die Discord-Regeln an\n"
        "`!xp` - Zeigt deine Levelkarte mit XP an\n"
        "`!help` - Zeigt diese Hilfe an\n"
    )
    await ctx.send(help_text)

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
            title="Willkommen auf dem Server!",
            description=f"Hallo {member.mention}, schön dass du hier bist! Bitte lese die Regeln und hab Spaß 🎉",
            color=discord.Color.green()
        )
        await welcome_channel.send(embed=embed)

@bot.event
async def on_message(message):
    # XP hinzufügen, wenn Nachricht in einem Server gesendet wird
    if message.author.bot:
        return
    if message.guild:
        add_xp(message.author.id, amount=random.randint(5, 15))
    await bot.process_commands(message)

# Levelkarte generieren mit PIL
def create_level_card(user: discord.User, level: int, xp: int):
    width, height = 400, 120
    card = Image.new("RGBA", (width, height), (54, 57, 63, 255))
    draw = ImageDraw.Draw(card)

    # Profilbild laden
    asset = user.display_avatar.replace(format="png", size=128)
    data = asset.read()
    avatar = Image.open(io.BytesIO(data)).resize((100, 100)).convert("RGBA")

    # Kreis Maske für rundes Profilbild
    mask = Image.new("L", avatar.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0) + avatar.size, fill=255)

    avatar = Image.composite(avatar, Image.new("RGBA", avatar.size), mask)
    card.paste(avatar, (10, 10), avatar)

    # Text
    font = ImageFont.truetype("arial.ttf", 24)  # Arial muss verfügbar sein, sonst anpassen
    font_small = ImageFont.truetype("arial.ttf", 18)
    draw.text((120, 30), f"{user.name}", font=font, fill=(255, 255, 255, 255))
    draw.text((120, 70), f"Level: {level}", font=font_small, fill=(255, 255, 255, 255))
    draw.text((250, 70), f"XP: {xp} / {level*100}", font=font_small, fill=(255, 255, 255, 255))

    # Balken für XP
    bar_x, bar_y = 120, 100
    bar_width = 260
    bar_height = 15
    draw.rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), fill=(100, 100, 100, 255))
    xp_width = int((xp / (level * 100)) * bar_width)
    draw.rectangle((bar_x, bar_y, bar_x + xp_width, bar_y + bar_height), fill=(255, 215, 0, 255))

    # In Bytes speichern und zurückgeben
    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

@bot.command()
async def xp(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    data = get_xp(member.id)
    level = data["level"]
    xp_points = data["xp"]
    card_image = create_level_card(member, level, xp_points)
    file = discord.File(fp=card_image, filename="levelcard.png")
    await ctx.send(file=file)

bot.run(TOKEN)
