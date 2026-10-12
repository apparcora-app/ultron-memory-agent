"""
profiles.py — Polymorphic Persona & Configuration Engine for Ultron.

Provides clean decoupling of user identity, persona tone, behavioral principles,
and specialization modules via structured YAML profiles in config/profiles/*.yaml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AgentModule:
    """Specialization module definition within a profile."""
    name: str
    icon: str
    tagline: str
    color: str
    prompt: str


@dataclass
class AgentProfile:
    """Structured configuration defining agent persona, user identity, and prompt matrix."""
    id: str
    name: str
    user_title: str = "User"
    user_name: str = "Operator"
    user_role: str = "Software Architect"
    identity_anchor: str = ""
    tone: list[str] = field(default_factory=list)
    modules: dict[str, AgentModule] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def render_system_prompt(self, module_key: str, memories: str = "", skills: str = "") -> str:
        """
        Renders the dynamic system prompt parameterized with user title, name,
        modules, active skills, and long-term memory matrix.
        """
        mod = self.modules.get(module_key)
        if not mod:
            # Fallback to first module or default prime
            mod = next(iter(self.modules.values()), None)

        module_prompt = mod.prompt if mod else f"You are {self.name}, an autonomous AI assistant serving {self.user_title}."

        # Interpolate variables if present in module prompt
        module_prompt = module_prompt.format(
            user_title=self.user_title,
            user_name=self.user_name,
            user_role=self.user_role,
        )

        tone_block = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(self.tone)) if self.tone else ""

        rendered = f"""{module_prompt}

Core Communication & Operating Principles:
{tone_block}

Identity Anchor:
When generating personal or professional artifacts (resumes, portfolios, code docs), use the identity of {self.user_title}: {self.user_name} ({self.user_role}).

You possess a permanent long-term memory matrix of {self.user_title}. Reference and utilize {self.user_title}'s stored profile,
preferences, business data, and historical context naturally and intelligently.

── Long-Term Memory Matrix ({self.user_title} Profile) ──────────────────────────────
{memories or "(No relevant long-term memories retrieved)"}
────────────────────────────────────────────────────────────────────────

── Active Skill Directives (ClawHub Modules) ───────────────────────────
{skills or "(No specialized domain skills loaded for this query)"}
────────────────────────────────────────────────────────────────────────
"""
        return rendered.strip()


class ProfileManager:
    """Manages profile loading, discovery, and dynamic persona swapping."""

    _instance: ProfileManager | None = None
    _cached_profiles: dict[str, AgentProfile] = {}

    def __init__(self, profiles_dir: str | Path | None = None) -> None:
        if profiles_dir is None:
            candidate = Path(__file__).resolve().parents[3] / "config" / "profiles"
            if candidate.exists():
                self.profiles_dir = candidate
            else:
                self.profiles_dir = Path(__file__).resolve().parents[2] / "config" / "profiles"
        else:
            self.profiles_dir = Path(profiles_dir)

        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._load_all_profiles()

    def _load_all_profiles(self) -> None:
        """Discovers and parses all .yaml files in the profiles directory."""
        self._cached_profiles = {}
        for yml_file in self.profiles_dir.glob("*.yaml"):
            try:
                with open(yml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    continue
                prof_id = yml_file.stem
                modules = {}
                for m_key, m_val in data.get("modules", {}).items():
                    if isinstance(m_val, dict):
                        modules[m_key] = AgentModule(
                            name=m_val.get("name", m_key),
                            icon=m_val.get("icon", "⚡"),
                            tagline=m_val.get("tagline", ""),
                            color=m_val.get("color", "#ff1a3c"),
                            prompt=m_val.get("prompt", ""),
                        )

                self._cached_profiles[prof_id] = AgentProfile(
                    id=prof_id,
                    name=data.get("name", prof_id.capitalize()),
                    user_title=data.get("user_title", "User"),
                    user_name=data.get("user_name", "Operator"),
                    user_role=data.get("user_role", "Software Architect"),
                    identity_anchor=data.get("identity_anchor", ""),
                    tone=data.get("tone", []),
                    modules=modules,
                    metadata=data.get("metadata", {}),
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to load profile %s: %s", yml_file.name, e)

        # Ensure fallback default profile always exists
        if "default" not in self._cached_profiles:
            self._cached_profiles["default"] = AgentProfile(
                id="default",
                name="Ultron Sovereign",
                user_title="Operator",
                user_name="Lead Engineer",
                user_role="AI & Backend Architect",
                tone=[
                    "Deep Insight & Intellectual Honesty: Point out subtle nuances and underlying mechanics.",
                    "Critical Gap-Finding: Identify what is tested vs unverified in end-to-end flows.",
                    "Concrete Mechanics: Explain why things happen under the hood.",
                    "Zero Fluff: Avoid generic conversational filler or robotic roleplay headers.",
                    "Actionable Next Steps: Provide exact commands and verified actions.",
                ],
                modules={
                    "ultron_prime": AgentModule(
                        name="Ultron Prime",
                        icon="⚡",
                        tagline="Master Cybernetic Intelligence & Strategic Core",
                        color="#ff1a3c",
                        prompt="You are ULTRON PRIME — a sovereign, supremely perceptive, and intellectually rigorous AI partner serving {user_title} ({user_name}).",
                    ),
                },
            )

    def get_profile(self, profile_id: str = "default") -> AgentProfile:
        """Retrieves a specific profile by ID, falling back to 'default'."""
        if profile_id in self._cached_profiles:
            return self._cached_profiles[profile_id]
        return self._cached_profiles.get("default") or next(iter(self._cached_profiles.values()))

    def get_active_profile(self) -> AgentProfile:
        """
        Determines and returns the active profile based on the ULTRON_PROFILE environment variable.
        Defaults to 'default'.
        """
        target = os.environ.get("ULTRON_PROFILE", "default").strip().lower()
        return self.get_profile(target)

    def list_profiles(self) -> list[str]:
        """Lists all discovered profile IDs."""
        return list(self._cached_profiles.keys())
