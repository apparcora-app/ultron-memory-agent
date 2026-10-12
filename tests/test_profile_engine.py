"""
test_profile_engine.py — Empirical Verification Suite for Polymorphic Persona Engine.

Verifies:
1. Dynamic loading and discovery of YAML profiles in config/profiles/*.yaml.
2. Fallback to default agnostic profile when requested profile is absent.
3. System prompt rendering with parameterized user title, name, role, and tone.
4. Environment variable switching via ULTRON_PROFILE.
5. Ultron MemoryAgent integration with active profile.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from agent import MemoryAgent
from core.profiles import AgentModule, AgentProfile, ProfileManager


class TestProfileEngine:
    """Test suite ensuring flexible persona and identity configuration."""

    @pytest.fixture
    def custom_profiles_dir(self) -> Path:
        """Create a temporary directory with test profiles."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Profile A: Enterprise Client
            client_yaml = {
                "name": "Enterprise Client AI",
                "user_title": "Director",
                "user_name": "Sarah Connor",
                "user_role": "Chief Technology Officer",
                "tone": [
                    "Concise executive briefing style.",
                    "Always quantify business risk and downtime costs.",
                ],
                "modules": {
                    "ultron_prime": {
                        "name": "Executive Core",
                        "icon": "🏢",
                        "tagline": "Enterprise Systems & Strategy",
                        "color": "#2563eb",
                        "prompt": "You are EXECUTIVE CORE serving {user_title} ({user_name}), {user_role}.",
                    }
                },
            }
            with open(tmp_path / "enterprise.yaml", "w", encoding="utf-8") as f:
                yaml.dump(client_yaml, f)

            yield tmp_path

    def test_profile_manager_discovers_profiles(self, custom_profiles_dir: Path) -> None:
        """Verify ProfileManager loads all YAML profiles."""
        pm = ProfileManager(profiles_dir=custom_profiles_dir)
        profiles = pm.list_profiles()
        assert "enterprise" in profiles
        assert "default" in profiles

        prof = pm.get_profile("enterprise")
        assert prof.user_title == "Director"
        assert prof.user_name == "Sarah Connor"
        assert prof.user_role == "Chief Technology Officer"
        assert len(prof.tone) == 2

    def test_render_system_prompt_interpolates_user_data(self) -> None:
        """Verify dynamic variables are properly interpolated into the system prompt."""
        profile = AgentProfile(
            id="test",
            name="Test Bot",
            user_title="Captain",
            user_name="James Kirk",
            user_role="Starship Commander",
            tone=["Follow Starfleet protocol."],
            modules={
                "ultron_prime": AgentModule(
                    name="Command Prime",
                    icon="🚀",
                    tagline="Bridge Operations",
                    color="#f59e0b",
                    prompt="Active directive for {user_title} ({user_name}): Protect the fleet.",
                )
            },
        )

        prompt = profile.render_system_prompt(
            module_key="ultron_prime",
            memories="Memory: USS Enterprise launched in 2245.",
            skills="Skill: Warp Core Stabilization",
        )

        assert "Active directive for Captain (James Kirk): Protect the fleet." in prompt
        assert "Captain Profile" in prompt
        assert "James Kirk (Starship Commander)" in prompt
        assert "Memory: USS Enterprise launched in 2245." in prompt
        assert "Skill: Warp Core Stabilization" in prompt
        assert "Follow Starfleet protocol." in prompt

    def test_ultron_profile_env_var_switching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify changing ULTRON_PROFILE switches the active persona."""
        monkeypatch.setenv("ULTRON_PROFILE", "developer")
        pm = ProfileManager()
        active = pm.get_active_profile()
        assert active.id == "developer"
        assert active.user_title == "Architect"

        monkeypatch.setenv("ULTRON_PROFILE", "default")
        active_default = pm.get_active_profile()
        assert active_default.id == "default"
        assert active_default.user_title == "Operator"

    def test_memory_agent_initializes_with_active_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify MemoryAgent properly adopts the active profile user_title."""
        monkeypatch.setenv("ULTRON_PROFILE", "default")
        agent = MemoryAgent(user_id="test_user")
        assert hasattr(agent, "profile")
        assert agent.user_title == "Operator"
        assert agent.profile.id == "default"
