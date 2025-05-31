import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
import datetime
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

SUPPORT_ROLES = [1376861514274836581, 1376872221749936138]  # Deine Supportrollen-IDs
CATEGORY_IDS = {
    "Technischer Support": 1378105582690631831,
    "Allgemeine Fragen": 1378105647341502615,
    "Bug melden": 1378105619579535510,
}

TICKET_LOG_CHANNEL_ID = 1378351074586660937  # Channel für Ticket-Logs

# Einfaches XP/Level-System als dict (In-Memory, nicht persistent)
user_xp = {}

def get_level(xp):
    # Simple Levelformel, z.B. jede 100 XP = 1 Level
    return xp // 100

class ProblemModal(Modal, title="Beschreibe dein Problem"):
    problem = TextInput(label="Was ist dein Problem?", style=discord.TextStyle.paragraph)

    def __init__(self, ticket_type, user):
        super().__init__()
        self.ticket_type = ticket_type
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Missbrauchserkennung: 1 Ticket pro User
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
            timestamp=datetime.datetime.utcnow()
        )
        ping_roles = " ".join(f"<@&{role_id}>" for role_id in SUPPORT_ROLES)

        view = TicketView(self.user)
        await ticket_channel.send(content=ping_roles, embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Dein Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True
        )

class TicketTypeDropdown(Select):
    def __init__(self):
        options = [discord.SelectOption(label=key, value=key) for key in CATEGORY_IDS.keys()]
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

        # Optional: Loggen, bevor löschen (hier nicht implementiert)
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
    user_id = ctx.author.id
    xp = user_xp.get(user_id, 0)
    level = get_level(xp)
    embed = discord.Embed(title=f"Levelkarte von {ctx.author}", color=discord.Color.gold())
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="Level", value=str(level))
    embed.add_field(name="XP", value=str(xp))
    embed.set_footer(text="Sammle XP durch Chatten!")
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # XP pro Nachricht
    user_id = message.author.id
    user_xp[user_id] = user_xp.get(user_id, 0) + 10
    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount <= 0:
        await ctx.send("Bitte gib eine positive Zahl an.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)  # +1, um den Befehl selbst zu löschen
    await ctx.send(f"✅ Es wurden {len(deleted)-1} Nachrichten gelöscht.", delete_after=5)

bot.run("DEIN_TOKEN_HIER")
