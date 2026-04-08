import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import uuid
from datetime import datetime
import re

# ============================================================
# DATABASE STORAGE (MongoDB)
# ============================================================

from pymongo import MongoClient

mongo_uri = os.environ.get("MONGODB_URI")
db_client = MongoClient(mongo_uri) if mongo_uri else None
db = db_client["pc_checker"] if db_client is not None else None
guilds_collection = db["guilds"] if db is not None else None
checks_collection = db["checks"] if db is not None else None
pending_agreements = db["pending_agreements"] if db is not None else None

# ============================================================
# DATA STORAGE FUNCTIONS (MongoDB)
# ============================================================

def get_default_guild_config():
    return {
        "webhook_url": "",
        "download_url": "",
        "pc_check_channel_id": 0,
        "log_channel_id": 0,
        "staff_role_id": 0,
        "approved_role_id": 0,
        "rejected_role_id": 0,
        "pending_role_id": 0,
    }

def get_guild_config(guild_id: str) -> dict:
    """Get guild config from database, create default if not exists."""
    if guilds_collection is None:
        return get_default_guild_config()

    guild_id_str = str(guild_id)
    guild_doc = guilds_collection.find_one({"_id": guild_id_str})

    if not guild_doc:
        # Create default config for new guild
        config = get_default_guild_config()
        guilds_collection.insert_one({
            "_id": guild_id_str,
            "name": "Unknown Server",
            "config": config,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        return config

    return guild_doc.get("config", get_default_guild_config())

def update_guild_config(guild_id: str, config_updates: dict):
    """Update guild config in database."""
    if guilds_collection is None:
        return

    guild_id_str = str(guild_id)
    guilds_collection.update_one(
        {"_id": guild_id_str},
        {
            "$set": {
                "config": config_updates,
                "updated_at": datetime.now().isoformat(),
            }
        },
        upsert=True
    )

def create_check(check_data: dict) -> dict:
    """Create a new pending check in database."""
    if checks_collection is None:
        return check_data

    checks_collection.insert_one(check_data)
    return check_data

def get_check(check_id: str) -> dict:
    """Get a check by check_id."""
    if checks_collection is None:
        return None

    try:
        return checks_collection.find_one({"_id": check_id})
    except Exception as e:
        print(f"Error finding check {check_id}: {e}")
        return None

def update_check(check_id: str, updates: dict):
    """Update a check in database."""
    if checks_collection is None:
        return

    try:
        checks_collection.update_one(
            {"_id": check_id},
            {"$set": updates}
        )
    except Exception as e:
        print(f"Error updating check: {e}")

def get_user_checks(guild_id: str, user_id: str) -> list:
    """Get all checks for a user in a guild."""
    if checks_collection is None:
        return []

    cursor = checks_collection.find({
        "guild_id": str(guild_id),
        "user_id": str(user_id)
    }).sort("created_at", -1)

    return list(cursor)

def load_config():
    """Legacy function - redirects to default config."""
    return get_default_guild_config()

def save_config(config):
    """Legacy function - configs are now per-guild."""
    pass

def load_requests():
    """Legacy function - returns empty dict."""
    return {}

def save_requests(requests):
    """Legacy function - no-op."""
    pass

def load_check_data():
    """Legacy function - returns empty dict."""
    return {}

def save_check_data(data):
    """Legacy function - no-op."""
    pass

def get_config():
    """Legacy function - returns default config."""
    return get_default_guild_config()

# ============================================================
# EMOJIS
# ============================================================

APPROVE_EMOJI = "✅"
REJECT_EMOJI = "❌"
MORE_INFO_EMOJI = "🔍"
PENDING_EMOJI = "⏳"
CONFIG_EMOJI = "⚙️"
CHECK_EMOJI = "🔍"

# ============================================================
# DISCORD UI - CONFIGURATION PANEL
# ============================================================

class ConfigView(discord.ui.View):
    """View for configuration management."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="PC Check Channel", style=discord.ButtonStyle.secondary, emoji="📁", custom_id="cfg_pc_channel")
    async def cfg_pc_channel(self, interaction, button):
        await interaction.response.send_message(
            "Select PC Check Channel:",
            view=ChannelSelectView(self.bot, "pc_check_channel_id", interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="Log Channel", style=discord.ButtonStyle.secondary, emoji="📝", custom_id="cfg_log_channel")
    async def cfg_log_channel(self, interaction, button):
        await interaction.response.send_message(
            "Select Log Channel:",
            view=ChannelSelectView(self.bot, "log_channel_id", interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="Staff Role", style=discord.ButtonStyle.secondary, emoji="👮", custom_id="cfg_staff_role")
    async def cfg_staff_role(self, interaction, button):
        await interaction.response.send_message(
            "Select Staff Role:",
            view=RoleSelectView(self.bot, "staff_role_id", interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="Approved Role", style=discord.ButtonStyle.success, emoji="✅", custom_id="cfg_approved_role")
    async def cfg_approved_role(self, interaction, button):
        await interaction.response.send_message(
            "Select Approved Role:",
            view=RoleSelectView(self.bot, "approved_role_id", interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="Rejected Role", style=discord.ButtonStyle.danger, emoji="❌", custom_id="cfg_rejected_role")
    async def cfg_rejected_role(self, interaction, button):
        await interaction.response.send_message(
            "Select Rejected Role:",
            view=RoleSelectView(self.bot, "rejected_role_id", interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="Pending Role", style=discord.ButtonStyle.secondary, emoji="⏳", custom_id="cfg_pending_role")
    async def cfg_pending_role(self, interaction, button):
        await interaction.response.send_message(
            "Select Pending Role:",
            view=RoleSelectView(self.bot, "pending_role_id", interaction.guild),
            ephemeral=True
        )

    @discord.ui.button(label="Show Current Config", style=discord.ButtonStyle.primary, emoji="📋", custom_id="cfg_show_config")
    async def cfg_show_config(self, interaction, button):
        config = get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title="Current Configuration",
            color=discord.Color.blue()
        )

        pc_channel = self.bot.get_channel(config.get("pc_check_channel_id", 0))
        log_channel = self.bot.get_channel(config.get("log_channel_id", 0))
        staff_role = interaction.guild.get_role(config.get("staff_role_id", 0))
        approved_role = interaction.guild.get_role(config.get("approved_role_id", 0))
        rejected_role = interaction.guild.get_role(config.get("rejected_role_id", 0))
        pending_role = interaction.guild.get_role(config.get("pending_role_id", 0))

        embed.add_field(name="PC Check Channel", value=pc_channel.mention if pc_channel else "Not Set", inline=True)
        embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not Set", inline=True)
        embed.add_field(name="Staff Role", value=staff_role.mention if staff_role else "Not Set", inline=True)
        embed.add_field(name="Approved Role", value=approved_role.mention if approved_role else "Not Set", inline=True)
        embed.add_field(name="Rejected Role", value=rejected_role.mention if rejected_role else "Not Set", inline=True)
        embed.add_field(name="Pending Role", value=pending_role.mention if pending_role else "Not Set", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class ConfigModal(discord.ui.Modal):
    def __init__(self, bot, key, title, placeholder, is_password=False, is_list=False):
        super().__init__(title=title)
        self.bot = bot
        self.key = key
        self.is_list = is_list

        self.input = discord.ui.TextInput(
            label=title,
            placeholder=placeholder,
            required=True,
            style=discord.TextStyle.long
        )
        if is_password:
            self.input.style = discord.TextStyle.short
        self.add_item(self.input)

    async def callback(self, interaction):
        config = get_guild_config(interaction.guild.id)

        if self.is_list:
            value = [v.strip().lower() for v in self.input.value.split(",") if v.strip()]
            config[self.key] = value
            display_value = ", ".join(value)
        else:
            value = self.input.value.strip()
            if self.key in ["pc_check_channel_id", "log_channel_id", "staff_role_id", "approved_role_id", "rejected_role_id", "pending_role_id"]:
                match = re.match(r'<#(\d+)>', value) or re.match(r'<@&(\d+)>', value) or re.match(r'<@(\d+)>', value)
                if match:
                    value = int(match.group(1))
                else:
                    value = int(value) if value.isdigit() else 0
            config[self.key] = value
            display_value = value

        update_guild_config(interaction.guild.id, config)
        await interaction.response.send_message(
            f"✅ Updated `{self.key}`",
            ephemeral=True
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, bot, config_key, guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.config_key = config_key

        # Get text channels
        channels = guild.text_channels if guild else []

        options = [
            discord.SelectOption(label=c.name, value=str(c.id))
            for c in channels[:25]
        ]

        if options:
            select = discord.ui.Select(placeholder="Select a channel...", options=options, custom_id="channel_select")
            async def callback(interaction):
                config = get_guild_config(interaction.guild.id)
                channel_id = int(interaction.data['values'][0])
                config[self.config_key] = channel_id
                update_guild_config(interaction.guild.id, config)
                channel = self.bot.get_channel(channel_id)
                await interaction.response.send_message(
                    f"✅ Set to #{channel.name}" if channel else f"✅ Set to ID: {channel_id}",
                    ephemeral=True
                )
            select.callback = callback
            self.add_item(select)


class RoleSelectView(discord.ui.View):
    def __init__(self, bot, config_key, guild):
        super().__init__(timeout=60)
        self.bot = bot
        self.config_key = config_key

        # Get roles (excluding @everyone)
        roles = [r for r in guild.roles if r.name != "@everyone"] if guild else []

        options = [
            discord.SelectOption(label=r.name, value=str(r.id))
            for r in roles[:25]
        ]

        if options:
            select = discord.ui.Select(placeholder="Select a role...", options=options, custom_id="role_select")
            async def callback(interaction):
                config = get_guild_config(interaction.guild.id)
                role_id = int(interaction.data['values'][0])
                config[self.config_key] = role_id
                update_guild_config(interaction.guild.id, config)
                role = interaction.guild.get_role(role_id)
                await interaction.response.send_message(
                    f"✅ Set to @{role.name}" if role else f"✅ Set to ID: {role_id}",
                    ephemeral=True
                )
            select.callback = callback
            self.add_item(select)

class ConfigChannelModal(discord.ui.Modal):
    def __init__(self, bot, key, title):
        super().__init__(title=title)
        self.bot = bot
        self.key = key

        self.input = discord.ui.TextInput(
            label="Channel ID or Mention",
            placeholder="#channel-name or Channel ID",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.input)

    async def callback(self, interaction):
        config = get_guild_config(interaction.guild.id)
        value = self.input.value.strip()

        # Extract channel ID from mention
        match = re.match(r'<#(\d+)>', value)
        if match:
            value = int(match.group(1))
        else:
            value = int(value) if value.isdigit() else 0

        config[self.key] = value
        update_guild_config(interaction.guild.id, config)

        channel = self.bot.get_channel(value)
        channel_name = channel.name if channel else f"ID: {value}"

        await interaction.response.send_message(
            f"✅ Updated `{self.key}` to: #{channel_name}",
            ephemeral=True
        )

class ConfigRoleModal(discord.ui.Modal):
    def __init__(self, bot, key, title):
        super().__init__(title=title)
        self.bot = bot
        self.key = key

        self.input = discord.ui.TextInput(
            label="Role ID or Mention",
            placeholder="@RoleName or Role ID",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.input)

    async def callback(self, interaction):
        config = get_guild_config(interaction.guild.id)
        value = self.input.value.strip()

        # Extract role ID from mention
        match = re.match(r'<@&(\d+)>', value)
        if match:
            value = int(match.group(1))
        else:
            value = int(value) if value.isdigit() else 0

        config[self.key] = value
        update_guild_config(interaction.guild.id, config)

        # Find the role in guild
        role = interaction.guild.get_role(value) if interaction.guild else None
        role_name = role.name if role else f"ID: {value}"

        await interaction.response.send_message(
            f"✅ Updated `{self.key}` to: @{role_name}",
            ephemeral=True
        )

class ConfigStatusView(discord.ui.View):
    """Show current configuration status."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Show Current Config", style=discord.ButtonStyle.primary, emoji="📋", custom_id="show_config")
    async def show_config(self, interaction, button):
        config = get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title="⚙️ PC Check Bot Configuration",
            color=discord.Color.blue()
        )

        webhook = config.get("webhook_url", "")
        embed.add_field(
            name="🔗 Webhook URL",
            value=f"`{webhook[:30]}...`" if webhook else "❌ Not Set",
            inline=True
        )

        # Channels
        pc_channel = bot.get_channel(config.get("pc_check_channel_id", 0))
        log_channel = bot.get_channel(config.get("log_channel_id", 0))

        embed.add_field(
            name="📁 PC Check Channel",
            value=f"{pc_channel.mention}" if pc_channel else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="📝 Log Channel",
            value=f"{log_channel.mention}" if log_channel else "❌ Not Set",
            inline=True
        )

        # Roles
        staff_role = interaction.guild.get_role(config.get("staff_role_id", 0))

        embed.add_field(
            name="👮 Staff Role",
            value=f"{staff_role.mention}" if staff_role else "❌ Not Set",
            inline=True
        )

        # Additional roles
        approved_role = interaction.guild.get_role(config.get("approved_role_id", 0))
        rejected_role = interaction.guild.get_role(config.get("rejected_role_id", 0))
        pending_role = interaction.guild.get_role(config.get("pending_role_id", 0))

        embed.add_field(
            name="✅ Approved Role",
            value=f"{approved_role.mention}" if approved_role else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="❌ Rejected Role",
            value=f"{rejected_role.mention}" if rejected_role else "❌ Not Set",
            inline=True
        )

        embed.add_field(
            name="⏳ Pending Role",
            value=f"{pending_role.mention}" if pending_role else "❌ Not Set",
            inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
# PC CHECK ACTION BUTTONS
# ============================================================

class PCCheckActionView(discord.ui.View):
    """Buttons for staff to approve/reject PC checks."""

    def __init__(self, check_id: str):
        super().__init__(timeout=None)
        self.check_id = check_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji=APPROVE_EMOJI, custom_id=f"pccheck_approve")
    async def approve(self, interaction, button):
        await handle_check_action(interaction, self.check_id, "APPROVED")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji=REJECT_EMOJI, custom_id=f"pccheck_reject")
    async def reject(self, interaction, button):
        await handle_check_action(interaction, self.check_id, "REJECTED")

    @discord.ui.button(label="Request Info", style=discord.ButtonStyle.secondary, emoji=MORE_INFO_EMOJI, custom_id=f"pccheck_moreinfo")
    async def more_info(self, interaction, button):
        await handle_check_action(interaction, self.check_id, "NEEDS_INFO")

