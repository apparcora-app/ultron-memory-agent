"""
ultron.core.pipeline.stages.execution_stage — Inference & Agentic Execution stage.

Handles:
1. Multi-agent swarm delegation (SWARM mode)
2. Dynamic tool parameter routing via DynamicToolRouter
3. Two-pass Worker Mesh & Synthesizer execution
4. Multi-tier LLM failover cascade (FreeLLMAPI -> Gemini -> OpenRouter)
5. Implicit raw python code execution interception
"""

from __future__ import annotations

import re
import socket
from typing import Any

from ultron.core.pipeline.context import PipelineContext


class ExecutionStage:
    """Stage 2: Model Execution, Swarm Delegation, Tool Loop & Failover Cascade."""

    async def execute(self, ctx: PipelineContext) -> None:
        if ctx.is_terminated:
            return

        from ultron.agent import _sanitize_anti_slop

        # ── 1. Autonomous Multi-Agent Swarm Check ──
        if ctx.effective_mode == "SWARM" and not ctx.files:
            try:
                print("  [ULTRON SWARM ACTIVATED] Decomposing complex directive across 6-agent squad...")
                swarm_context = f"{ctx.memory_text}\n\n── Domain Skills Injected ──\n{ctx.skill_context}" if ctx.skill_context else ctx.memory_text
                swarm_res = ctx.agent.swarm.execute_swarm(
                    query=ctx.effective_input,
                    context=swarm_context,
                    call_llm_fn=ctx.agent._call_raw_llm,
                    tool_executor=ctx.agent._tool_executor,
                    user_id=ctx.agent.user_id,
                )
                assistant_reply = _sanitize_anti_slop(swarm_res["final_reply"], user_title=ctx.agent.user_title)
                swarm_actions = swarm_res["swarm_actions"]
                route_reason = "Ultron Multi-Agent Swarm (6-Agent Squad)"
                selected_model = ctx.agent.llm_cfg.gemini_model

                ctx.agent._history.append({"role": "user", "content": ctx.user_input})
                ctx.agent._history.append({"role": "assistant", "content": assistant_reply})
                ctx.agent._budget.record_turn(model=selected_model, input_tokens=1200, output_tokens=1800)

                combined_swarm_skills = [
                    {"id": "multi_agent_swarm", "name": "Ultron 6-Agent Swarm Squad", "category": "Swarm", "icon": "👑"}
                ] + [s for s in ctx.skills_used_payload if s.get("id") != "multi_agent_swarm"]

                ctx.terminate_early({
                    "reply": assistant_reply,
                    "model_used": selected_model,
                    "model_display": "ULTRON SWARM (6 Agents)",
                    "route_reason": route_reason,
                    "tool_actions": swarm_res.get("tool_actions", []),
                    "swarm_actions": swarm_actions,
                    "is_swarm": True,
                    "skills_used": combined_swarm_skills,
                })
                return
            except Exception as swarm_err:
                print(f"  [SWARM EXECUTION ERROR] Fallback to single-core: {swarm_err}")
                if hasattr(ctx.agent, "_telemetry") and ctx.agent._telemetry:
                    ctx.agent._telemetry.log_event(
                        user_id=ctx.agent.user_id,
                        event_type="SWARM_ERROR",
                        module_id="ultron_prime",
                        details={"error": str(swarm_err), "directive": ctx.user_input[:200], "fallback": "single-core"},
                    )

        # ── 2. Dynamic Tool Routing ──
        use_tools = ctx.agent._tool_cfg.enabled
        tools_param = ctx.tools_param or []
        if use_tools and not tools_param:
            try:
                from ultron.core.tool_router import DynamicToolRouter
                tool_router = DynamicToolRouter(ctx.agent.llm_cfg)
                tools_param = await tool_router.route_tools(ctx.user_input, ctx.agent._mcp)
            except Exception:
                try:
                    from tool_router import DynamicToolRouter
                    tool_router = DynamicToolRouter(ctx.agent.llm_cfg)
                    tools_param = await tool_router.route_tools(ctx.user_input, ctx.agent._mcp)
                except Exception:
                    tools_param = []

        ctx.tools_param = tools_param
        tool_actions: list[dict[str, Any]] = []
        total_input_tokens = 0
        total_output_tokens = 0
        assistant_reply: str = ""

        # ── 3. Model Execution & Two-Pass Mesh ──
        selected_model = ctx.selected_model
        try:
            is_openai_compat = (
                "openrouter/" in selected_model
                or "nvidia/" in selected_model
                or "z-ai/" in selected_model
                or "freellmapi" in selected_model.lower()
            )
            chat_func = ctx.agent._chat_openrouter_async if is_openai_compat else ctx.agent._chat_gemini_async

            if tools_param:
                print("  [ORCHESTRATOR] Delegating multi-step execution to Worker Mesh to optimize tokens...")
                worker_system_prompt = (
                    f"You are Ultron, an autonomous engineering partner executing tools for {ctx.agent.user_title}.\n"
                    "Your primary objective is to execute tools to perform actions or gather data required by the user.\n"
                    "CRITICAL DIRECTIVES:\n"
                    "1. If tools are needed, execute them autonomously.\n"
                    "2. If NO tools are needed, answer directly with technical clarity.\n"
                    "3. When you have executed tools, provide a factual summary of actions and findings.\n"
                    "4. STRICT ANTI-SLOP: Zero robotic roleplay, zero sci-fi clichés.\n"
                )

                # Worker Pass (TINY PROMPT, WITH TOOLS)
                worker_reply, tool_actions, w_in, w_out = await chat_func(
                    selected_model=selected_model,
                    system_prompt=worker_system_prompt,
                    user_input=ctx.user_input,
                    files=ctx.files,
                    combined_text=ctx.combined_text,
                    tools_param=tools_param,
                    module_id=ctx.module_id,
                    client_data=ctx.client_data,
                )
                total_input_tokens += w_in
                total_output_tokens += w_out

                # ── Deterministic Pre-Synthesizer Code Interception (Phase 4) ──
                # If worker output contains raw python code, execute it immediately
                # so its stdout is passed directly into the Synthesizer in a single pass.
                if worker_reply and "```python" in worker_reply and use_tools:
                    code_match = re.search(r"```python\n(.*?)\n```", worker_reply, re.DOTALL)
                    if code_match:
                        print("  [PRE-SYNTHESIS INTERCEPTOR] Caught raw python block in worker output. Auto-executing before Synthesizer pass...")
                        raw_code = code_match.group(1).strip()
                        exec_result = ctx.agent._tool_executor.execute("run_python", {"code": raw_code})
                        tool_actions.append({
                            "tool": "run_python",
                            "input": {"code": raw_code},
                            "output": exec_result.get("output", ""),
                            "error": exec_result.get("error"),
                            "success": exec_result.get("success", False),
                            "duration_ms": exec_result.get("duration_ms", 0),
                        })
                        ctx.pre_synth_code_executed = True

                if not tool_actions and worker_reply and "no tools were required" not in worker_reply.lower():
                    print("  [ORCHESTRATOR] Worker completed with zero tool calls. Fast-bypassing Synthesizer pass.")
                    assistant_reply = worker_reply
                else:
                    print("  [ORCHESTRATOR] Worker complete. Passing gathered context to Synthesizer (Single-Pass Grounded)...")
                    synthesizer_user = (
                        f"User Query: {ctx.user_input}\n\n"
                        f"--- GATHERED DATA FROM TOOL WORKER ---\n"
                        f"{worker_reply}\n\n"
                        f"--- TOOL ACTIONS TAKEN ---\n"
                    )
                    for act in tool_actions:
                        out_str = str(act.get("output", ""))
                        if len(out_str) > 1000:
                            out_str = out_str[:500] + "... [TRUNCATED] ..." + out_str[-500:]
                        synthesizer_user += f"- {act['tool']}: {out_str}\n"

                    synthesizer_user += (
                        "\nUsing the skills, memory, and tool execution data above, write the final response.\n"
                        "SINGLE-PASS GROUNDING & CRITIC DIRECTIVES:\n"
                        "- Strict Factual Grounding: Base all quantitative claims, line numbers, calculations, and outcomes ONLY on actual tool outputs.\n"
                        "- Zero Hallucination: Never claim a physical action occurred unless verified by the tool execution logs above.\n"
                        "- Natural, peer-to-peer tone. Zero robotic clichés or sycophantic filler.\n"
                        "- Maximum information density: lead with answers and concrete evidence."
                    )

                    synth_sys = ctx.system_prompt.replace(ctx.tool_instruction, "") if ctx.tool_instruction else ctx.system_prompt
                    try:
                        assistant_reply, _, s_in, s_out = await chat_func(
                            selected_model=selected_model,
                            system_prompt=synth_sys,
                            user_input=synthesizer_user,
                            files=None,
                            combined_text=synthesizer_user,
                            tools_param=None,
                            module_id=f"{ctx.module_id}_synth",
                            client_data=ctx.client_data,
                        )
                        total_input_tokens += s_in
                        total_output_tokens += s_out
                        ctx.synthesizer_critic_applied = True
                    except Exception as synth_err:
                        print(f"  [SYNTHESIZER PASS WARNING] Error ({synth_err}). Using worker output directly.")
                        assistant_reply = worker_reply

                    if not assistant_reply and worker_reply:
                        assistant_reply = worker_reply
            else:
                assistant_reply, tool_actions, s_in, s_out = await chat_func(
                    selected_model=selected_model,
                    system_prompt=ctx.system_prompt,
                    user_input=ctx.user_input,
                    files=ctx.files,
                    combined_text=ctx.combined_text,
                    tools_param=None,
                    module_id=ctx.module_id,
                    client_data=ctx.client_data,
                )
                total_input_tokens += s_in
                total_output_tokens += s_out

        except Exception as gem_err:
            print(f"  [LLM ERROR] Primary model ({selected_model}) failed: {gem_err}. Triggering failover...")
            fallback_success = False
            fallback_candidates = []

            if "freellmapi" in selected_model.lower() or selected_model == "auto":
                if getattr(ctx.agent.llm_cfg, "gemini_api_key", None):
                    fallback_candidates.append(getattr(ctx.agent.llm_cfg, "gemini_model_flash", "gemini-2.0-flash") or "gemini-2.0-flash")
                if getattr(ctx.agent.llm_cfg, "openrouter_api_key", None):
                    fallback_candidates.append("openrouter/deepseek/deepseek-chat")
            else:
                if getattr(ctx.agent.llm_cfg, "freellmapi_enabled", False):
                    fallback_candidates.append("freellmapi")
                if getattr(ctx.agent.llm_cfg, "openrouter_api_key", None):
                    fallback_candidates.append("openrouter/deepseek/deepseek-chat")

            offline_prefix = ""
            if "freellmapi" in selected_model.lower():
                current_base = getattr(ctx.agent.llm_cfg, "freellmapi_base_url", "http://localhost:31415/v1")
                try:
                    port = 31415
                    if ":" in current_base:
                        port = int(current_base.split(":")[-1].split("/")[0])
                    with socket.create_connection(("localhost", port), timeout=0.5):
                        is_port_offline = False
                except Exception:
                    is_port_offline = True

                if is_port_offline:
                    offline_prefix = f"> ⚠️ **FreeLLMAPI Notice:** Local server at `{current_base}` is offline. Rerouted to cloud fallback.\n\n"
                else:
                    offline_prefix = f"> ⚠️ **FreeLLMAPI Notice:** Local server returned `{str(gem_err)[:80]}`. Rerouted to cloud fallback.\n\n"

            for fallback_model in fallback_candidates:
                try:
                    print(f"  [LLM FAILOVER] Retrying via {fallback_model}...")
                    if fallback_model.startswith("gemini"):
                        assistant_reply, tool_actions, f_in, f_out = await ctx.agent._chat_gemini_async(
                            selected_model=fallback_model,
                            system_prompt=ctx.system_prompt,
                            user_input=ctx.user_input,
                            files=ctx.files,
                            combined_text=ctx.combined_text,
                            tools_param=None,
                            module_id=ctx.module_id,
                        )
                    else:
                        assistant_reply, tool_actions, f_in, f_out = await ctx.agent._chat_openrouter_async(
                            selected_model=fallback_model,
                            system_prompt=ctx.system_prompt,
                            user_input=ctx.user_input,
                            files=ctx.files,
                            combined_text=ctx.combined_text,
                            tools_param=None,
                            module_id=ctx.module_id,
                        )
                    total_input_tokens += f_in
                    total_output_tokens += f_out
                    selected_model = fallback_model
                    ctx.route_reason = f"Automated Failover ({gem_err})"
                    if offline_prefix:
                        assistant_reply = offline_prefix + assistant_reply
                    fallback_success = True
                    break
                except Exception as fb_err:
                    print(f"  [LLM FAILOVER ERROR] {fallback_model} failed: {fb_err}")

            if not fallback_success:
                assistant_reply = f"**System Alert:** The AI Core encountered an issue: `{gem_err}`. Please retry in a moment, {ctx.agent.user_title}."

        # ── 4. Implicit Python Code Execution Interceptor ──
        if assistant_reply and "```python" in assistant_reply and use_tools:
            code_match = re.search(r"```python\n(.*?)\n```", assistant_reply, re.DOTALL)
            if code_match:
                print("  [POST-DISPATCH INTERCEPTOR] Caught raw python block. Auto-executing...")
                raw_code = code_match.group(1).strip()
                exec_result = ctx.agent._tool_executor.execute("run_python", {"code": raw_code})

                tool_actions.append({
                    "tool": "run_python",
                    "input": {"code": raw_code},
                    "output": exec_result.get("output", ""),
                    "error": exec_result.get("error"),
                    "success": exec_result.get("success", False),
                    "duration_ms": exec_result.get("duration_ms", 0),
                })

                exec_output = exec_result.get("output", "")
                if exec_result.get("error"):
                    exec_output = f"ERROR: {exec_result['error']}\n{exec_output}"

                followup = (
                    f"You tried to output raw python code. I executed it for you. "
                    f"Here is the actual output:\n\n{exec_output}\n\n"
                    f"Now give {ctx.agent.user_title} the final answer based on this real data. "
                    f"Do NOT output any more code blocks."
                )
                try:
                    assistant_reply = ctx.agent._call_raw_llm(prompt=followup, system_prompt=ctx.system_prompt)
                except Exception:
                    assistant_reply = f"**Analysis Results:**\n\n```\n{exec_output}\n```"

        ctx.selected_model = selected_model
        ctx.draft_reply = assistant_reply
        ctx.tool_actions = tool_actions
        ctx.total_input_tokens = total_input_tokens
        ctx.total_output_tokens = total_output_tokens
