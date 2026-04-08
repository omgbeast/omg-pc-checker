# PC Verification Discord Bot

A Discord bot with fully configurable settings via Discord commands. No code editing required.

## Features

- **Fully configurable via Discord** - All settings set through `/pccheck_config` command
- **DM delivery** - Users receive download link via DM automatically
- **Auto role management** - Assign/remove roles based on check status
- **Staff dashboard** - Approve/Reject/Request More Info with buttons
- **Logging** - All actions logged to configured channel

## How It Works

1. **Staff** uses `/send_pc_check @user` to request a check
2. **Bot DMs** the user with download link
3. **User** downloads and runs the EXE
4. **EXE** sends system info to Discord automatically
5. **Staff** sees results with Approve/Reject/More Info buttons
6. **Roles** are automatically assigned/removed based on status

## Setup

### 1. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Create application and add Bot
3. Enable intents:
   - **Message Content Intent**
   - **Server Members Intent**
4. Copy bot token

### 2. Create Webhook

1. In your Discord server channel (for PC checks)
2. Channel Settings → Integrations → Webhooks
3. Create webhook and copy URL

### 3. Configure Bot

1. Run `python bot.py`
2. Use `/pccheck_config` command
3. Set each setting using the buttons:
   - 🔑 Bot Token
   - 🔗 Webhook URL
   - 📁 PC Check Channel
   - 📝 Log Channel
   - 👮 Staff Role
   - ✅ Approved Role (optional)
   - ❌ Rejected Role (optional)
   - ⏳ Pending Role (optional)
   - 📥 Download URL

### 4. Build the EXE

```bash
pip install pyinstaller
python build_exe.py
```

Upload `dist/PCCheck.exe` to your hosting and set the Download URL in config.

## Commands

| Command | Description |
|---------|-------------|
| `/pccheck_config` | Configure bot settings (Admin) |
| `/pccheck_status` | View current configuration |
| `/send_pc_check @user` | Request PC check from user (Staff) |
| `/check_status` | Check your own PC verification status |
| `/pccheck_help` | Show help information |

## Configuration Options

| Setting | Description |
|---------|-------------|
| Bot Token | Your Discord bot token |
| Webhook URL | Webhook for receiving PC check data |
| PC Check Channel | Channel to post check requests |
| Log Channel | Channel for approve/reject logs |
| Staff Role | Role that can approve/reject |
| Approved Role | Auto-assigned when approved |
| Rejected Role | Auto-assigned when rejected |
| Pending Role | Auto-assigned when check requested |
| Download URL | Link to PCCheck.exe |

## Auto Role Features

When configured, the bot will automatically:
- Give pending role when check is requested
- Give approved role and remove rejected when approved
- Give rejected role and remove approved when rejected
- Remove pending role when processed

## What the EXE Collects

- Hostname & Username
- OS Version
- CPU, GPU, RAM
- MAC Address & Public IP
- GPU Driver version
- Suspicious processes
- VM detection

## Files

| File | Description |
|------|-------------|
| bot.py | Main bot |
| pc_check_exe.py | EXE source |
| build_exe.py | Build script |
| bot_config.json | Configuration (auto-created) |
| check_requests.json | Pending checks |
| check_data.json | User check results |

## Security Note

This is a verification system, not anti-cheat. Determined users can bypass it. For competitive gaming, use professional anti-cheat solutions.
