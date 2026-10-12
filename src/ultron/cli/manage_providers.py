#!/usr/bin/env python3
"""
manage_providers.py — CLI for managing providers.yaml

Commands:
  discover   Paste an API key → see all available models (free/paid)
  add        Add one or more discovered models to providers.yaml
  list       Show what's currently in providers.yaml
  remove     Remove a provider by ID
  reload     Hot-reload providers into the running gateway

Usage:
  python manage_providers.py discover --provider openrouter --key sk-or-...
  python manage_providers.py discover --key sk-or-...          # auto-detects
  python manage_providers.py discover --key sk-or-... --free   # free only
  python manage_providers.py add --id openrouter-deepseek-r1
  python manage_providers.py add --all-free --provider openrouter --key sk-or-...
  python manage_providers.py list
  python manage_providers.py remove --id openrouter-deepseek-r1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path so imports work when run directly
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ultron.core.provider_discovery import (
    DiscoveredModel,
    detect_provider_from_key,
    discover_models,
)

PROVIDERS_YAML = ROOT / "providers.yaml"

# ANSI colors (Windows-compatible via ENABLE_VIRTUAL_TERMINAL_PROCESSING)
os.system("")  # enables ANSI on Windows
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"
BLUE   = "\033[94m"


def _tier_badge(tier: str) -> str:
    colors = {
        "fast": f"{GREEN}Fast{RESET}",
        "reasoning": f"{CYAN}Reason{RESET}",
        "standard": f"{YELLOW}Standard{RESET}",
        "local": f"{DIM}Local{RESET}",
    }
    return colors.get(tier, tier)


def _free_badge(model: DiscoveredModel) -> str:
    if model.is_free:
        return f"{GREEN}FREE{RESET}"
    return f"{YELLOW}${model.cost_per_1m_input:.3f}/1M{RESET}"


def _ctx(n: int) -> str:
    if n >= 1_000_000:
        return f"{n // 1_000_000}M"
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def cmd_discover(args: argparse.Namespace) -> None:
    """Discover models for a given provider + API key."""
    api_key = args.key or os.environ.get(
        f"{(args.provider or 'openrouter').upper()}_API_KEY", ""
    )
    if not api_key:
        print(f"{RED}Error:{RESET} No API key provided. Use --key or set the env var.")
        sys.exit(1)

    provider = args.provider or detect_provider_from_key(api_key, getattr(args, "base_url", None))
    base_url = getattr(args, "base_url", None)

    print(f"\n{BOLD}Discovering models from {provider.upper()}...{RESET}")
    try:
        models = discover_models(api_key=api_key, provider=provider, base_url=base_url)
    except Exception as e:
        print(f"{RED}Discovery failed:{RESET} {e}")
        sys.exit(1)

    # Filter
    if getattr(args, "free", False):
        models = [m for m in models if m.is_free]
    if getattr(args, "vision", False):
        models = [m for m in models if m.supports_vision]
    if getattr(args, "tools", False):
        models = [m for m in models if m.supports_tools]
    if getattr(args, "tier", None):
        models = [m for m in models if m.tier == args.tier]
    if getattr(args, "search", None):
        q = args.search.lower()
        models = [m for m in models if q in m.display_name.lower() or q in m.model_id.lower()]

    # Load existing IDs to mark already-added ones
    existing_ids = _get_existing_ids()

    free_models = [m for m in models if m.is_free]
    paid_models = [m for m in models if not m.is_free]

    print(f"\n{BOLD}{'-'*80}{RESET}")
    print(f"  {BOLD}Provider:{RESET} {provider.upper()}   "
          f"{BOLD}Total:{RESET} {len(models)}   "
          f"{GREEN}Free: {len(free_models)}{RESET}   "
          f"{YELLOW}Paid: {len(paid_models)}{RESET}")
    print(f"{BOLD}{'-'*80}{RESET}\n")

    def _print_section(title: str, section_models: list[DiscoveredModel]) -> None:
        if not section_models:
            return
        print(f"  {BOLD}{title} ({len(section_models)}){RESET}")
        print(f"  {'ID':<45} {'Name':<35} {'Ctx':>6}  {'Price':>12}  {'Tier':<10}  {'Vision'}")
        print(f"  {'-'*45} {'-'*35} {'-'*6}  {'-'*12}  {'-'*10}  {'-'*6}")
        for m in section_models:
            added = f" {DIM}[added]{RESET}" if m.providers_yaml_id in existing_ids else ""
            vision = f"{GREEN}Yes{RESET}" if m.supports_vision else f"{DIM}No{RESET}"
            print(
                f"  {CYAN}{m.model_id:<45}{RESET}"
                f" {m.display_name:<35}"
                f" {_ctx(m.context_window):>6}"
                f"  {_free_badge(m):>20}"
                f"  {_tier_badge(m.tier):<18}"
                f"  {vision}"
                f"{added}"
            )
        print()

    _print_section("FREE MODELS", free_models)
    _print_section("PAID MODELS", paid_models)

    # Save discovered list for add command
    cache_path = ROOT / ".discovery_cache.json"
    cache_path.write_text(
        json.dumps([
            {
                "id": m.providers_yaml_id,
                "provider_type": m.provider_type,
                "model_id": m.model_id,
                "display_name": m.display_name,
                "is_free": m.is_free,
                "yaml": m.to_providers_yaml_entry(),
            }
            for m in models
        ], indent=2),
        encoding="utf-8",
    )

    print(f"  {DIM}Tip: Run{RESET}  python manage_providers.py add --id <model-id>")
    print(f"  {DIM}     or{RESET}   python manage_providers.py add --all-free --provider {provider} --key <key>")
    print(f"  {DIM}Results cached in .discovery_cache.json{RESET}\n")


def cmd_add(args: argparse.Namespace) -> None:
    """Add a model (or all free models) to providers.yaml."""
    # All-free shortcut: re-discover and add everything free
    if getattr(args, "all_free", False):
        api_key = args.key or ""
        provider = args.provider or detect_provider_from_key(api_key)
        if not api_key:
            print(f"{RED}Error:{RESET} --key required for --all-free")
            sys.exit(1)
        print(f"\n{BOLD}Discovering + adding all free models from {provider.upper()}...{RESET}")
        try:
            models = discover_models(api_key=api_key, provider=provider)
        except Exception as e:
            print(f"{RED}Discovery failed:{RESET} {e}")
            sys.exit(1)
        free_models = [m for m in models if m.is_free]
        existing_ids = _get_existing_ids()
        added = 0
        for m in free_models:
            if m.providers_yaml_id in existing_ids:
                print(f"  {DIM}Skip (already exists):{RESET} {m.providers_yaml_id}")
                continue
            _append_to_yaml(m)
            print(f"  {GREEN}Added:{RESET} {m.providers_yaml_id}  ({m.display_name})")
            added += 1
        print(f"\n{GREEN}Done.{RESET} {added} free models added to providers.yaml.\n")
        return

    # Single model add
    model_id = getattr(args, "id", None)
    if not model_id:
        print(f"{RED}Error:{RESET} Provide --id <model-id> or use --all-free")
        sys.exit(1)

    # Load from cache
    cache_path = ROOT / ".discovery_cache.json"
    if not cache_path.exists():
        print(f"{RED}Error:{RESET} No discovery cache found. Run 'discover' first.")
        sys.exit(1)

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = next((e for e in cache if e["id"] == model_id), None)
    if not entry:
        # Also try matching by model_id directly
        entry = next((e for e in cache if e["model_id"] == model_id), None)
    if not entry:
        print(f"{RED}Error:{RESET} Model '{model_id}' not found in cache. Run 'discover' first.")
        sys.exit(1)

    existing_ids = _get_existing_ids()
    if entry["id"] in existing_ids:
        print(f"{YELLOW}Already exists:{RESET} {entry['id']} — skipping.")
        return

    # Append to providers.yaml
    _append_raw_yaml(entry["yaml"])
    print(f"\n{GREEN}Added:{RESET} {entry['id']}  ({entry['display_name']})")
    print(f"  Provider: {entry['provider_type'].upper()}")
    print(f"  Free: {GREEN}Yes{RESET}" if entry["is_free"] else f"  Free: {YELLOW}No{RESET}")
    print(f"\n{DIM}Restart agent or call gateway.reload() to use the new provider.{RESET}\n")


def cmd_list(args: argparse.Namespace) -> None:
    """List all providers currently in providers.yaml."""
    if not PROVIDERS_YAML.exists():
        print(f"{RED}providers.yaml not found.{RESET}")
        return

    import yaml
    raw = yaml.safe_load(PROVIDERS_YAML.read_text(encoding="utf-8"))
    providers = raw.get("providers", [])

    print(f"\n{BOLD}{'-'*80}{RESET}")
    print(f"  {BOLD}providers.yaml — {len(providers)} providers{RESET}")
    print(f"{BOLD}{'-'*80}{RESET}\n")
    print(f"  {'ID':<35} {'Model':<45} {'Tier':<12} {'Cost/1M':<12} {'Vision'}")
    print(f"  {'-'*35} {'-'*45} {'-'*12} {'-'*12} {'-'*6}")

    for p in sorted(providers, key=lambda x: x.get("priority", 50)):
        vid = f"{GREEN}Yes{RESET}" if p.get("supports_vision") else f"{DIM}No{RESET}"
        cost = p.get("cost_per_1m_input", 0)
        cost_str = f"{GREEN}FREE{RESET}" if cost == 0 else f"{YELLOW}${cost:.3f}{RESET}"
        print(
            f"  {CYAN}{p['id']:<35}{RESET}"
            f" {p['model']:<45}"
            f" {_tier_badge(p.get('tier','standard')):<20}"
            f" {cost_str:<20}"
            f" {vid}"
        )
    print()


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a provider from providers.yaml by ID."""
    model_id = getattr(args, "id", None)
    if not model_id:
        print(f"{RED}Error:{RESET} --id required")
        sys.exit(1)

    if not PROVIDERS_YAML.exists():
        print(f"{RED}providers.yaml not found.{RESET}")
        return

    import yaml
    raw = yaml.safe_load(PROVIDERS_YAML.read_text(encoding="utf-8"))
    providers = raw.get("providers", [])
    before = len(providers)
    providers = [p for p in providers if p.get("id") != model_id]

    if len(providers) == before:
        print(f"{YELLOW}Not found:{RESET} '{model_id}' not in providers.yaml")
        return

    raw["providers"] = providers
    PROVIDERS_YAML.write_text(
        "# providers.yaml — auto-managed by manage_providers.py\n"
        + yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"{GREEN}Removed:{RESET} {model_id}")