async def handle_check_action(interaction, check_id: str, new_status: str):
    """Handle approve/reject/moreinfo button clicks."""

    config = get_guild_config(interaction.guild.id)

    # Check permissions
    user = interaction.user
    staff_role_id = config.get("staff_role_id", 0)

    has_permission = False
    if user.guild_permissions.manage_messages:
        has_permission = True
    elif staff_role_id and any(role.id == staff_role_id for role in user.roles):
        has_permission = True

    if not has_permission:
        await interaction.response.send_message(
            "❌ You don't have permission to review PC checks.",
            ephemeral=True
        )
        return

    # Load check data from database
    check_data = get_check(check_id)

    if not check_data:
        await interaction.response.send_message(
            "❌ Check not found. It may have already been processed.",
            ephemeral=True
        )
        return

    # Update status in database
    update_check(check_id, {
        "status": new_status,
        "processed_by": str(interaction.user.id),
        "processed_at": datetime.now().isoformat(),
    })

    # Update user's roles if configured
    user_id = check_data.get("user_id")
    member = interaction.guild.get_member(int(user_id)) if user_id else None
    if member:
        try:
            approved_role_id = config.get("approved_role_id", 0)
            rejected_role_id = config.get("rejected_role_id", 0)
            pending_role_id = config.get("pending_role_id", 0)

            # Remove pending role
            if pending_role_id:
                pending_role = interaction.guild.get_role(pending_role_id)
                if pending_role and pending_role in member.roles:
                    await member.remove_roles(pending_role)

            # Handle new status
            if new_status == "APPROVED" and approved_role_id:
                approved_role = interaction.guild.get_role(approved_role_id)
                if approved_role:
                    await member.add_roles(approved_role)
                    # Remove rejected if they had it
                    if rejected_role_id:
                        rejected_role = interaction.guild.get_role(rejected_role_id)
                        if rejected_role and rejected_role in member.roles:
                            await member.remove_roles(rejected_role)

            elif new_status == "REJECTED" and rejected_role_id:
                rejected_role = interaction.guild.get_role(rejected_role_id)
                if rejected_role:
                    await member.add_roles(rejected_role)
                    # Remove approved if they had it
                    if approved_role_id:
                        approved_role = interaction.guild.get_role(approved_role_id)
                        if approved_role and approved_role in member.roles:
                            await member.remove_roles(approved_role)
        except Exception as e:
            print(f"Error updating roles: {e}")

    # Update the message
    check_data["status"] = new_status
    embed = create_pc_check_embed(check_data)

    # Update view based on status
    view = None
    if new_status in ["APPROVED", "REJECTED"]:
        view = None  # Hide buttons
    else:
        view = PCCheckActionView(check_id)

    try:
        await interaction.message.edit(embed=embed, view=view)
    except:
        pass

    # Confirmation message
    status_emoji = {"APPROVED": "✅", "REJECTED": "❌", "NEEDS_INFO": "🔍"}
    await interaction.response.send_message(
        f"{status_emoji.get(new_status, '⚠️')} Check {new_status.replace('_', ' ')}!",
        ephemeral=True
    )

    # Send to log channel
    log_channel_id = config.get("log_channel_id", 0)
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(
                title=f"PC Check {new_status.replace('_', ' ')}",
                color=discord.Color.green() if new_status == "APPROVED" else discord.Color.red(),
                timestamp=datetime.now()
            )
            log_embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
            log_embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Check ID", value=check_id, inline=True)
            if check_data.get("hostname"):
                log_embed.add_field(name="Hostname", value=check_data["hostname"], inline=True)
            if check_data.get("username"):
                log_embed.add_field(name="Username", value=check_data["username"], inline=True)

            await log_channel.send(embed=log_embed)

