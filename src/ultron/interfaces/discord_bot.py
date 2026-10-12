"""
discord_bot.py — Ultron Protocol: Discord Mobile & Desktop Command Bridge.

Connects Ultron to Discord so the operator can send directives, upload files/PDFs/spreadsheets,
and receive autonomous action reports from anywhere on iOS, Android, and Desktop.

Features:
  • Direct Messages (1-on-1 DM with Ultron) and Server Channels.
  • Rich Cyberpunk Embeds with tool execution logs & model badges.
  • Multi-modal — Handles text, images, PDFs, Excel sheets, and CSVs.
  • Autonomous Execution — Executes tools (terminal, Python, browser, web search) and reports live.
  • Slash Commands — /status, /budget, /memory, /module, /clear.
  • Operator ID Security — Restricts access to authorized Discord User IDs.
  • Shared Neural Memory — Synchronized with the Web HUD's memory matrix.

Usage:
  python discord_bot.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

import discord
from discord import app_commands
from dotenv import load_dotenv

from ultron.agent import ULTRON_MODULES, MemoryAgent
from ultron.infrastructure.file_processor import FileProcessor, ProcessedFile

load_dotenv()

# ── Config & Credentials ──────────────────────────────────────────────────────

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
ALLOWED_USER_IDS_RAW = os.getenv("DISCORD_ALLOWED_USER_IDS", "").strip()

ALLOWED_USER_IDS: set[int] = set()
if ALLOWED_USER_IDS_RAW:
    for uid_str in ALLOWED_USER_IDS_RAW.split(","):
        uid_str = uid_str.strip()
        if uid_str.isdigit():
            ALLOWED_USER_IDS.add(int(uid_str))

# Active user module state: user_id -> module_id
_user_modules: dict[str, str] = {}

# Shared agent instance
_agent_instance: MemoryAgent | None = None


def get_agent() -> MemoryAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = MemoryAgent(user_id="default_user")
    return _agent_instance


# ── Security Gatekeeper ───────────────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    """Check if the sender is authorized."""
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


# ── Formatting Helpers ────────────────────────────────────────────────────────

def format_tool_actions(actions: list[dict[str, Any]]) -> str:
    """Format executed tool actions into a crisp Discord status block."""
    if not actions:
        return ""

    lines = ["**⚙️ SYSTEM ACTIONS EXECUTED:**"]
    for a in actions:
        tool = a.get("tool", "")
        success = "✅" if a.get("success") else "❌"
        duration = f"({a.get('duration_ms', 0) / 1000:.1f}s)" if a.get("duration_ms") else ""

        if tool == "open_browser":
            inp = a.get("input", {})
            lines.append(f"{success} **BROWSER:** Opened Chrome `[{inp.get('profile', 'default')}]` {duration}")
        elif tool == "open_application":
            inp = a.get("input", {})
            lines.append(f"{success} **APP:** Launched `{inp.get('app_name')}` {duration}")
        elif tool == "execute_command":
            cmd = a.get("input", {}).get("command", "")
            lines.append(f"{success} **TERMINAL:** `{(cmd or '')[:35]}` {duration}")
        elif tool == "run_python":
            desc = a.get("input", {}).get("description", "Python Script")
            lines.append(f"{success} **PYTHON:** {desc} {duration}")
        elif tool == "web_search":
            query = a.get("input", {}).get("query", "")
            lines.append(f"{success} **WEB INTEL:** *{(query or '')[:30]}* {duration}")
        elif tool == "file_operation":
            inp = a.get("input", {})
            lines.append(f"{success} **FILE:** {inp.get('operation', '').upper()} `{os.path.basename(inp.get('path', ''))}` {duration}")
        else:
            lines.append(f"{success} **{tool.upper()}** {duration}")

    return "\n".join(lines) + "\n\n"


async def send_discord_response(channel: discord.abc.Messageable, reply_text: str, model_used: str, tool_actions: list[dict[str, Any]], reference_msg: discord.Message | None = None) -> None:
    """Sends response formatted nicely with cybernetic styling, chunking if necessary."""
    model_lower = (model_used or "").lower()
    if "gemini" in model_lower:
        color = discord.Color.from_rgb(66, 133, 244)  # Google Blue
        model_badge = "⚡ GEMINI 2.0 FLASH"
    elif "haiku" in model_lower:
        color = discord.Color.from_rgb(0, 240, 255)  # Cyan
        model_badge = "⚡ HAIKU 4.5"
    else:
        color = discord.Color.from_rgb(255, 26, 60)  # Crimson
        model_badge = "🧠 SONNET 5"

    actions_text = format_tool_actions(tool_actions)
    combined = f"{actions_text}{reply_text}".strip()

    # If within Discord embed description limit (4096 chars)
    if len(combined) <= 3900:
        embed = discord.Embed(
            description=combined,
            color=color,
        )
        embed.set_author(name=f"ULTRON PROTOCOL — {model_badge}", icon_url="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/robot.svg")
        embed.set_footer(text="Cybernetic AI Mainframe • Operator Authorization Active")

        if reference_msg:
            await reference_msg.reply(embed=embed)
        else:
            await channel.send(embed=embed)
        return

    # If longer than embed limit, split into standard text messages
    max_len = 1900
    parts = []
    text = combined
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()

    for i, part in enumerate(parts):
        header = f"**[ULTRON CORE • {model_badge}]**\n" if i == 0 else ""
        if i == 0 and reference_msg:
            await reference_msg.reply(f"{header}{part}")
        else:
            await channel.send(f"{header}{part}")


# ── Discord Client Setup ──────────────────────────────────────────────────────

class UltronBotClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.guild_messages = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()
        print("  [DISCORD] Slash commands synced globally.")

    async def on_ready(self) -> None:
        print("\n" + "=" * 60)
        print("  [ULTRON PROTOCOL] DISCORD MOBILE BRIDGE ONLINE")
        print(f"  Logged in as: {self.user.name} ({self.user.id})")
        if ALLOWED_USER_IDS:
            print(f"  Authorized Operator IDs: {ALLOWED_USER_IDS}")
        else:
            print("  Security: Open (First-time setup mode)")
        print("=" * 60 + "\n")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="over workspace • /status",
        )
        await self.change_presence(status=discord.Status.online, activity=activity)


bot = UltronBotClient()


# ── Slash Commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="status", description="Inspect Ultron system telemetry, models, and memory matrix.")
async def slash_status(interaction: discord.Interaction) -> None:
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("🚫 Access restricted to authorized Operator account.", ephemeral=True)
        return

    agent = get_agent()
    budget = agent.get_budget_data()
    skills = agent.skill_manager.get_all_skills()
    memories = agent.show_all_memories()

    embed = discord.Embed(
        title="🤖 ULTRON SYSTEM TELEMETRY",
        color=discord.Color.from_rgb(0, 240, 255),
    )
    embed.add_field(name="System Status", value="🟢 OPERATIONAL", inline=True)
    embed.add_field(name="LLM Core", value="Claude Sonnet 5 + Haiku", inline=True)
    embed.add_field(name="Vector Matrix", value=f"{len(memories)} Facts Stored", inline=True)
    embed.add_field(name="ClawHub Skills", value=f"{len(skills)} Installed", inline=True)
    embed.add_field(name="Today's Tokens", value=f"{budget.get('total_tokens', 0):,}", inline=True)
    embed.add_field(name="Today's Spend", value=f"${budget.get('cost_usd', 0.0):.4f}", inline=True)
    embed.set_footer(text="Ultron Cybernetic Mainframe • Local ChromaDB")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="budget", description="View daily token usage and cost metrics.")
async def slash_budget(interaction: discord.Interaction) -> None:
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("🚫 Access restricted.", ephemeral=True)
        return

    agent = get_agent()
    summary = agent.budget_summary()
    embed = discord.Embed(
        title="📊 DAILY BUDGET TELEMETRY",
        description=f"```\n{summary}\n```",
        color=discord.Color.from_rgb(255, 26, 60),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="memory", description="Inspect operator profile facts locked in permanent vector memory.")
async def slash_memory(interaction: discord.Interaction) -> None:
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("🚫 Access restricted.", ephemeral=True)
        return

    agent = get_agent()
    memories = agent.show_all_memories()

    if not memories:
        await interaction.response.send_message("🧠 **Memory Matrix:** No facts currently stored.", ephemeral=True)
        return

    lines = [f"**{i}.** {m.get('text', '')}" for i, m in enumerate(memories[:20], 1)]
    embed = discord.Embed(
        title=f"🧠 LOCKED MEMORY MATRIX ({len(memories)} Facts)",
        description="\n".join(lines),
        color=discord.Color.from_rgb(0, 240, 255),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="module", description="Switch active Ultron persona module.")
@app_commands.describe(module_name="Module ID: ultron_prime, financial_war_room, ledger_protocol, career_acquisition, client_infiltration")
async def slash_module(interaction: discord.Interaction, module_name: str | None = None) -> None:
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("🚫 Access restricted.", ephemeral=True)
        return

    user_id_str = str(interaction.user.id)

    if not module_name:
        current = _user_modules.get(user_id_str, "ultron_prime")
        lines = [f"🎛️ **Current Module:** `{current}`\n\n**Available Modules:**"]
        for mod_id, info in ULTRON_MODULES.items():
            lines.append(f"• `/module {mod_id}` — {info['icon']} **{info['name']}**: *{info['tagline']}*")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    target = module_name.lower().strip()
    if target in ULTRON_MODULES:
        _user_modules[user_id_str] = target
        info = ULTRON_MODULES[target]
        await interaction.response.send_message(
            f"⚡ Active module switched to: {info['icon']} **{info['name']}**\n*{info['tagline']}*"
        )
    else:
        await interaction.response.send_message(f"❌ Unknown module: `{target}`. Use `/module` to see all.", ephemeral=True)


@bot.tree.command(name="clear", description="Purge in-session neural buffer (long-term memory remains intact).")
async def slash_clear(interaction: discord.Interaction) -> None:
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("🚫 Access restricted.", ephemeral=True)
        return

    agent = get_agent()
    agent.clear_session_history()
    await interaction.response.send_message("⚡ In-session neural buffer purged. Long-term memory matrix remains intact.")


# ── Message Event (DMs & Channel Directives) ──────────────────────────────────

@bot.event
async def on_message(message: discord.Message) -> None:
    # Ignore own messages
    if message.author == bot.user:
        return

    # Check if message is in DM or bot is mentioned
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions

    # If in a guild channel, only respond if mentioned
    if not is_dm and not is_mentioned:
        return

    if not is_authorized(message.author.id):
        if is_dm:
            await message.reply(
                f"🚫 **ACCESS RESTRICTED.**\nYour Discord User ID is: `{message.author.id}`\n"
                f"Add this ID to `DISCORD_ALLOWED_USER_IDS` in `.env` to grant clearance."
            )
        return

    # Clean prompt text (strip mention tag if present)
    user_text = message.clean_content
    if is_mentioned and bot.user:
        user_text = user_text.replace(f"@{bot.user.name}", "").replace(f"@{bot.user.display_name}", "").strip()

    # Process attachments (PDF, Excel, CSV, Images)
    processed_files: list[ProcessedFile] = []
    if message.attachments:
        for att in message.attachments:
            try:
                content_bytes = await att.read()
                if content_bytes:
                    pf = FileProcessor.process_file(att.filename, content_bytes)
                    processed_files.append(pf)
            except Exception as e:
                print(f"Error processing attachment {att.filename}: {e}")

    if not user_text and not processed_files:
        return

    # Send typing presence
    async with message.channel.typing():
        agent = get_agent()
        active_module = _user_modules.get(str(message.author.id), "ultron_prime")

        try:
            import asyncio
            chat_result = await asyncio.to_thread(
                agent.chat,
                user_input=user_text,
                files=processed_files,
                module_id=active_module,
            )

            reply = chat_result.get("reply", "") if isinstance(chat_result, dict) else str(chat_result)
            tool_actions = chat_result.get("tool_actions", []) if isinstance(chat_result, dict) else []
            model_used = chat_result.get("model_used", "")

            await send_discord_response(
                channel=message.channel,
                reply_text=reply,
                model_used=model_used,
                tool_actions=tool_actions,
                reference_msg=message,
            )

        except Exception as e:
            await message.reply(f"⚠️ **ULTRON SYSTEM ERROR:** {e}")


# ── Main Launcher ─────────────────────────────────────────────────────────────

def main() -> None:
    if not DISCORD_BOT_TOKEN:
        print("\n" + "=" * 60)
        print("  [ERROR] DISCORD_BOT_TOKEN is not set in .env!")
        print("  1. Visit: https://discord.com/developers/applications")
        print("  2. Create a 'New Application' -> Bot -> Reset Token -> Copy")
        print("  3. Enable 'MESSAGE CONTENT INTENT' under Bot tab")
        print("  4. Add DISCORD_BOT_TOKEN=your_token_here to .env")
        print("=" * 60 + "\n")
        sys.exit(1)

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
