import discord
from discord.ext import commands, tasks
import asyncio
import os
import time
import random
import json
import mysql.connector
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


bot = commands.Bot(command_prefix="!", intents=intents)

invites = {}
recently_joined = {}

def save_invites(guild_invites):
    data = {}
    for guild_id, invites_list in guild_invites.items():
        data[guild_id] = {invite.code: invite.uses for invite in invites_list}

    with open("invites.json", "w") as f:
        json.dump(data, f)

def load_invites():
    try:
        with open("invites.json", "r") as f:
            content = f.read().strip()
            if not content:
                print("A invites.json fájl üres.")
                return {}
            data = json.loads(content)
            return {int(guild_id): data[guild_id] for guild_id in data}
    except FileNotFoundError:
        print("A invites.json fájl nem található.")
        return {}
    except json.JSONDecodeError as e:
        print(f"Hibás JSON formátum a invites.json fájlban: {e}")
        return {}

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE")
        )
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Adatbázis kapcsolat hiba: {err}")
        return None


conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="dcbot"
)
print("Sikeres kapcsolat!")


CHANNEL_ID = 1373567323826294815
LOG_CHANNEL_ID = 1370017358646608005

@bot.command(name="születésnap")
async def szuletesnap(ctx, *args):
    try:
        await ctx.message.delete()
    except:
        pass  

    if args and args[0].lower() == "törlés":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM birthdays WHERE user_id = %s", (ctx.author.id,))
        conn.commit()
        conn.close()

        msg = await ctx.send("❌ A születésnapod törölve lett.")
        await asyncio.sleep(10)
        try:
            await msg.delete()
        except:
            pass

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"🗑️ **Születésnap törölve:** {ctx.author.mention}")
        return

    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel

    question_msg = await ctx.send("📅 Kérlek, add meg a születésnapod **hónapját** (1-12):")
    try:
        month_msg = await bot.wait_for("message", timeout=30.0, check=check)
        await question_msg.delete()
        await month_msg.delete()
        month_content = month_msg.content.strip()
        if not month_content.isdigit():
            raise ValueError()
        month = int(month_content)
        if not 1 <= month <= 12:
            raise ValueError()
    except Exception:
        return await ctx.send("❌ Hibás hónap! Próbáld újra a `!születésnap` paranccsal.")



    question_msg = await ctx.send("📅 Most add meg a **napot** (1-31):")
    try:
        day_msg = await bot.wait_for("message", timeout=30.0, check=check)
        await question_msg.delete()
        await day_msg.delete()
        day_content = day_msg.content.strip()
        if not day_content.isdigit():
            raise ValueError()
        day = int(day_content)
        if not 1 <= day <= 31:
            raise ValueError()
    except Exception:
        return await ctx.send("❌ Hibás nap! Próbáld újra a `!születésnap` paranccsal.")



    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO birthdays (user_id, month, day) VALUES (%s, %s, %s)", (ctx.author.id, month, day))
    conn.commit()
    conn.close()

    msg = await ctx.send("✅ A születésnapod el lett mentve!")
    await asyncio.sleep(10)
    try:
        await msg.delete()
    except:
        pass

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📌 **Születésnap hozzáadva:** {ctx.author.mention} ({month:02}.{day:02})")

@tasks.loop(minutes=1)
async def birthday_check():
    now = datetime.now()
    if now.hour == 8 and now.minute == 0:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM birthdays WHERE month = %s AND day = %s", (now.month, now.day))
        users = cursor.fetchall()
        conn.close()

        if users:
            channel = bot.get_channel(CHANNEL_ID)
            for (user_id,) in users:
                await channel.send(f"<@{user_id}> 🎉 **Boldog születésnapot kíván a FőnixRP Admin csapata!** 🎂")

class WhitelistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Hitelesített rang megszerzése", style=discord.ButtonStyle.success, custom_id="whitelist_button")
    async def whitelist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="🧡 | Hitelesített")
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ Megkaptad a Hitelesített rangot, üdv a szerveren!", ephemeral=True)

        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"**Whitelistet kapott:** {interaction.user.mention}")

@bot.event
async def on_ready():
    print(f'✅ Bejelentkezve mint {bot.user}')
    print(json.dumps(load_invites(), indent=2))

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send("```A bot újraindult és aktív. ✅```")

    stored_invites = load_invites()

    for guild in bot.guilds:
        current_invites = await guild.invites()
        invites[guild.id] = current_invites

        if str(guild.id) in stored_invites:
            for invite in current_invites:
                if invite.code in stored_invites[str(guild.id)]:
                    invite.uses = stored_invites[str(guild.id)][invite.code]

        channel = discord.utils.get(guild.text_channels, name="『📘』whitelist")
        if channel:
            async for message in channel.history(limit=10):
                if message.author == bot.user and "Hitelesített rangot" in message.content:
                    break
            else:
                channel_mention = "<#1136975585965527091>"
                embed = discord.Embed(
                    title="✅ Whitelist",
                    description=f"Kattints a gombra, hogy megkapd a Hitelesített rangot, de mielőtt csatlakozol olvasd át a {channel_mention} szobát!",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed, view=WhitelistView())

    birthday_check.start()

@bot.event
async def on_member_join(member):
    now = time.time()
    if member.id in recently_joined and now - recently_joined[member.id] < 60:
        return

    recently_joined[member.id] = now

    old_invites = invites.get(member.guild.id, [])
    new_invites = await member.guild.invites()
    for invite in new_invites:
        for old in old_invites:
            if invite.code == old.code and invite.uses > old.uses:
                break
    invites[member.guild.id] = new_invites
    save_invites(invites)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name != "✅":
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member is None or member.bot:
        return

    channel = bot.get_channel(payload.channel_id)
    if channel.name != "『📘』whitelist":
        return

    message = await channel.fetch_message(payload.message_id)
    await message.remove_reaction(payload.emoji, member)

    role = discord.utils.get(guild.roles, name="🧡 | Hitelesített")
    if role:
        await member.add_roles(role)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"**Whitelist Hozzáadva:** {member.mention}")

tracked_tickets = {}

TICKET_LOG_CHANNEL_ID = 1376127480460480573

@bot.event
async def on_guild_channel_delete(channel):
    if isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket"):
        log_channel = bot.get_channel(TICKET_LOG_CHANNEL_ID)
        if not log_channel:
            print("❌ Ticket log csatorna nem található.")
            return

        await log_channel.send(f"📁 **Ticket lezárva/törölve:** `{channel.name}`")

        try:
            messages = [message async for message in channel.history(limit=None, oldest_first=True)]
            if not messages:
                await log_channel.send("ℹ️ A ticket üres volt.")
                return

            log_lines = [f"**Ticket log: {channel.name}**\n"]
            for msg in messages:
                timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M')
                content = msg.content or "[csatolmány vagy beágyazás]"
                log_lines.append(f"[{timestamp}] {msg.author}: {content}")

            chunk = ""
            for line in log_lines:
                if len(chunk) + len(line) > 1900:
                    await log_channel.send(f"```{chunk}```")
                    chunk = ""
                chunk += line + "\n"

            if chunk:
                await log_channel.send(f"```{chunk}```")

        except Exception as e:
            await log_channel.send(f"❌ Hiba a ticket mentése közben: {e}")

bot.run(os.getenv("TOKEN"))
