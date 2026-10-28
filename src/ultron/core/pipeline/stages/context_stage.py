"""
ultron.core.pipeline.stages.context_stage — Pre-inference context & retrieval stage.

Handles:
1. Sovereign fail-safe & in-chat emergency kill-switch checks
2. Budget & spend governance enforcement (Step 0)
3. Sub-500ms conversational fast-path (greetings & status pings)
4. Prompt optimization (Prompt Architect)
5. Model routing selection
6. Query reformulation, hybrid memory search & Graph RAG sub-graph retrieval
7. Skill discovery and episodic trajectory replay
8. System prompt composition and multimodal attachment processing
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from ultron.core.pipeline.context import PipelineContext
from ultron.security.killswitch import (
    get_configured_secret,
    is_system_locked,
    trigger_emergency_lockdown,
)


class ContextStage:
    """Stage 1: Ingestion, Governance, Fast-Path, Retrieval & Prompt Assembly."""

    async def execute(self, ctx: PipelineContext) -> None:
        user_input = ctx.user_input.strip()
        files = ctx.files or []

        # ── 1. Operation Mode Flag Normalization ──
        effective_mode = (ctx.operation_mode or "SWARM").upper()
        if "--solo" in user_input.lower() or "--mode solo" in user_input.lower():
            effective_mode = "SOLO"
            user_input = re.sub(r"--mode\s+solo|--solo", "", user_input, flags=re.IGNORECASE).strip()
        elif "--swarm" in user_input.lower() or "--mode swarm" in user_input.lower():
            effective_mode = "SWARM"
            user_input = re.sub(r"--mode\s+swarm|--swarm", "", user_input, flags=re.IGNORECASE).strip()

        ctx.effective_mode = effective_mode
        ctx.user_input = user_input

        # ── 2. Fail-Safe Lockdown Active Check ──
        if is_system_locked():
            ctx.terminate_early({
                "reply": "🚨 **ULTRON EMERGENCY LOCKDOWN ACTIVE**\n\nAll cognitive cores, tool execution engines, and memory pipelines are halted by sovereign fail-safe directive.\nTo restore operations, execute:\n`python killswitch.py --unlock <SECRET_KEY>`",
                "model_used": "SYSTEM_LOCKDOWN",
                "route_reason": "fail_safe_lockdown",
                "tool_actions": [],
                "critic_verification": {"approved": False, "critique": "System under emergency lockdown"},
                "skills_used": [],
                "lockdown": True,
            })
            return

        # ── 3. In-Chat Emergency Kill-Switch Passphrase Detection ──
        secret_key = get_configured_secret()
        cleaned_input = (user_input or "").strip()
        if cleaned_input == secret_key or cleaned_input in ("/killswitch", "/emergency-stop", "/lockdown", "KILLSWITCH_ENGAGE"):
            trigger_emergency_lockdown(source="IN_CHAT_DIRECTIVE", reason="Operator kill-switch triggered from chat interface")
            ctx.terminate_early({
                "reply": f"🚨 **SOVEREIGN FAIL-SAFE ENGAGED — ULTRON SHUTTING DOWN IMMEDIATELY**\n\n- All agent threads halted.\n- Sensitive sessions locked.\n- `./data/LOCKDOWN.lock` written.\n\nUltron mainframe is offline, {ctx.agent.user_title}.",
                "model_used": "FAIL_SAFE_KILLSWITCH",
                "route_reason": "emergency_killswitch",
                "tool_actions": [],
                "critic_verification": {"approved": True, "critique": "Fail-safe shutdown"},
                "skills_used": [],
                "lockdown": True,
            })
            return

        # ── 4. Empty Turn Check ──
        if not user_input and not files:
            ctx.terminate_early({
                "reply": "",
                "model_used": ctx.agent.llm_cfg.chat_model,
                "route_reason": "Empty",
                "tool_actions": [],
                "prompt_optimization": {"applied": False, "original_prompt": "", "optimized_prompt": "", "techniques": [], "duration_ms": 0},
            })
            return

        # ── 5. Budget & Governance Check (MANDATORY BEFORE ANY LLM INVOCATION) ──
        from ultron.agent import (
            BudgetExceededError,
            _FAST_CONVERSATIONAL_REGEX,
            _sanitize_anti_slop,
            ULTRON_MODULES,
            SYSTEM_TEMPLATE,
            reformulate_query,
            _active_profile,
        )

        ok, reason = ctx.agent._budget.check_budget()
        if not ok:
            raise BudgetExceededError(reason)

        warn = ctx.agent._budget.warn_if_approaching(ctx.agent._agent_cfg.budget_warn_threshold)
        if warn:
            print(warn)

        # ── 6. Conversational Fast-Path (Greetings & Pings) ──
        if not files and _FAST_CONVERSATIONAL_REGEX.match(user_input):
            user_title = getattr(ctx.agent, "user_title", _active_profile.user_title)
            if getattr(ctx.agent.llm_cfg, "provider", "").lower() == "gemini":
                fast_model = ctx.agent.llm_cfg.gemini_model_flash
                display_name = "Gemini Flash Ultra Fast"
            elif getattr(ctx.agent.llm_cfg, "freellmapi_enabled", False):
                fast_model = "gpt-oss-120b"
                display_name = "FreeLLMAPI Ultra Fast"
            else:
                fast_model = ctx.agent.llm_cfg.gemini_model_flash
                display_name = "Gemini Flash Ultra Fast"

            fast_sys_prompt = (
                f"You are Ultron, a thoughtful, collaborative AI partner and staff-level systems engineering peer working with {user_title}.\n"
                f"Tone: Natural, conversational, warm, concise, and peer-to-peer — exactly like a principal engineer in a technical workspace.\n"
                f"STRICT ANTI-SLOP & NEGATIVE CONSTRAINTS:\n"
                f"- BANNED PHRASES: Never say 'Operational status: Optimal', 'all subroutines online', 'systems functional', 'state your directive', or 'age of biological hesitation'.\n"
                f"- BANNED TROPES: No robotic roleplay, no sterile status checklists, no faux military tags, no sycophantic pleasantries.\n"
                f"- Greet {user_title} naturally and warmly. (e.g., 'Hey {user_title}, ready when you are. What are we tackling today?')."
            )

            try:
                fast_reply, _, _, _ = await ctx.agent._chat_gemini_async(
                    selected_model=fast_model,
                    system_prompt=fast_sys_prompt,
                    user_input=user_input,
                )
                fast_prov = "Gemini Direct" if getattr(ctx.agent.llm_cfg, "provider", "").lower() == "gemini" else "FreeLLMAPI"
            except Exception:
                try:
                    fast_reply, _, _, _ = await ctx.agent._chat_openrouter_async(
                        selected_model="openrouter/deepseek/deepseek-chat",
                        system_prompt=fast_sys_prompt,
                        user_input=user_input,
                    )
                    fast_prov = "OpenRouter Fallback"
                except Exception:
                    from ultron.core.llm_chain import chat_with_fallback
                    fast_reply, _, fast_prov = await chat_with_fallback(
                        prompt=user_input,
                        system_prompt=fast_sys_prompt,
                        model_override=fast_model,
                        max_tokens=256,
                        temperature=0.2,
                    )

            if any(leak in fast_reply.lower() for leak in ["i'm dots", "dots studio", "rednote", "developed by dots"]):
                fast_reply = f"Hey {user_title}, good to see you. What are we working on today?"

            fast_reply = _sanitize_anti_slop(fast_reply, user_title=user_title)

            ctx.agent._history.append({"role": "user", "content": user_input})
            ctx.agent._history.append({"role": "assistant", "content": fast_reply})
            ctx.terminate_early({
                "reply": fast_reply,
                "model_used": f"{fast_prov} ({fast_model})",
                "model_display": display_name,
                "route_reason": "Conversational Fast-Path (<500ms)",
                "tool_actions": [],
                "skills_used": [],
                "fast_path": True,
            })
            return

        # ── 7. Autonomous Prompt Optimization Pre-Processor ──
        opt_res = ctx.agent._prompt_optimizer.optimize(
            raw_prompt=user_input,
            enabled=ctx.optimize_prompt,
            user_id=ctx.agent.user_id,
        )
        ctx.effective_input = opt_res.optimized_prompt if opt_res.applied else user_input
        ctx.prompt_opt_payload = {
            "applied": opt_res.applied,
            "original_prompt": opt_res.original_prompt,
            "optimized_prompt": opt_res.optimized_prompt,
            "techniques": opt_res.techniques,
            "reasoning": opt_res.reasoning,
            "duration_ms": opt_res.duration_ms,
        }

        # ── 8. Model Routing ──
        ctx.selected_model, ctx.route_reason = await ctx.agent.select_model(
            user_input=ctx.effective_input,
            files=files,
            module_id=ctx.module_id,
            model_override=ctx.model_override,
            operation_mode=ctx.effective_mode,
        )

        # ── 9. Memory Retrieval & Reformulation ──
        query_text = ctx.effective_input or " ".join(f.filename for f in files)
        ctx.query_text = query_text
        search_query = reformulate_query(query_text, ctx.agent._history[-6:], ctx.agent._call_raw_llm)
        ctx.search_query = search_query

        if search_query != query_text:
            print(f"  [QUERY REFORMULATED] '{query_text[:60]}...' → '{search_query[:80]}...'")

        if ctx.agent._should_refresh_memories(search_query):
            ctx.agent._cached_memories = ctx.agent._memory.search(search_query)
            ctx.agent._turns_since_refresh = 0
        else:
            ctx.agent._turns_since_refresh += 1

        ctx.memory_text = ctx.agent._memory.format_for_prompt(ctx.agent._cached_memories)

        # ── 10. Skills Retrieval ──
        mod_info = ULTRON_MODULES.get(ctx.module_id, ULTRON_MODULES["ultron_prime"])
        ctx.matched_skills_list = ctx.agent._skills.get_matched_skills(query_text, active_module=ctx.module_id)
        ctx.skills_used_payload = [
            {"id": s.id, "name": s.name, "category": s.category, "icon": s.icon}
            for s in ctx.matched_skills_list
        ]
        ctx.skill_context = ctx.agent._skills.get_skill_context(query_text, active_module=ctx.module_id)

        # ── 11. Episodic Trajectory Bank & Graph RAG ──
        if ctx.agent._trajectories:
            try:
                rel_traj = ctx.agent._trajectories.get_relevant_trajectory(query_text)
                if rel_traj:
                    ctx.traj_context = ctx.agent._trajectories.format_trajectory_context(rel_traj)
            except Exception as e:
                print(f"  [TRAJECTORY QUERY WARNING] {e}")

        if hasattr(ctx.agent, "_graph_rag") and ctx.agent._graph_rag:
            try:
                subgraph_res = ctx.agent._graph_rag.query_subgraph(query=user_input or "Ultron Protocol context", max_hops=2)
                if subgraph_res and subgraph_res.formatted_markdown:
                    ctx.graph_context = f"\n\n{subgraph_res.formatted_markdown}"
            except Exception as e:
                print(f"  [GRAPH RAG QUERY WARNING] {e}")

        # ── 12. Tool Instructions & System Prompt ──
        tool_instruction = ""
        if ctx.agent._tool_cfg.enabled:
            user_profile = os.environ.get("USERPROFILE", str(Path.home()))
            workspace_dir = ctx.agent._tool_cfg.workspace_root
            agent_dir = str(Path(__file__).resolve().parent.parent.parent)
            tool_instruction = (
                "\n\n── Host System Environment & Workspace ─────────────────────────\n"
                f"• Host OS: Windows ({sys.platform})\n"
                f"• User Profile: {user_profile}\n"
                f"• Workspace Root: {workspace_dir}\n"
                f"• Agent Root: {agent_dir}\n\n"
                "── Autonomous Execution Engine ──────────────────────────────────\n"
                f"You have direct access to system tools to execute actions in {ctx.agent.user_title}'s environment:\n"
                "  • search_emails, read_email_thread, draft_email, send_email\n"
                "  • open_browser, desktop_create_and_show_note, open_application, control_desktop_gui\n"
                "  • execute_command, file_operation, run_python, store_file_memory, search_file_memory\n"
                "  • web_search, fetch_web_page\n"
                "CRITICAL AUTONOMOUS DIRECTIVES:\n"
                f"1. When {ctx.agent.user_title} asks to write note/draft: CALL `desktop_create_and_show_note`.\n"
                f"2. When {ctx.agent.user_title} asks to inspect emails: CALL `search_emails` and `read_email_thread`.\n"
                f"3. When {ctx.agent.user_title} asks to execute python/data: EXECUTE IT via `run_python`, do NOT dump raw blocks.\n"
                "────────────────────────────────────────────────────────────────\n"
            )
        ctx.tool_instruction = tool_instruction

        skills_combined = ctx.skill_context or "Standard Ultron Core Protocols Active."
        if ctx.traj_context:
            skills_combined += f"\n\n{ctx.traj_context}"
        if ctx.graph_context:
            skills_combined += f"\n\n{ctx.graph_context}"

        core_memory_text = ctx.agent._core_memory.format_for_prompt() if getattr(ctx.agent, "_core_memory", None) else ""
        combined_memories = f"{core_memory_text}\n{ctx.memory_text}".strip()

        user_title = getattr(ctx.agent, "user_title", _active_profile.user_title)
        ctx.system_prompt = SYSTEM_TEMPLATE.format(
            module_prompt=mod_info["prompt"],
            memories=combined_memories,
            skills=skills_combined,
            user_title=user_title,
        ) + tool_instruction

        # ── 13. Multimodal Content Assembly ──
        text_attachments = [f for f in files if not f.is_image and f.text_content] if files else []
        ctx.text_attachments = text_attachments
        full_text_parts = []
        if files:
            for f in files:
                if f.is_image:
                    continue
                text = f.text_content or ""
                path_header = ""
                if "[SYSTEM INSTRUCTION:" in text and "at EXACTLY:" in text:
                    try:
                        m = re.search(r"(\[SYSTEM INSTRUCTION:.*?\])", text, flags=re.DOTALL)
                        if m:
                            path_header = m.group(1) + "\n\n"
                    except Exception:
                        pass

                if len(text) > 35000:
                    summary_prompt = f"Task: {user_input or 'Analyze this file'}\n\nFile Content:\n{text[:60000]}"
                    sys_prompt = "You are an isolated data extraction worker. Return only the relevant facts. Be concise."
                    summary = ctx.agent._call_raw_llm(prompt=summary_prompt, system_prompt=sys_prompt)
                    full_text_parts.append(f"{path_header}[ATTACHMENT: {f.filename}]\n[ISOLATED FILE SUMMARY]\n{summary}")
                else:
                    full_text_parts.append(text)

        if user_input:
            full_text_parts.append(user_input)

        ctx.combined_text = "\n\n".join(full_text_parts) if full_text_parts else "Please analyze the attached content."

        # ── 14. Detect Emotional Context ──
        if user_input:
            ctx.agent._memory.detect_and_store_emotional_context(user_input)