def cmd_reload(args: argparse.Namespace) -> None:
    """Hot-reload providers.yaml into the gateway without restart."""
    try:
        from ultron.core.llm_gateway import default_gateway
        default_gateway.reload()
        providers = default_gateway.get_capable_providers()
        print(f"{GREEN}Reloaded.{RESET} Active providers: {len(providers)}")
        for pid in providers:
            print(f"  {CYAN}{pid}{RESET}")
    except Exception as e:
        print(f"{RED}Reload failed:{RESET} {e}")


# -- YAML helpers --------------------------------------------------------------

def _get_existing_ids() -> set[str]:
    if not PROVIDERS_YAML.exists():
        return set()
    import yaml
    raw = yaml.safe_load(PROVIDERS_YAML.read_text(encoding="utf-8"))
    return {p.get("id", "") for p in raw.get("providers", [])}


def _append_raw_yaml(yaml_block: str) -> None:
    """Append a raw YAML provider block to providers.yaml."""
    content = PROVIDERS_YAML.read_text(encoding="utf-8")
    # Find the last provider entry and append after it
    PROVIDERS_YAML.write_text(content.rstrip() + "\n\n" + yaml_block, encoding="utf-8")


def _append_to_yaml(model: DiscoveredModel) -> None:
    _append_raw_yaml(model.to_providers_yaml_entry())


