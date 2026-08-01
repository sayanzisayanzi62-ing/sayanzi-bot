# =========================================
# SAYANZI FINAL BOT (ENGLISH RESPONSES & FULL FEATURES)
# discord.py 2.x
# =========================================

import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import asyncio
import sqlite3
import time
import random
import io
import os

TOKEN = os.getenv("TOKEN")

COLOR = 0x8000ff
OWNER_ID = 1446592341908652112
SUPPORT_INVITE = "https://discord.gg/h3FB6hsmn"
BOT_INVITE = "https://discord.com/oauth2/authorize?client_id=1501541120058851348&permissions=8&integration_type=0&scope=bot"

# =========================================
# BOT INTENTS SETUP
# =========================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=["!", "#", "c."],
    intents=intents,
    case_insensitive=True,
    help_command=None
)

# =========================================
# DATABASE INITIALIZATION
# =========================================

db = sqlite3.connect("sayanzi.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS xp(
guild_id TEXT,
user_id TEXT,
messages INTEGER DEFAULT 0,
day_count INTEGER DEFAULT 0,
week_count INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS warns(
guild_id TEXT,
user_id TEXT,
warns INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS economy(
user_id TEXT PRIMARY KEY,
balance REAL DEFAULT 0,
last_daily REAL DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS welcome_settings(
guild_id TEXT PRIMARY KEY,
message TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS premium_users(
user_id TEXT,
guild_id TEXT,
role_id TEXT,
expiry_time REAL,
PRIMARY KEY (user_id, guild_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS mafia_hints_usage(
user_id TEXT,
guild_id TEXT,
hints_count INTEGER DEFAULT 0,
last_reset REAL,
PRIMARY KEY (user_id, guild_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS server_settings(
guild_id TEXT PRIMARY KEY,
t_role_id TEXT,
admin_role_id TEXT
)
""")

db.commit()

# =========================================
# CACHE & DICTIONARIES
# =========================================

auto_replies = {}
badword_words = {}
spam_cache = {}

# =========================================
# PERMISSIONS & HIERARCHY CHECKS
# =========================================

def is_admin(interaction_or_member, guild=None):
    if isinstance(interaction_or_member, discord.Interaction):
        user = interaction_or_member.user
        g = interaction_or_member.guild
    else:
        user = interaction_or_member
        g = guild

    if not g:
        return False
    
    if user.id == g.owner_id:
        return True

    member = g.get_member(user.id)
    if member and member.guild_permissions.administrator:
        return True
        
    return False

def is_user_premium(user_id, guild_id):
    if user_id == OWNER_ID:
        return True
    current_time = time.time()
    cur.execute("SELECT expiry_time FROM premium_users WHERE user_id=? AND guild_id=?", (str(user_id), str(guild_id)))
    row = cur.fetchone()
    if row and row[0] > current_time:
        return True
    return False

async def check_admin_and_hierarchy(interaction: discord.Interaction, member: discord.Member = None):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You cannot do this, you lack Administrator permissions.", ephemeral=True)
        return False

    if member:
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ Their role is higher than mine!", ephemeral=True)
            return False

        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Their role is higher than yours!", ephemeral=True)
            return False

    return True

def parse_time(t):
    try:
        value = int(t[:-1])
        unit = t[-1].lower()

        if unit == "s":
            return value
        elif unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
    except:
        return None

# =========================================
# PROBOT STYLE CAPTCHA VIEW FOR TRANSFERS
# =========================================

class TransferCaptchaModal(discord.ui.Modal, title="Transfer Confirmation"):
    def __init__(self, sender: discord.Member, recipient: discord.Member, amount: float, tax: float, net_amount: float, expected_code: str):
        super().__init__()
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.tax = tax
        self.net_amount = net_amount
        self.expected_code = expected_code

        self.code_input = discord.ui.TextInput(
            label="Type the numbers shown in the image to confirm",
            placeholder="Type numbers here...",
            min_length=4,
            max_length=6,
            required=True
        )
        self.add_item(self.code_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.sender.id:
            return await interaction.response.send_message("❌ This menu is not for you!", ephemeral=True)

        user_input = self.code_input.value.strip()
        if user_input != self.expected_code:
            return await interaction.response.send_message("❌ Incorrect numbers, transfer cancelled.", ephemeral=True)

        uid = str(self.sender.id)
        r_uid = str(self.recipient.id)

        cur.execute("SELECT balance FROM economy WHERE user_id=?", (uid,))
        s_row = cur.fetchone()
        s_bal = s_row[0] if s_row else 0.0

        if s_bal < self.amount:
            return await interaction.response.send_message(f"❌ You do not have enough balance! Current balance: **`${s_bal:,.0f}`**", ephemeral=True)

        cur.execute("UPDATE economy SET balance = balance - ? WHERE user_id=?", (self.amount, uid))
        
        cur.execute("SELECT balance FROM economy WHERE user_id=?", (r_uid,))
        r_row = cur.fetchone()
        if r_row:
            cur.execute("UPDATE economy SET balance = balance + ? WHERE user_id=?", (self.net_amount, r_uid))
        else:
            cur.execute("INSERT INTO economy VALUES(?,?,?)", (r_uid, self.net_amount, 0))
        db.commit()

        success_text = f"💰 | **{self.sender.name}, has transferred `${self.net_amount:,.0f}` to {self.recipient.name}**"
        await interaction.response.send_message(success_text)


class TransferConfirmView(discord.ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member, amount: float, tax: float, net_amount: float, expected_code: str):
        super().__init__(timeout=60)
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.tax = tax
        self.net_amount = net_amount
        self.expected_code = expected_code

    @discord.ui.button(label="Confirm Transfer 🔢", style=discord.ButtonStyle.green)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.sender.id:
            return await interaction.response.send_message("❌ Button not assigned to you!", ephemeral=True)
        modal = TransferCaptchaModal(self.sender, self.recipient, self.amount, self.tax, self.net_amount, self.expected_code)
        await interaction.response.send_modal(modal)

# =========================================
# GAMES VIEWS (MAFIA & CHAIRS)
# =========================================

class MafiaView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=180)
        self.players = []
        self.guild_id = guild_id

    @discord.ui.button(label="Join 📥", style=discord.ButtonStyle.green, custom_id="mafia_join")
    async def join_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            return await interaction.response.send_message("❌ You are already registered in the mafia game!", ephemeral=True)
        
        max_limit = 25 if is_user_premium(interaction.user.id, self.guild_id) else 15
        
        if len(self.players) >= max_limit:
            return await interaction.response.send_message(f"❌ Sorry, maximum limit reached (`{max_limit}` players)!", ephemeral=True)
        
        self.players.append(interaction.user)
        await interaction.response.send_message("✅ You have successfully registered for the mafia game!", ephemeral=True)

    @discord.ui.button(label="Leave 📤", style=discord.ButtonStyle.red, custom_id="mafia_leave")
    async def leave_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("❌ You are not registered!", ephemeral=True)
        
        self.players.remove(interaction.user)
        await interaction.response.send_message("✅ You have been removed from the registry.", ephemeral=True)

    @discord.ui.button(label="Start Game 🚀", style=discord.ButtonStyle.blurple, custom_id="mafia_start")
    async def start_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("❌ Only administrators can start the game!", ephemeral=True)
        if len(self.players) < 4:
            return await interaction.response.send_message("❌ There must be at least 4 players registered!", ephemeral=True)
        
        self.stop()
        mentions = ", ".join([p.mention for p in self.players])
        embed = discord.Embed(
            title="🎮 Mafia Game Started!",
            description=f"Participants ({len(self.players)}):\n{mentions}",
            color=COLOR
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ChairsView(discord.ui.View):
    def __init__(self, host, guild_id):
        super().__init__(timeout=120)
        self.players = []
        self.host = host
        self.guild_id = guild_id

    @discord.ui.button(label="Sit on Chair 🪑", style=discord.ButtonStyle.green, custom_id="chair_sit")
    async def sit_chair(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_limit = 30 if is_user_premium(interaction.user.id, self.guild_id) else 20
        if len(self.players) >= max_limit:
            return await interaction.response.send_message("❌ Sorry, max capacity reached!", ephemeral=True)

        if interaction.user not in self.players:
            self.players.append(interaction.user)
            await interaction.response.send_message("🏃‍♂️ You grabbed a chair!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You are already seated!", ephemeral=True)

# =========================================
# SUGGESTION VIEW
# =========================================

class SuggestionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.yes_voters = set()
        self.no_voters = set()

    @discord.ui.button(label="👍 Agree (0)", style=discord.ButtonStyle.green, custom_id="suggest_yes")
    async def vote_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.no_voters:
            self.no_voters.remove(uid)
        self.yes_voters.add(uid)
        button.label = f"👍 Agree ({len(self.yes_voters)})"
        self.children[1].label = f"👎 Disagree ({len(self.no_voters)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("✅ Vote recorded!", ephemeral=True)

    @discord.ui.button(label="👎 Disagree (0)", style=discord.ButtonStyle.red, custom_id="suggest_no")
    async def vote_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.yes_voters:
            self.yes_voters.remove(uid)
        self.no_voters.add(uid)
        self.children[0].label = f"👍 Agree ({len(self.yes_voters)})"
        button.label = f"👎 Disagree ({len(self.no_voters)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ Vote recorded!", ephemeral=True)

# =========================================
# HELP MENU INTERACTIVE
# =========================================

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="All member", description="Member commands, economy, and games", emoji="👥"),
            discord.SelectOption(label="Staff member", description="Administration and security commands", emoji="👑")
        ]
        super().__init__(placeholder="Select desired category", options=options, custom_id="help_select")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "All member":
            embed = discord.Embed(
                title="👥 All Member Commands",
                description="List of general commands, economy, XP, and games:",
                color=COLOR
            )
            embed.add_field(
                name="💰 Economy & General",
                value="""
#credit / c / !credit / /credit [member]
/daily (Claim daily reward 10k)
/tax <amount> (Calculate tax)
!xp / /xp | !level / /level
!t | !t day | !t week
!i [member] | !عضو | !افاتار | !سيرفر
!اقتراح <suggestion>
!mafia | !mafia_hint | !chairs
""",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=HelpView())

        elif self.values[0] == "Staff member":
            embed = discord.Embed(
                title="👑 Staff Member Commands",
                description="List of moderators, server management, and security:",
                color=COLOR
            )
            embed.add_field(
                name="🛡️ Moderation & Security",
                value="""
!تحذير @member | !لاتحذير @member | !سجل @member
!clear <number> / !مسح <number>
!قف | !فت
/ban | /unban
/timeout | /timeout_remove
/add_role | /remove_role
/badword | /badword_remove | /badword_list
/auto_reply | /auto_reply_remove | /auto_reply_list
/protection | /protection_remove | /protection_list
""",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=HelpView())

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())
        self.add_item(discord.ui.Button(label="Add Bot", emoji="🔗", url=BOT_INVITE, style=discord.ButtonStyle.link))
        self.add_item(discord.ui.Button(label="Support", emoji="💬", url=SUPPORT_INVITE, style=discord.ButtonStyle.link))

# =========================================
# BACKGROUND TASKS
# =========================================

async def check_expired_premiums():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            current_time = time.time()
            cur.execute("SELECT user_id, guild_id FROM premium_users WHERE expiry_time <= ?", (current_time,))
            rows = cur.fetchall()
            for uid, gid in rows:
                cur.execute("DELETE FROM premium_users WHERE user_id=? AND guild_id=?", (uid, gid))
                db.commit()
        except:
            pass
        await asyncio.sleep(60)

# =========================================
# BOT READY EVENT
# =========================================

@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(HelpView())
    bot.loop.create_task(check_expired_premiums())
    print(f"✅ Sayanzi Bot Logged in as {bot.user}")

# =========================================
# WELCOME EVENT
# =========================================

@bot.event
async def on_member_join(member):
    cur.execute("SELECT message FROM welcome_settings WHERE guild_id=?", (str(member.guild.id),))
    row = cur.fetchone()
    if not row:
        return
    
    msg_template = row[0]
    final_text = msg_template.replace("[user]", member.mention)

    if "[ing]" in final_text:
        final_text = final_text.replace("[ing]", "")
        try:
            avatar_bytes = await member.display_avatar.read()
            file = discord.File(io.BytesIO(avatar_bytes), filename="avatar.png")
            
            for channel in member.guild.text_channels:
                if "welcome" in channel.name or "ترحيب" in channel.name or channel.permissions_for(member.guild.me).send_messages:
                    embed = discord.Embed(description=final_text, color=COLOR)
                    embed.set_image(url="attachment://avatar.png")
                    await channel.send(embed=embed, file=file)
                    break
        except:
            pass
    else:
        for channel in member.guild.text_channels:
            if "welcome" in channel.name or "ترحيب" in channel.name or channel.permissions_for(member.guild.me).send_messages:
                embed = discord.Embed(description=final_text, color=COLOR)
                await channel.send(embed=embed)
                break

# =========================================
# MESSAGE EVENT (XP, AUTO REPLY, BADWORD, ANTI SPAM & LINKS, CREDIT PREFIX)
# =========================================

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    gid = str(message.guild.id)
    uid = str(message.author.id)

    # XP System
    cur.execute("SELECT * FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    if cur.fetchone():
        cur.execute("UPDATE xp SET messages=messages+1, day_count=day_count+1, week_count=week_count+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO xp VALUES(?,?,?,?,?)", (gid, uid, 1, 1, 1))
    db.commit()

    # Credit Text Commands: #credit, c, !credit (GLOBAL / مشترك بكل السيرفرات)
    content = message.content.strip()
    if content.startswith(("#credit", "c", "!credit")) or content == "c":
        parts = content.split()
        
        if len(parts) == 1 or (len(parts) == 2 and parts[1].startswith("<@")):
            target = message.mentions[0] if message.mentions else message.author
            t_uid = str(target.id)
            cur.execute("SELECT balance FROM economy WHERE user_id=?", (t_uid,))
            row = cur.fetchone()
            bal = row[0] if row else 0.0
            
            if len(parts) == 1 and not message.mentions:
                resp_text = f":bank: | **{message.author.name}, your account balance is `${bal:,.0f}`.**"
            else:
                resp_text = f"**{target.name} :credit_card: balance is `${bal:,.0f}`.**"
            return await message.channel.send(resp_text)
        
        elif len(parts) >= 3 and message.mentions:
            recipient = message.mentions[0]
            if recipient.id == message.author.id:
                return await message.channel.send("❌ You cannot transfer credits to yourself!")
            try:
                raw_amount = float(parts[2])
            except:
                return await message.channel.send("❌ Please enter a valid transfer amount!")
            
            if raw_amount <= 0:
                return await message.channel.send("❌ Amount must be greater than zero!")

            tax = 0
            net_amount = raw_amount - tax

            cur.execute("SELECT balance FROM economy WHERE user_id=?", (uid,))
            s_row = cur.fetchone()
            s_bal = s_row[0] if s_row else 0.0

            if s_bal < raw_amount:
                return await message.channel.send(f"❌ You do not have enough balance! Current balance: **`${s_bal:,.0f}`**")

            expected_code = str(random.randint(1000, 9999))
            
            transfer_msg = f"**{message.author.name}, Transfer Fees: `{tax}`, Amount :`${raw_amount:,.0f}`**\n **type these numbers to confirm : `{expected_code}`**"
            view = TransferConfirmView(message.author, recipient, raw_amount, tax, net_amount, expected_code)
            return await message.channel.send(transfer_msg, view=view)

    # Auto Reply
    for trigger, reply in auto_replies.items():
        if trigger in message.content.lower():
            embed = discord.Embed(description=reply, color=COLOR)
            await message.channel.send(embed=embed)

    # Badword Protection
    for word, sec in badword_words.items():
        if word in message.content.lower():
            try:
                await message.delete()
                await message.author.timeout(timedelta(seconds=sec))
                await message.channel.send(f"⛔ {message.author.mention} has been timed out for using forbidden words.")
            except:
                pass

    # Anti Links
    if "http://" in message.content.lower() or "https://" in message.content.lower():
        if not is_admin(message.author, message.guild):
            try:
                await message.delete()
                await message.channel.send(f"🚫 {message.author.mention} Links are not allowed in this server!")
            except:
                pass

    # Anti Spam
    key = (gid, uid)
    spam_cache[key] = spam_cache.get(key, []) + [time.time()]
    spam_cache[key] = [t for t in spam_cache[key] if time.time() - t < 3]

    if len(spam_cache[key]) >= 5:
        try:
            await message.author.timeout(timedelta(minutes=10), reason="Spamming")
            await message.channel.send(f"⏱ {message.author.mention} You have been timed out for spamming.")
        except:
            pass
        spam_cache[key] = []

    await bot.process_commands(message)

# =========================================
# ECONOMY & TAX SLASH COMMANDS (GLOBAL)
# =========================================

@bot.tree.command(name="credit", description="Check your balance or another member's balance")
async def slash_credit(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    uid = str(member.id)
    cur.execute("SELECT balance FROM economy WHERE user_id=?", (uid,))
    row = cur.fetchone()
    bal = row[0] if row else 0.0
    
    if member.id == interaction.user.id:
        resp_text = f":bank: | **{member.name}, your account balance is `${bal:,.0f}`.**"
    else:
        resp_text = f"**{member.name} :credit_card: balance is `${bal:,.0f}`.**"
    await interaction.response.send_message(resp_text)

@bot.tree.command(name="add_credit", description="Add balance to a specific member (Bot Owner only)")
@app_commands.describe(user="The user to add credit to", amount="Amount of credit to add")
async def slash_add_credit(interaction: discord.Interaction, user: discord.Member, amount: int):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ This command is exclusively for the Bot Owner!", ephemeral=True)
    
    uid = str(user.id)
    
    cur.execute("SELECT balance FROM economy WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE economy SET balance = balance + ? WHERE user_id=?", (float(amount), uid))
    else:
        cur.execute("INSERT INTO economy VALUES (?, ?, ?)", (uid, float(amount), 0.0))
    db.commit()
    
    await interaction.response.send_message(f"✅ Successfully added **{amount:,}** credits to {user.mention}!")

@bot.tree.command(name="daily", description="Claim your daily reward (10,000 credits)")
async def slash_daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    current_time = time.time()
    
    cur.execute("SELECT last_daily FROM economy WHERE user_id=?", (uid,))
    row = cur.fetchone()
    
    if row and current_time - row[0] < 86400:
        remaining = int(86400 - (current_time - row[0]))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return await interaction.response.send_message(f"⏳ You have already claimed your daily reward! You can claim again in `{hours} hours and {minutes} minutes`.", ephemeral=True)
    
    daily_amount = 10000.0
    if row:
        cur.execute("UPDATE economy SET balance = balance + ?, last_daily = ? WHERE user_id=?", (daily_amount, current_time, uid))
    else:
        cur.execute("INSERT INTO economy VALUES(?,?,?)", (uid, daily_amount, current_time))
    db.commit()
    
    embed = discord.Embed(description=f"🎁 **Daily reward deposited successfully!**\nYou received: **`${daily_amount:,.0f}`**", color=COLOR)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tax", description="Calculate transfer tax (5% rate)")
@app_commands.describe(amount="Amount to transfer")
async def slash_tax(interaction: discord.Interaction, amount: float):
    tax = amount * 0.05
    net = amount - tax
    transfer_amount = amount / 0.95
    
    embed = discord.Embed(title="🧮 Bot Tax Calculator", color=COLOR)
    embed.add_field(name="Requested Amount", value=f"`{amount:,.0f}`", inline=False)
    embed.add_field(name="Tax Fee (5%)", value=f"`{tax:,.0f}`", inline=False)
    embed.add_field(name="Net Amount Received", value=f"**`${net:,.0f}`**", inline=False)
    embed.add_field(name="Type this command to deliver exact amount", value=f"`!credit @user {transfer_amount:,.2f}`", inline=False)
    await interaction.response.send_message(embed=embed)

# =========================================
# WELCOME COMMAND (/welcom_join)
# =========================================

@bot.tree.command(name="welcom_join", description="Set custom welcome message with [user] and [ing]")
@app_commands.describe(message="Welcome message (use [user] for mention and [ing] for avatar)")
async def welcom_join(interaction: discord.Interaction, message: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack Administrator permissions.", ephemeral=True)
    
    gid = str(interaction.guild.id)
    cur.execute("INSERT OR REPLACE INTO welcome_settings VALUES (?, ?)", (gid, message))
    db.commit()
    
    embed = discord.Embed(title="✅ Welcome System Saved", description=f"**Saved Message:**\n{message}", color=COLOR)
    await interaction.response.send_message(embed=embed)

# =========================================
# GAMES COMMANDS (MAFIA, CHAIRS)
# =========================================

@bot.command(name="mafia")
async def mafia_game(ctx):
    view = MafiaView(ctx.guild.id)
    embed = discord.Embed(title="🕵️‍♂️ Mafia Game Registration", description="Click the **(Join 📥)** button below to participate.", color=COLOR)
    await ctx.send(embed=embed, view=view)

@bot.command(name="mafia_hint")
async def mafia_hint(ctx):
    if not is_user_premium(ctx.author.id, ctx.guild.id):
        return await ctx.send("❌ This feature is exclusively for Premium subscribers!")

    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    current_time = time.time()
    
    cur.execute("SELECT hints_count, last_reset FROM mafia_hints_usage WHERE user_id=? AND guild_id=?", (uid, gid))
    row = cur.fetchone()

    hints_allowed = 5
    if row:
        hints_count, last_reset = row
        if current_time - last_reset >= 86400:
            hints_count = 0
            last_reset = current_time
        if hints_count >= hints_allowed:
            return await ctx.send("❌ You have used all 5 of your allowed hints today!")
        hints_count += 1
        cur.execute("UPDATE mafia_hints_usage SET hints_count=?, last_reset=? WHERE user_id=? AND guild_id=?", (hints_count, last_reset, uid, gid))
    else:
        hints_count = 1
        cur.execute("INSERT INTO mafia_hints_usage VALUES (?, ?, ?, ?)", (uid, gid, hints_count, current_time))
    db.commit()

    hints_pool = [
        "💡 Mafia Hint: Watch out for contradicting statements; quiet members are often suspicious.",
        "💡 Mafia Hint: Blending into general discussions is a common tactic for culprits.",
        "💡 Mafia Hint: In advanced rounds, focusing on the last person's actions reveals a lot."
    ]
    embed = discord.Embed(title="🕵️‍♂️ Mafia Hint", description=f"{random.choice(hints_pool)}\n\n*Remaining hints today: **{hints_allowed - hints_count}***", color=COLOR)
    await ctx.send(embed=embed)

@bot.command(name="chairs")
async def chairs_game(ctx):
    view = ChairsView(ctx.author, ctx.guild.id)
    embed = discord.Embed(title="🪑 Musical Chairs Game", description="Click the **(Sit on Chair 🪑)** button to join!", color=COLOR)
    await ctx.send(embed=embed, view=view)
    
    await asyncio.sleep(15)
    view.stop()
    players = view.players
    if len(players) < 2:
        return await ctx.send("❌ Too few participants!")

    while len(players) > 1:
        await asyncio.sleep(5)
        loser = random.choice(players)
        players.remove(loser)
        await ctx.send(f"❌ Eliminated: {loser.mention} | Remaining: `{len(players)}`")
    await ctx.send(f"🏆 Musical Chairs Champion: {players[0].mention} 🎉")

# =========================================
# SUGGESTION COMMAND
# =========================================

@bot.command(name="اقتراح")
async def suggestion_command(ctx, *, text: str = None):
    if not text:
        return await ctx.send("❌ Please write your suggestion next to the command!")
    embed = discord.Embed(title="💡 New Suggestion", description=f"**Author:** {ctx.author.mention}\n\n{text}", color=COLOR)
    view = SuggestionView()
    await ctx.message.delete()
    await ctx.send(embed=embed, view=view)

# =========================================
# BROADCAST COMMANDS (/send_all & /send_online) [OWNER ONLY] - [3.5s Delay]
# =========================================

@bot.tree.command(name="send_all", description="Broadcast message to all members in the server (Bot Owner only)")
@app_commands.describe(text="Message content to broadcast")
async def send_all(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ This command is exclusively for the Bot Owner!", ephemeral=True)
    
    await interaction.response.send_message("🚀 Broadcasting message to all members...", ephemeral=True)
    
    success_count = 0
    fail_count = 0
    
    for member in interaction.guild.members:
        if member.bot:
            continue
        try:
            await member.send(text)
            success_count += 1
            await asyncio.sleep(3.5)
        except:
            fail_count += 1
            
    await interaction.followup.send(f"✅ Broadcast complete! Sent: `{success_count}` | Failed: `{fail_count}`", ephemeral=True)

@bot.tree.command(name="send_online", description="Broadcast message to online members only (Bot Owner only)")
@app_commands.describe(text="Message content to broadcast")
async def send_online(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ This command is exclusively for the Bot Owner!", ephemeral=True)
    
    await interaction.response.send_message("🚀 Broadcasting message to online members...", ephemeral=True)
    
    success_count = 0
    fail_count = 0
    
    for member in interaction.guild.members:
        if member.bot or member.status == discord.Status.offline:
            continue
        try:
            await member.send(text)
            success_count += 1
            await asyncio.sleep(3.5)
        except:
            fail_count += 1
            
    await interaction.followup.send(f"✅ Broadcast complete! Sent: `{success_count}` | Failed: `{fail_count}`", ephemeral=True)

# =========================================
# PROTECTION SYSTEM SLASH COMMANDS
# =========================================

@bot.tree.command(name="protection", description="Add or configure protection settings")
@app_commands.describe(feature="Protection feature name (e.g., antilinks, antispam)", status="Enable or disable")
@app_commands.choices(status=[
    app_commands.Choice(name="Enable", value="enable"),
    app_commands.Choice(name="Disable", value="disable")
])
async def protection_config(interaction: discord.Interaction, feature: str, status: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack Administrator permissions.", ephemeral=True)
    await interaction.response.send_message(f"✅ Protection feature `{feature}` has been set to `{status}`.", ephemeral=True)

@bot.tree.command(name="protection_remove", description="Remove a protection rule or configuration")
@app_commands.describe(feature="Protection feature name")
async def protection_remove(interaction: discord.Interaction, feature: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack Administrator permissions.", ephemeral=True)
    await interaction.response.send_message(f"✅ Protection rule `{feature}` removed successfully.", ephemeral=True)

@bot.tree.command(name="protection_list", description="View active protection configurations")
async def protection_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack Administrator permissions.", ephemeral=True)
    
    embed = discord.Embed(title="🛡️ Server Protection Status", color=COLOR)
    embed.add_field(name="Anti Links", value="`Active`", inline=True)
    embed.add_field(name="Anti Spam", value="`Active`", inline=True)
    embed.add_field(name="Banned Words", value=f"`{len(badword_words)} words`", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =========================================
# HELP & LARGE BILINGUAL COMMANDS MENU (/commands) - [WITHOUT OWNER COMMANDS]
# =========================================

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="Sayanzi bot", description="Access all essential bot commands from here.", color=COLOR)
    await ctx.send(embed=embed, view=HelpView())

@bot.tree.command(name="commands", description="Display Sayanzi bot commands menu / عرض أوامر بوت سايانزي")
async def commands_list(interaction: discord.Interaction):
    large_commands_text = """```text
==================================================
        🤖 SAYANZI BOT COMMANDS / أوامر بوت سايانزي
==================================================

👥 ALL MEMBER COMMANDS (أوامر الأعضاء):
  • #credit / c / !credit - Check balance / فحص الرصيد
  • /credit [member] - Check balance via slash / فحص رصيد (سلاش)
  • /daily - Claim daily reward 10k / استلام الراتب اليومي
  • /tax <amount> - Calculate transfer fees / حساب الضريبة
  • !xp / /xp - Check XP points / فحص نقاط الخبرة
  • !level / /level - Check current level / فحص المستوى الحالي
  • !t / !t day / !t week - Leaderboard rankings / لوحة الترتيب
  • !i [member] - Detailed profile info / عرض الملف الشخصي
  • !عضو - Quick member info / معلومات العضو السريعة
  • !افاتار - View avatar / عرض صورة الحساب
  • !سيرفر - Server information / معلومات السيرفر
  • !اقتراح <text> - Create suggestion / طرح اقتراح مع أزرار
  • !mafia - Join mafia game / الانضمام للمافيا
  • !mafia_hint - Mafia hint (Premium) / تلميح المافيا (بريميوم)
  • !chairs - Musical chairs game / لعبة الكراسي

👑 STAFF MEMBER COMMANDS (أوامر الإدارة):
  • !تحذير @member - Warn member / تحذير عضو
  • !لاتحذير @member - Remove warning / إزالة تحذير
  • !سجل @member - View warning records / سجل التحذيرات
  • !clear <number> / !مسح <number> - Purge messages / مسح الرسائل
  • !قف - Lock channel / قفل الشات
  • !فت - Unlock channel / فتح الشات
  • /ban - Ban member / حظر عضو
  • /unban - Unban user by ID / إلغاء حظر بالآيدي
  • /timeout - Timeout member / إعطاء تايم لعضو
  • /timeout_remove - Remove timeout / إزالة التايم
  • /add_role - Add role / إضافة رتبة
  • /remove_role - Remove role / إزالة رتبة
  • /protection - Configure protection / إعدادات الحماية
  • /protection_remove - Remove protection rule / إزالة قاعدة حماية
  • /protection_list - View protection rules / عرض قائمة الحماية
  • /badword - Banned protection word / إضافة كلمة محظورة
  • /badword_remove - Remove banned word / إزالة كلمة محظورة
  • /badword_list - Banned words list / قائمة الكلمات المحظورة
  • /auto_reply - Automatic word reply / إضافة رد تلقائي
  • /auto_reply_remove - Remove auto-reply / إزالة رد تلقائي
  • /auto_reply_list - Auto-replies list / قائمة الردود التلقائية
  • /welcom_join - Set welcome message / ضبط رسالة الترحيب

==================================================
```"""
    await interaction.response.send_message(large_commands_text, ephemeral=True)

# =========================================
# XP, LEVEL, TOP, PROFILE, INFO COMMANDS
# =========================================

@bot.command()
async def xp(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))

@bot.tree.command(name="xp", description="Check your XP points")
async def slash_xp(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    await interaction.response.send_message(embed=discord.Embed(title="⭐ XP", description=f"```{row[0] if row else 0}```", color=COLOR))

@bot.command()
async def level(ctx):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    amt = row[0] if row else 0
    await ctx.send(embed=discord.Embed(title="📊 LEVEL", description=f"```{amt // 50}```", color=COLOR))

@bot.tree.command(name="level", description="Check your current level")
async def slash_level(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    uid = str(interaction.user.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, uid))
    row = cur.fetchone()
    amt = row[0] if row else 0
    await interaction.response.send_message(embed=discord.Embed(title="📊 LEVEL", description=f"```{amt // 50}```", color=COLOR))

@bot.command(name="t")
async def top_command(ctx, mode=None):
    gid = str(ctx.guild.id)
    col, title = "messages", "Months Top"
    if mode == "day":
        col, title = "day_count", "Top Day"
    elif mode == "week":
        col, title = "week_count", "Top Week"
    cur.execute(f"SELECT user_id, {col} FROM xp WHERE guild_id=? ORDER BY {col} DESC LIMIT 10", (gid,))
    embed = discord.Embed(title=f"🏆 {title}", color=COLOR)
    for i, (uid, cnt) in enumerate(cur.fetchall(), start=1):
        embed.add_field(name=f"{i}. <@{uid}>", value=f"💬 {cnt} points", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="i")
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    gid = str(ctx.guild.id)
    cur.execute("SELECT messages FROM xp WHERE guild_id=? AND user_id=?", (gid, str(member.id)))
    row = cur.fetchone()
    msgs = row[0] if row else 0
    
    created_at = member.created_at.strftime("%Y-%m-%d")
    joined_at = member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown"
    
    embed = discord.Embed(title=f"Profile: {member.name}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏷️ Name", value=f"`{member}`", inline=False)
    embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="📅 Account Created", value=f"`{created_at}`", inline=True)
    embed.add_field(name="📥 Server Joined", value=f"`{joined_at}`", inline=True)
    embed.add_field(name="👑 Highest Role", value=member.top_role.mention, inline=False)
    embed.add_field(name="📊 Level / XP", value=f"Level: `{msgs // 50}` | Points: `{msgs}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="افاتار")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar: {member.name}", color=COLOR)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="عضو")
async def member_info(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Member Info: {member}", color=COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👑 Highest Role", value=member.top_role.mention)
    embed.add_field(name="🆔 ID", value=f"`{member.id}`")
    await ctx.send(embed=embed)

@bot.command(name="سيرفر", aliases=["server"])
async def server_info(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"🖥 Server Info: {guild.name}", color=COLOR)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 Members", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="👑 Owner", value=f"{guild.owner.mention}", inline=True)
    await ctx.send(embed=embed)

# =========================================
# MODERATION COMMANDS (Text)
# =========================================

@bot.command(name="تحذير")
async def warn(ctx, member: discord.Member):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ You lack permissions!")
    gid = str(ctx.guild.id)
    uid = str(member.id)
    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (gid, uid))
    if cur.fetchone():
        cur.execute("UPDATE warns SET warns=warns+1 WHERE guild_id=? AND user_id=?", (gid, uid))
    else:
        cur.execute("INSERT INTO warns VALUES(?,?,?)", (gid, uid, 1))
    db.commit()
    await ctx.send(f"⚠ {member.mention} has been warned.")

@bot.command(name="لاتحذير")
async def unwarn(ctx, member: discord.Member):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ You lack permissions!")
    cur.execute("UPDATE warns SET warns = CASE WHEN warns > 0 THEN warns - 1 ELSE 0 END WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    db.commit()
    await ctx.send(f"✅ Warning removed from {member.mention}.")

@bot.command(name="سجل")
async def records_command(ctx, member: discord.Member = None):
    member = member or ctx.author
    cur.execute("SELECT warns FROM warns WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
    row = cur.fetchone()
    await ctx.send(embed=discord.Embed(title=f"📋 Records for {member.name}", description=f"⚠️ Warnings: `{row[0] if row else 0}`", color=COLOR))

@bot.command(name="clear", aliases=["مسح"])
async def clear(ctx, amount: int):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ You lack permissions!")
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Cleared `{amount}` messages.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except:
        pass

@bot.command(name="قف")
async def lock(ctx):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ You lack permissions!")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Channel locked.")

@bot.command(name="فت")
async def unlock(ctx):
    if not is_admin(ctx.author, ctx.guild):
        return await ctx.send("❌ You lack permissions!")
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Channel unlocked.")

# =========================================
# ADMIN SLASH COMMANDS
# =========================================

@bot.tree.command(name="ban", description="Ban a member from the server")
async def ban(interaction: discord.Interaction, member: discord.Member):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.ban()
    await interaction.response.send_message("✅ Member banned successfully.")

@bot.tree.command(name="unban", description="Unban a user by their ID")
async def unban(interaction: discord.Interaction, user_id: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message("✅ User unbanned.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error:\n`{e}`", ephemeral=True)

@bot.tree.command(name="timeout", description="Timeout a member for a specified duration")
async def timeout(interaction: discord.Interaction, member: discord.Member, time: str):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message("❌ Invalid time format (e.g., 10m, 1h)", ephemeral=True)
    await member.timeout(timedelta(seconds=secs))
    await interaction.response.send_message("✅ Timeout applied successfully.")

@bot.tree.command(name="timeout_remove", description="Remove timeout from a member")
async def timeout_remove(interaction: discord.Interaction, member: discord.Member):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.timeout(None)
    await interaction.response.send_message("✅ Timeout removed.")

@bot.tree.command(name="add_role", description="Add a role to a member")
async def add_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ Added role to {member.mention}.")

@bot.tree.command(name="remove_role", description="Remove a role from a member")
async def remove_role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not await check_admin_and_hierarchy(interaction, member):
        return
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ Removed role from {member.mention}.")

# =========================================
# BADWORD & AUTO-REPLY COMMANDS
# =========================================

@bot.tree.command(name="badword", description="Add a banned protection word with timeout duration")
@app_commands.describe(word="Forbidden word", time="Timeout duration like 10s or 5m")
async def badword(interaction: discord.Interaction, word: str, time: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    secs = parse_time(time)
    if not secs:
        return await interaction.response.send_message("❌ Invalid time format", ephemeral=True)
    badword_words[word.lower()] = secs
    await interaction.response.send_message(f"✅ Added `{word}` to forbidden words list.", ephemeral=True)

@bot.tree.command(name="badword_remove", description="Remove a word from protection list")
async def badword_remove(interaction: discord.Interaction, word: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    if word.lower() in badword_words:
        del badword_words[word.lower()]
        await interaction.response.send_message(f"✅ Removed `{word}`.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Word not found.", ephemeral=True)

@bot.tree.command(name="badword_list", description="View banned words list")
async def badword_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    if not badword_words:
        return await interaction.response.send_message("📋 Banned words list is empty.", ephemeral=True)
    lst = "\n".join([f"• `{w}` ({s}s)" for w, s in badword_words.items()])
    await interaction.response.send_message(embed=discord.Embed(title="🛡️ Banned Words", description=lst, color=COLOR), ephemeral=True)

@bot.tree.command(name="auto_reply", description="Add an automatic word reply")
async def auto_reply(interaction: discord.Interaction, trigger: str, reply: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    auto_replies[trigger.lower()] = reply
    await interaction.response.send_message(f"✅ Added auto-reply for `{trigger}`.", ephemeral=True)

@bot.tree.command(name="auto_reply_remove", description="Remove an automatic reply")
async def auto_reply_remove(interaction: discord.Interaction, trigger: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    if trigger.lower() in auto_replies:
        del auto_replies[trigger.lower()]
        await interaction.response.send_message("✅ Deleted successfully.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Not found.", ephemeral=True)

@bot.tree.command(name="auto_reply_list", description="View automatic replies list")
async def auto_reply_list(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("❌ You lack permissions.", ephemeral=True)
    if not auto_replies:
        return await interaction.response.send_message("📋 Auto-replies list is empty.", ephemeral=True)
    lst = "\n".join([f"• **{t}** ➔ `{r}`" for t, r in auto_replies.items()])
    await interaction.response.send_message(embed=discord.Embed(title="💬 Auto Replies", description=lst, color=COLOR), ephemeral=True)

# =========================================
# RUN BOT
# =========================================

bot.run(TOKEN)

