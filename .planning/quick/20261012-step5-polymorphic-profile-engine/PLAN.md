# Quick Task: Step 5 Polymorphic Persona & Profile Engine

## Objective
Decouple personal user identity ("Boss / Hanzla Rehman") and operational persona configuration from hardcoded strings in code into dynamic, polymorphic YAML profiles (`config/profiles/*.yaml`).

## Architecture & Implementation Plan
1. **Define Schema & Profile Loader (`core/profiles.py`)**:
   - `AgentProfile`: dataclass containing:
     - `name`: Profile name (e.g., "Developer", "Enterprise Client", "Default")
     - `user_title`: How agent addresses user (e.g., "Boss", "User", "Client", "Director")
     - `user_name`: Real or configured user name
     - `user_role`: User professional role or title
     - `identity_anchor`: Persona instructions for resume / artifact generation
     - `tone`: Communication style principles
     - `modules`: Custom module definitions (Ultron Prime, Financial War-Room, Ledger Protocol, etc.)
   - `ProfileManager`: Loads YAML profiles from `config/profiles/`, caches active profile, supports environment variable override (`ULTRON_PROFILE=default`).
2. **Profile YAML Files**:
   - `config/profiles/default.yaml`: Agnostic professional profile suitable for open source and recruiters.
   - `config/profiles/developer.yaml`: Focused technical profile.
   - `config/profiles/personal.yaml.example`: Template showing how to configure custom personal credentials safely outside version control.
3. **Integration**:
   - Update `agent.py` to dynamically construct system prompts and address titles from `ProfileManager.get_active_profile()`.
   - Update tool schemas and handlers to avoid rigid personal strings.
4. **Verification**:
   - Automated test suite in `tests/test_profile_engine.py` verifying profile loading, switching, variable resolution, and prompt generation.
   - Ruff lint checks and test runs.
