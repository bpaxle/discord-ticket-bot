from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DEIN_TOKEN")

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Wichtig für on_member_join

# Bot ohne Standard-Help-Command, damit eigener Help Command möglich ist
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# IDs anpassen:
SUPPORT_ROLES = [1376861514274836581, 1376872221749936138]  # Rollen mit Supportrechten
AUTO_ROLE_ID = 1378097824041799792  # Rolle, die neuen Mitgliedern automatisch vergeben wird

# Ticket-Kategorien (IDs anpassen)
CATEGORY_IDS = {
    "Technischer Support": 1378105582690631831,
    "Bug": 1378105647341502615,
    "Discord Hilfe": 1378105619579535510,
}

TEAM_ROLE_IDS = SUPPORT_ROLES  # Rollen die Tickets übernehmen/schließen dürfen

# --- Neues: Kanal-ID für die Willkommensnachricht (hier anpassen!) ---
WELCOME_CHANNEL_ID = 1378330711819288638  # <-- Hier Channel-ID eintragen!

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

# --- Neuer on_member_join mit Willkommens-Embed + Rolle vergeben ---
@bot.event
async def on_member_join(member):
    guild = member.guild
    role = guild.get_role(AUTO_ROLE_ID)
    if role:
        await member.add_roles(role)
        print(f"Rolle {role.name} wurde an {member.name} vergeben.")

    channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"👋 Willkommen auf {guild.name}, {member.name}!",
            description=(
                f"Schön, dass du da bist, {member.mention}!\n\n"
                "**📜 Unsere wichtigsten Regeln:**\n"
                "1. Sei respektvoll zu anderen.\n"
                "2. Kein Spam oder Werbung.\n"
                "3. Nutze die Kanäle korrekt.\n"
                "4. Keine illegalen Inhalte.\n"
                "5. Folge den Anweisungen des Teams.\n\n"
                "📩 Bei Fragen kannst du jederzeit ein Ticket eröffnen!"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else guild.icon.url)
        embed.set_footer(text="Viel Spaß auf dem Server!")
        await channel.send(embed=embed)

# Commands

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
    """Löscht Nachrichten, Standard 5"""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("Du hast keine Berechtigung zum Löschen.", delete_after=5)
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"{len(deleted)-1} Nachrichten gelöscht.", delete_after=5)

@bot.command()
async def help(ctx):
    help_text = (
        "**Verfügbare Commands:**\n"
        "`!ticket` - Öffnet das Ticket-Menü (Admins only)\n"
        "`!clear [Anzahl]` - Löscht Nachrichten\n"
        "`!rules` - Zeigt die Discord-Regeln an\n"
    )
    await ctx.send(help_text)

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

@bot.event
async def on_message(message):
    # Blockiere DMs an Bot
    if not message.guild:
        return
    await bot.process_commands(message)

bot.run(TOKEN)
