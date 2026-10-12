from typing import Any

from ultron.core.config import LLMConfig
from ultron.core.tool_definitions import ULTRON_TOOLS
from ultron.infrastructure.mcp_client import MCPManager


class DynamicToolRouter:
    def __init__(self, llm_cfg: LLMConfig):
        self.llm_cfg = llm_cfg
        self.fast_model = llm_cfg.gemini_model_lite
        self.api_key = llm_cfg.openrouter_api_key

        self.ALWAYS_ON_TOOLS = {
            "execute_command",
            "run_python",
            "file_operation",
            "core_memory_update",
            "core_memory_append",
            "core_memory_replace",
            "store_file_memory",
            "search_file_memory"
        }

    async def route_tools(self, user_input: str, mcp_manager: MCPManager) -> list[dict[str, Any]]:
        if not user_input or not user_input.strip():
            return []

        # Fast-Path: Pure conversational queries or simple conceptual questions don't need external tools
        tool_keywords = {
            "browser", "search", "google", "website", "url", "fetch", "scrape", "open",
            "run", "python", "script", "file", "folder", "read", "write", "delete", "excel",
            "csv", "email", "gmail", "smtp", "desktop", "click", "notepad", "app", "cmd", "terminal",
            "git", "pip", "calc", "calculate", "execute"
        }
        lower_input = user_input.lower()
        has_tool_keyword = any(kw in lower_input for kw in tool_keywords)
        if not has_tool_keyword and len(user_input.split()) < 30:
            # Skip tool injection entirely for conversational/informational turns (<0.01ms latency, enables 1-pass execution)
            return []

        mcp_schemas = mcp_manager.get_anthropic_schemas()
        all_schemas = ULTRON_TOOLS + mcp_schemas

        compact_list = []
        for s in all_schemas:
            name = s["name"]
            if name in self.ALWAYS_ON_TOOLS:
                continue
            desc = s.get("description", "")[:100]
            compact_list.append(f"- {name}: {desc}")

        compact_str = "\n".join(compact_list)

        prompt = f'''You are an ultra-fast tool routing algorithm.
The user wants to perform this task:
{user_input[:1000]}

Review these available optional tools:
{compact_str}

Return a JSON array of strings containing ONLY the names of the tools that might be useful for this task.
If no tools are needed, return []. Respond with RAW JSON ONLY.'''

        selected_tool_names = set(self.ALWAYS_ON_TOOLS)

        try:
            from ultron.core.llm_chain import chat_with_fallback
            content, _, _ = await chat_with_fallback(
                prompt=prompt,
                model_override=self.fast_model,
                max_tokens=150
            )
            raw_text = content.strip()
            if raw_text.startswith("`json"):
                raw_text = raw_text.split("`json")[1]
            if raw_text.endswith("`"):
                raw_text = raw_text.rsplit("`", 1)[0]
            raw_text = raw_text.strip()

            import json
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                selected_tool_names.update(parsed)
        except Exception as e:
            print(f"  [TOOL ROUTER ERROR] Failed to triage tools: {e}")
            return all_schemas

        final_schemas = [s for s in all_schemas if s["name"] in selected_tool_names]
        print(f"  [TOOL ROUTER] Triaged {len(all_schemas)} total tools down to {len(final_schemas)} active tools.")
        return final_schemas