# -- CLI entry point -----------------------------------------------------------

def main() -> None:
    import io
    import sys
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="manage_providers",
        description="Ultron Provider Manager — discover and manage LLM providers",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # discover
    p_disc = sub.add_parser("discover", help="Discover all models for an API key")
    p_disc.add_argument("--key", "-k", help="API key (or set <PROVIDER>_API_KEY env var)")
    p_disc.add_argument("--provider", "-p", help="Provider: openrouter|gemini|groq|nvidia|together|generic")
    p_disc.add_argument("--base-url", dest="base_url", help="Base URL for generic providers")
    p_disc.add_argument("--free", action="store_true", help="Show only free models")
    p_disc.add_argument("--vision", action="store_true", help="Show only vision-capable models")
    p_disc.add_argument("--tools", action="store_true", help="Show only tool-capable models")
    p_disc.add_argument("--tier", choices=["fast", "reasoning", "standard", "local"], help="Filter by tier")
    p_disc.add_argument("--search", "-s", help="Filter by name/ID substring")

    # add
    p_add = sub.add_parser("add", help="Add a model to providers.yaml")
    p_add.add_argument("--id", help="Provider ID from discover output (e.g. openrouter-deepseek-r1)")
    p_add.add_argument("--all-free", action="store_true", dest="all_free", help="Add ALL free models from a provider")
    p_add.add_argument("--key", "-k", help="API key (required for --all-free)")
    p_add.add_argument("--provider", "-p", help="Provider (required for --all-free)")

    # list
    sub.add_parser("list", help="List all providers in providers.yaml")

    # remove
    p_rem = sub.add_parser("remove", help="Remove a provider from providers.yaml")
    p_rem.add_argument("--id", required=True, help="Provider ID to remove")

    # reload
    sub.add_parser("reload", help="Hot-reload providers.yaml into the running gateway")

    args = parser.parse_args()
    dispatch = {
        "discover": cmd_discover,
        "add": cmd_add,
        "list": cmd_list,
        "remove": cmd_remove,
        "reload": cmd_reload,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
