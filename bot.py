import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
import os
import json

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

SUPPORT_ROLES = [123456789012345678]  # Deine Supportrollen-IDs ersetzen
CATEGORY_IDS = {
    "Technischer Support": 111111111111111111,
    "Allgemeine Fragen": 222222222222222222,
    "Bug melden": 333333333333333333,
}

TICKET_LOG_CHANNEL_ID = 444444444444444444  # Channel-ID für Ticket-Logs ersetzen

# --- Level-System Daten ---
xp_data_file = "xp_data.json"

def load_xp_data():
    try:
        with open(xp_data_file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_xp_data(data):
    with open(xp_data_file, "w") as f:
        json.dump(data, f)

xp_data = load_xp_data()

def get_level(xp):
    # Simple Levelformel (z.B. Level = int(sqrt(xp / 100)))
    import math
    return int(math.sqrt(xp / 100))

class ProblemModal(Modal, title="Beschreibe dein Problem"):
    problem = TextInput(label="Was ist dein Problem?", style=discord.TextStyle.paragraph)

    def __init__(self, ticket_type, user):
        super().__init__()
        self.ticket_type = ticket_type
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Missbrauchserkennung – prüfe, ob der User schon ein offenes Ticket hat
        for channel in guild.text_channels:
            if channel.topic == str(user.id):
                await interaction.response.send_message(
                    "❌ Du hast bereits ein offenes Ticket. Bitte schließe es zuerst.",
                    ephemeral=True
                )
                return

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
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=str(self.user.id)
        )

        embed = discord.Embed(
            title=f"Ticket: {self.ticket_type}",
            description=f"{self.user.mention} hat ein Ticket geöffnet.\n\n**Problem:**\n{self.problem.value}",
            color=discord.Color.blue(),
        )

        view = TicketView(self.user)
        ping_roles = " ".join(f"<@&{role_id}>" for role_id in SUPPORT_ROLES)
        await ticket_channel.send(content=ping_roles, embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Dein Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True
        )

class TicketTypeDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=key, value=key) for key in CATEGORY_IDS.keys()
        ]
        super().__init__(placeholder="Wähle den Ticket-Typ", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ProblemModal(self.values[0], interaction.user))

class TicketView(View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="🔒 Schließen", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("Nur der Ticket-Ersteller kann das Ticket schließen.", ephemeral=True)
            return

        # Optional: Log schreiben
        log_channel = bot.get_channel(TICKET_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"Ticket von {self.user} wurde geschlossen: {interaction.channel.mention}")

        await interaction.channel.delete()

@bot.event
async def on_ready():
    print(f"Bot {bot.user} ist online.")

@bot.command()
async def ticket(ctx):
    view = View()
    view.add_item(TicketTypeDropdown())
    await ctx.send("Bitte wähle den Typ deines Tickets:", view=view)

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="willkommen")
    if channel:
        await channel.send(f"👋 Willkommen auf dem Server, {member.mention}!")

@bot.command()
async def xp(ctx):
    user = ctx.author
    user_id = str(user.id)

    # XP erhöhen
    xp_data[user_id] = xp_data.get(user_id, 0) + 10  # +10 XP pro !xp-Aufruf (oder ändere nach Wunsch)
    save_xp_data(xp_data)

    xp = xp_data[user_id]
    level = get_level(xp)

    # "Levelkarte" als Text (ohne Bild)
    embed = discord.Embed(title=f"{user.name}s Levelkarte", color=discord.Color.green())
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.set_footer(text="Einfach !xp tippen, um XP zu sammeln!")

    await ctx.send(embed=embed)

# Token sicher aus Umgebungsvariablen laden
bot.run(os.getenv("TOKEN"))
