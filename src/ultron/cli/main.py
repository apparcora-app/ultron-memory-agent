"""
main.py — Interactive CLI entry point for the Memory Agent.

Usage
─────
  python main.py                        # default user
  python main.py --user alice           # named user
  python main.py --user alice --debug   # show raw memory ops

Special commands (type in chat)
────────────────────────────────
  /memories   — list every stored memory for this user
  /clear      — wipe in-session message history (long-term memory is kept)
  /forget <id> — delete a specific memory by ID
  /help       — show this command list
  /quit       — exit
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ultron.agent import BudgetExceededError, MemoryAgent

console = Console()


# ── display helpers ───────────────────────────────────────────────────────────

def print_welcome(user_id: str) -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]🧠 Memory Agent[/bold cyan]\n"
            f"User: [yellow]{user_id}[/yellow]\n\n"
            "[dim]Type [bold]/help[/bold] for commands, [bold]/quit[/bold] to exit.[/dim]",
            border_style="cyan",
        )
    )


def print_memories_table(memories: list[dict]) -> None:
    if not memories:
        console.print("[dim]No memories stored yet.[/dim]")
        return

    table = Table(title="📚 Stored Memories", show_lines=True, border_style="blue")
    table.add_column("ID (short)", style="dim", max_width=12)
    table.add_column("Memory", style="white")

    for m in memories:
        short_id = str(m.get("id", ""))[:8]
        text = m.get("memory", m.get("text", str(m)))
        table.add_row(short_id, text)

    console.print(table)


def print_assistant(reply: str) -> None:
    console.print(Panel(Markdown(reply), title="[bold green]Assistant[/bold green]", border_style="green"))


def print_debug(label: str, data: object) -> None:
    console.print(f"[dim][DEBUG] {label}:[/dim]", data)


# ── command handling ──────────────────────────────────────────────────────────

def handle_command(cmd: str, agent: MemoryAgent, debug: bool) -> bool:
    """
    Process a slash command.

    Returns True if execution should continue, False to quit.
    """
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()

    if command == "/quit":
        console.print("[bold red]Goodbye![/bold red]")
        return False

    elif command == "/help":
        console.print(
            Panel(
                "[bold]/memories[/bold]    — list all stored memories\n"
                "[bold]/clear[/bold]       — clear in-session history\n"
                "[bold]/forget <id>[/bold] — delete memory by short ID prefix\n"
                "[bold]/budget[/bold]      — show today's token usage and cost\n"
                "[bold]/help[/bold]        — show this message\n"
                "[bold]/quit[/bold]        — exit",
                title="Commands",
                border_style="yellow",
            )
        )

    elif command == "/memories":
        memories = agent.show_all_memories()
        print_memories_table(memories)

    elif command == "/clear":
        agent.clear_session_history()
        console.print("[dim]In-session history cleared. Long-term memories are intact.[/dim]")

    elif command == "/budget":
        console.print(Panel(agent.budget_summary(), title="💰 Budget & Usage", border_style="magenta"))

    elif command == "/forget":
        if len(parts) < 2:
            console.print("[red]Usage: /forget <memory-id-prefix>[/red]")
        else:
            prefix = parts[1].strip()
            memories = agent.show_all_memories()
            matched = [m for m in memories if str(m.get("id", "")).startswith(prefix)]
            if not matched:
                console.print(f"[red]No memory found with ID starting with '{prefix}'[/red]")
            elif len(matched) > 1:
                console.print("[red]Ambiguous prefix — be more specific.[/red]")
                print_memories_table(matched)
            else:
                mem_id = matched[0]["id"]
                agent.memory_manager.delete(mem_id)
                console.print(f"[green]Deleted memory {mem_id}[/green]")

    else:
        console.print(f"[red]Unknown command: {command}. Type /help for options.[/red]")

    return True


# ── main loop ─────────────────────────────────────────────────────────────────

def run(user_id: str, debug: bool) -> None:
    print_welcome(user_id)

    try:
        agent = MemoryAgent(user_id=user_id)
    except OSError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[bold red]Failed to initialise agent:[/bold red] {exc}")
        sys.exit(1)

    console.print("[dim]Agent ready. Local memory database connected.[/dim]\n")


    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Flushing pending memories…[/dim]")
            agent.flush_pending_memory()
            console.print("[bold red]Goodbye![/bold red]")
            break

        if not user_input:
            continue

        # Slash command?
        if user_input.startswith("/"):
            should_continue = handle_command(user_input, agent, debug)
            if not should_continue:
                agent.flush_pending_memory()
                break
            continue

        # Normal chat turn
        try:
            with console.status("[dim]Thinking…[/dim]", spinner="dots"):
                result = agent.chat(user_input)
            reply = result.get("reply", "") if isinstance(result, dict) else str(result)

            print_assistant(reply)

            if debug:
                memories = agent.memory_manager.search(user_input)
                print_debug("retrieved memories", memories)


        except BudgetExceededError as exc:
            console.print(Panel(
                f"[bold red]Daily budget exhausted:[/bold red] {exc}\n\n"
                f"{agent.budget_summary()}",
                title="💸 Budget Limit",
                border_style="red",
            ))
            agent.flush_pending_memory()
            break

        except Exception as exc:
            import traceback
            traceback.print_exc()
            console.print(f"[bold red]Error during chat:[/bold red] {exc}")
            if debug:
                import traceback
                traceback.print_exc()


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Memory Agent — AI assistant with persistent long-term memory"
    )
    parser.add_argument(
        "--user",
        default="default_user",
        help="User ID to scope memories (default: 'default_user')",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print retrieved memories and raw Mem0 responses each turn",
    )
    args = parser.parse_args()
    run(user_id=args.user, debug=args.debug)


if __name__ == "__main__":
    main()