# ============================================================
# EMBED CREATION
# ============================================================

def get_status_color(status: str) -> discord.Color:
    colors = {
        "PENDING": discord.Color.blue(),
        "APPROVED": discord.Color.green(),
        "REJECTED": discord.Color.red(),
        "NEEDS_INFO": discord.Color.orange(),
    }
    return colors.get(status, discord.Color.greyple())

def get_status_emoji(status: str) -> str:
    emojis = {
        "PENDING": PENDING_EMOJI,
        "APPROVED": APPROVE_EMOJI,
        "REJECTED": REJECT_EMOJI,
        "NEEDS_INFO": MORE_INFO_EMOJI,
    }
    return emojis.get(status, "❓")

def create_pc_check_embed(data: dict) -> discord.Embed:
    """Create an embed showing PC check results."""
    status = data.get("status", "PENDING")

    embed = discord.Embed(
        title=f"PC Verification Check",
        color=get_status_color(status),
        timestamp=datetime.now()
    )

    # User info
    user_id = data.get("user_id", "Unknown")
    embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
    embed.add_field(name="Discord ID", value=user_id, inline=True)
    embed.add_field(name="Check ID", value=data.get("check_id", "N/A"), inline=True)

    # Status
    status_emoji = get_status_emoji(status)
    embed.add_field(
        name="Status",
        value=f"{status_emoji} **{status.replace('_', ' ').title()}**",
        inline=True
    )

    # System info
    embed.add_field(name="Hostname", value=data.get("hostname", "N/A"), inline=True)
    embed.add_field(name="Username", value=data.get("username", "N/A"), inline=True)
    embed.add_field(name="OS", value=data.get("os_version", "N/A"), inline=False)

    # Hardware
    embed.add_field(name="CPU", value=data.get("cpu", "N/A"), inline=False)
    embed.add_field(name="GPU", value=data.get("gpu", "N/A"), inline=True)
    embed.add_field(name="RAM", value=data.get("ram", "N/A"), inline=True)

    # Network
    embed.add_field(name="MAC Address", value=data.get("mac_address", "N/A"), inline=True)
    # Public IP hidden for privacy

    # Warnings
    warnings = []
    if data.get("is_vm"):
        warnings.append(f"🚨 Virtual Machine: {data.get('vm_indicator', 'Detected')}")

    if data.get("suspicious_processes"):
        proc_list = "\n".join([f"  - `{p}`" for p in data["suspicious_processes"][:10]])
        warnings.append(f"⚠️ Suspicious Processes:\n{proc_list}")

    if data.get("suspicious_files"):
        file_list = "\n".join([f"  - `{f}`" for f in data["suspicious_files"][:10]])
        warnings.append(f"⚠️ Suspicious Files:\n{file_list}")

    if warnings:
        embed.add_field(name="⚠️ Warnings", value="\n".join(warnings), inline=False)
    else:
        embed.add_field(name="✅ Checks Passed", value="No VM or suspicious software detected", inline=False)

    # Analysis based on status
    if status == "PENDING":
        embed.add_field(
            name="Action Required",
            value="Awaiting staff review. Use buttons below to Approve/Reject.",
            inline=False
        )
    elif status == "APPROVED":
        embed.add_field(
            name="Result",
            value="✅ This user has been approved to play.",
            inline=False
        )
    elif status == "REJECTED":
        embed.add_field(
            name="Result",
            value="❌ This user has been rejected.",
            inline=False
        )
    elif status == "NEEDS_INFO":
        embed.add_field(
            name="Action Required",
            value="Staff requested more information from this user.",
            inline=False
        )

    embed.set_footer(text=f"Check ID: {data.get('check_id', 'N/A')}")

    return embed

