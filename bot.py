import discord
from discord.ext import commands, tasks
from discord.ui import View, Select, Modal, TextInput
import datetime
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

SUPPORT_ROLES = [123456789012345678]  # Deine Supportrollen-IDs
CATEGORY_IDS = {
    "Technischer Support": 111111111111111111,
    "Allgemeine Fragen": 222222222222222222,
    "Bug melden": 333333333333333333,
}

TICKET_LOG_CHANNEL_ID = 444444444444444444  # Channel-ID für Logs

class ProblemModal(Modal, title="Beschreibe dein Problem"):
    problem = TextInput(label="Was ist dein Problem?", style=discord.TextStyle.paragraph)

    def __init__(self, ticket_type, user):
        super().__init__()
        self.ticket_type = ticket_type
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        # Missbrauchserkennung – prüfe auf existierendes Ticket des Users
        for channel in guild.text_channels:
            if channel.topic == str(user.id):
                await interaction.response.send_message(
                    "❌ Du hast bereits ein offenes Ticket. Bitte schließe es, bevor du ein neues erstellst.",
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

bot.run("DEIN_TOKEN")