# ============================================================
# BOT COMMANDS
# ============================================================

class PCBOT(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        intents.dm_messages = True  # Enable DM messages
        super().__init__(command_prefix="!", intents=intents)

    async def on_message(self, message: discord.Message):
        # Only handle DMs
        if not isinstance(message.channel, discord.DMChannel):
            return

        # Ignore bot messages
        if message.author.bot:
            return

        user_id = str(message.author.id)

        # Check if user has pending agreement
        if pending_agreements is not None:
            # Clean up expired agreements (older than 24 hours)
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            pending_agreements.delete_many({"created_at": {"$lt": cutoff}})

            pending = pending_agreements.find_one({"_id": user_id})
            if pending:
                if message.content.strip().upper() == "AGREE":
                    # User agreed, send download link
                    pending_agreements.delete_one({"_id": user_id})

                    config = get_guild_config(pending["guild_id"])
                    download_url = config.get("download_url", "")

                    embed = discord.Embed(
                        title="✅ Agreement Accepted",
                        description="Here is your download link:",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="Download Tool",
                        value=f"[Click here to download PC Check Tool]({download_url})" if download_url else "❌ Download URL not configured",
                        inline=False
                    )
                    embed.add_field(
                        name="Instructions",
                        value="1. Download the tool above\n"
                              "2. Run the downloaded .exe file\n"
                              "3. Type AGREE when prompted\n"
                              "4. Enter your Check ID and Discord User ID\n"
                              "5. Wait for it to finish (auto-closes)\n"
                              "6. Your results will be sent automatically",
                        inline=False
                    )
                    embed.add_field(
                        name="Check ID",
                        value=f"`{pending['check_id']}`",
                        inline=False
                    )
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send("Please type **AGREE** to receive the download link.")
                return

        # Let other commands process
        await bot.process_commands(message)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_interaction(self, interaction: discord.Interaction):
        # Handle PC check button clicks
        if interaction.data.get("custom_id", "").startswith("pccheck_"):
            custom_id = interaction.data["custom_id"]
            check_id = custom_id.replace("pccheck_approve", "").replace("pccheck_reject", "").replace("pccheck_moreinfo", "")

            # Determine action from original custom_id
            if "approve" in custom_id:
                action = "APPROVED"
            elif "reject" in custom_id:
                action = "REJECTED"
            else:
                action = "NEEDS_INFO"

            await handle_check_action(interaction, check_id, action)

bot = PCBOT()

# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(name="pccheck_config", description="[Owner] Configure PC Check bot settings")
async def pccheck_config(interaction: discord.Interaction):
    """Show configuration panel."""
    config = get_guild_config(interaction.guild.id)

    # Check if user is bot owner or has admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only administrators can configure the bot.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="⚙️ PC Check Bot Configuration",
        description="Click buttons to configure each setting:",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed, view=ConfigView(bot))


@bot.tree.command(name="pccheck_status", description="[Owner] View current configuration")
async def pccheck_status(interaction: discord.Interaction):
    """Show current configuration status."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only administrators can view configuration.",
            ephemeral=True
        )
        return

    config = get_guild_config(interaction.guild.id)

    embed = discord.Embed(
        title="PC Check Bot Configuration",
        color=discord.Color.blue()
    )

    pc_channel = bot.get_channel(config.get("pc_check_channel_id", 0))
    log_channel = bot.get_channel(config.get("log_channel_id", 0))
    staff_role = interaction.guild.get_role(config.get("staff_role_id", 0))
    approved_role = interaction.guild.get_role(config.get("approved_role_id", 0))
    rejected_role = interaction.guild.get_role(config.get("rejected_role_id", 0))
    pending_role = interaction.guild.get_role(config.get("pending_role_id", 0))

    embed.add_field(name="PC Check Channel", value=pc_channel.mention if pc_channel else "Not Set", inline=True)
    embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not Set", inline=True)
    embed.add_field(name="Staff Role", value=staff_role.mention if staff_role else "Not Set", inline=True)
    embed.add_field(name="Approved Role", value=approved_role.mention if approved_role else "Not Set", inline=True)
    embed.add_field(name="Rejected Role", value=rejected_role.mention if rejected_role else "Not Set", inline=True)
    embed.add_field(name="Pending Role", value=pending_role.mention if pending_role else "Not Set", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="send_pc_check", description="[Staff] Send PC check request to a user")
@app_commands.describe(user="The user to request a PC check from")
async def send_pc_check(interaction: discord.Interaction, user: discord.User):
    """Send a PC check request to a user via DM."""

    config = get_guild_config(interaction.guild.id)

    # Check permissions
    staff_role_id = config.get("staff_role_id", 0)
    has_permission = False

    if interaction.user.guild_permissions.manage_messages:
        has_permission = True
    elif staff_role_id and any(role.id == staff_role_id for role in interaction.user.roles):
        has_permission = True

    if not has_permission:
        await interaction.response.send_message(
            "❌ You don't have permission to request PC checks.",
            ephemeral=True
        )
        return

    # Generate check ID
    check_id = str(uuid.uuid4())[:8]
    download_url = config.get("download_url", "")

    # Create pending check data with guild_id
    check_data = {
        "_id": check_id,
        "check_id": check_id,
        "guild_id": str(interaction.guild.id),
        "user_id": str(user.id),
        "username": f"{user.name}#{user.discriminator}",
        "status": "PENDING",
        "created_at": datetime.now().isoformat(),
        "created_by": str(interaction.user.id),
    }

    # Save to database
    create_check(check_data)

    # Store pending agreement
    if pending_agreements is not None:
        # Check if user has existing check and remove their old roles first
        user_checks = checks_collection.find({"user_id": str(user.id)})
        for old_check in user_checks:
            if old_check.get("status") == "APPROVED":
                approved_role_id = config.get("approved_role_id", 0)
                if approved_role_id:
                    member = interaction.guild.get_member(user.id)
                    if member:
                        try:
                            role = interaction.guild.get_role(approved_role_id)
                            if role and role in member.roles:
                                await member.remove_roles(role)
                        except:
                            pass
            elif old_check.get("status") == "REJECTED":
                rejected_role_id = config.get("rejected_role_id", 0)
                if rejected_role_id:
                    member = interaction.guild.get_member(user.id)
                    if member:
                        try:
                            role = interaction.guild.get_role(rejected_role_id)
                            if role and role in member.roles:
                                await member.remove_roles(role)
                        except:
                            pass

        # Upsert pending agreement
        pending_agreements.update_one(
            {"_id": str(user.id)},
            {"$set": {
                "check_id": check_id,
                "guild_id": str(interaction.guild.id),
                "created_at": datetime.now().isoformat(),
            }},
            upsert=True
        )

    # Confirm immediately to avoid interaction timeout
    confirm_msg = f"✅ PC check request sent!"
    confirm_msg += f"\n• DM sent to {user.mention}"
    confirm_msg += f"\n• Check ID: `{check_id}`"

    await interaction.response.send_message(confirm_msg, ephemeral=True)

    # Send DM to user asking for agreement (after response)
    try:
        dm_embed = discord.Embed(
            title="🔍 PC Verification Required",
            description=f"You have been requested to complete a PC verification check by {interaction.user.mention}.",
            color=discord.Color.orange()
        )
        dm_embed.add_field(
            name="Terms Agreement",
            value="By running this tool, you agree to:\n"
                  "• Your system information being collected\n"
                  "• Results being reviewed by server staff\n"
                  "• Being banned if cheating software is detected\n\n"
                  "**Type AGREE to receive the download link.**",
            inline=False
        )
        dm_embed.add_field(
            name="Check ID",
            value=f"`{check_id}`",
            inline=False
        )
        dm_embed.set_footer(text="If you have issues, contact staff.")

        await user.send(embed=dm_embed)
    except:
        pass

    # Post check request in channel (without download link, for staff)
    pc_channel_id = config.get("pc_check_channel_id", 0)
    if pc_channel_id:
        pc_channel = bot.get_channel(pc_channel_id)
        if pc_channel:
            embed = create_pc_check_embed(check_data)
            view = PCCheckActionView(check_id)
            staff_role_id = config.get("staff_role_id", 0)
            staff_mention = f"<@&{staff_role_id}> " if staff_role_id else ""
            await pc_channel.send(
                content=f"{staff_mention}{user.mention} PC check requested (`{check_id}`)",
                embed=embed,
                view=view
            )

    # Give pending role if configured
    pending_role_id = config.get("pending_role_id", 0)
    if pending_role_id:
        member = interaction.guild.get_member(user.id)
        if member:
            try:
                pending_role = interaction.guild.get_role(pending_role_id)
                if pending_role:
                    await member.add_roles(pending_role)
            except:
                pass


@bot.tree.command(name="check_status", description="Check your PC verification status")
async def check_status(interaction: discord.Interaction):
    """Users check their own status."""
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    # Get the most recent check for this user in this guild
    user_checks = get_user_checks(guild_id, user_id)

    if not user_checks:
        await interaction.response.send_message(
            "ℹ️ You haven't submitted a PC check yet.",
            ephemeral=True
        )
        return

    # Get most recent check
    user_check = user_checks[0]
    status = user_check.get("status", "UNKNOWN")
    status_emoji = get_status_emoji(status)

    embed = discord.Embed(
        title="PC Check Status",
        color=get_status_color(status)
    )
    embed.add_field(name="Status", value=f"{status_emoji} **{status.replace('_', ' ').title()}**", inline=True)
    embed.add_field(name="Check ID", value=user_check.get("check_id", "N/A"), inline=True)

    if status == "APPROVED":
        embed.description = "✅ Your PC has been approved. You're good to go!"
    elif status == "REJECTED":
        embed.description = "❌ Your PC check was rejected. Contact staff for more info."
    elif status == "NEEDS_INFO":
        embed.description = "🔍 Staff requested more information from you. Please contact them."
    else:
        embed.description = "Your check is being processed."

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="pccheck_help", description="Get help with PC checks")
async def pccheck_help(interaction: discord.Interaction):
    """Show help information."""
    embed = discord.Embed(
        title="PC Check System Help",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="For Users",
        value="1. You will receive a DM with download link\n"
              "2. Download and run the PC Check tool\n"
              "3. It auto-closes when done\n"
              "4. Use `/check_status` to check your status",
        inline=False
    )

    embed.add_field(
        name="For Staff",
        value="• `/send_pc_check @user` - Request a check\n"
              "• Click Approve/Reject buttons on checks\n"
              "• `/pccheck_config` - Configure bot settings",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# WEBHOOK HANDLER (for PC Check EXE)
# ============================================================

# ============================================================
# MAIN
# ============================================================

import threading
from flask import Flask, request
import json as json_lib

# Flask app for receiving EXE data
flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def webhookReceiver():
    """Receive PC check data from EXE and post to channel."""
    try:
        data = request.get_json()
        print(f"Webhook received: {data}")

        check_id = data.get('check_id', 'UNKNOWN')
        user_id = data.get('user_id', '0')

        # Look up the check to find guild_id
        check_data = get_check(check_id)
        print(f"Check data for {check_id}: {check_data}")

        if not check_data:
            return "Check not found", 404

        guild_id = check_data.get("guild_id")
        if not guild_id:
            return "Guild not found for check", 400

        # Get guild config
        config = get_guild_config(guild_id)
        print(f"Config for guild {guild_id}: {config}")

        # Get channel ID
        pc_channel_id = config.get("pc_check_channel_id", 0)
        print(f"PC Channel ID: {pc_channel_id}")

        # Check for suspicious processes and VM
        suspicious = data.get('suspicious_processes', [])
        is_vm = data.get('is_vm', False)

        # Determine status based on findings
        if is_vm or suspicious:
            # Flag for review if VM or suspicious processes found
            new_status = "NEEDS_INFO"
        else:
            new_status = "PENDING"

        # Get suspicious files from EXE data
        suspicious_files = data.get('suspicious_files', [])

        # Update check with system info
        update_check(check_id, {
            "hostname": data.get('hostname'),
            "username": data.get('username'),
            "os_version": data.get('os_version'),
            "cpu": data.get('cpu'),
            "gpu": data.get('gpu'),
            "ram": data.get('ram'),
            "mac_address": data.get('mac_address'),
            # public_ip hidden for privacy
            "is_vm": is_vm,
            "vm_indicator": data.get('vm_indicator'),
            "suspicious_processes": suspicious,
            "suspicious_files": suspicious_files,
            "gpu_driver": data.get('gpu_driver'),
            "status": new_status,
        })

        # Create embed from EXE data
        embed = discord.Embed(
            title="PC Verification Check",
            color=discord.Color.orange() if new_status == "NEEDS_INFO" else discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="Check ID", value=check_id, inline=True)

        status_text = "🔍 NEEDS REVIEW - Suspicious software detected" if new_status == "NEEDS_INFO" else "⏳ RECEIVED - Pending Review"
        embed.add_field(name="Status", value=status_text, inline=True)

        embed.add_field(name="Hostname", value=data.get('hostname', 'N/A'), inline=True)
        embed.add_field(name="Username", value=data.get('username', 'N/A'), inline=True)
        embed.add_field(name="OS", value=data.get('os_version', 'N/A'), inline=False)
        embed.add_field(name="CPU", value=data.get('cpu', 'N/A'), inline=False)
        embed.add_field(name="GPU", value=data.get('gpu', 'N/A'), inline=True)
        embed.add_field(name="RAM", value=data.get('ram', 'N/A'), inline=True)
        embed.add_field(name="MAC", value=data.get('mac_address', 'N/A'), inline=True)
        # Public IP hidden for privacy

        # Warnings section
        warnings = []
        if is_vm:
            warnings.append(f"🚨 VM Detected: {data.get('vm_indicator', 'Unknown')}")
        if suspicious:
            proc_list = "\n".join([f"  - `{p}`" for p in suspicious])
            warnings.append(f"⚠️ Suspicious Processes:\n{proc_list}")
        if suspicious_files:
            file_list = "\n".join([f"  - `{f}`" for f in suspicious_files[:10]])
            warnings.append(f"⚠️ Suspicious Files:\n{file_list}")

        if warnings:
            embed.add_field(name="⚠️ Warnings", value="\n".join(warnings), inline=False)
        else:
            embed.add_field(name="✅ Checks Passed", value="No VM or suspicious software detected", inline=False)

        embed.set_footer(text=f"Check ID: {check_id}")

        # Post to PC Check channel
        staff_role_id = config.get("staff_role_id", 0)
        print(f"Posting to channel {pc_channel_id}, staff role: {staff_role_id}")
        if pc_channel_id:
            pc_channel = bot.get_channel(pc_channel_id)
            print(f"Channel object: {pc_channel}")
            if pc_channel:
                view = PCCheckActionView(check_id)
                staff_mention = f"<@&{staff_role_id}> " if staff_role_id else ""
                asyncio.run_coroutine_threadsafe(
                    pc_channel.send(content=f"{staff_mention}<@{user_id}> PC check received!", embed=embed, view=view),
                    bot.loop
                )
            else:
                print("Channel not found!")
        else:
            print("No channel ID configured!")

        return "OK", 200

    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)

@bot.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"PC Check Bot Ready!")
    print(f"{'='*50}")
    print(f"Bot: {bot.user.name}")
    print(f"Commands synced: Yes")
    print(f"Database: {'MongoDB Connected' if db_client else 'MongoDB NOT CONNECTED (no URI)'}")
    print(f"{'='*50}\n")

def main():
    # Bot token is set via environment variable on Render
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        print("ERROR: DISCORD_BOT_TOKEN environment variable not set!")
        print("Please set it in Render dashboard -> Environment -> Environment Variables")
        return

    # Start Flask server in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Web server started on port 10000")

    bot.run(token)

if __name__ == "__main__":
    main()
