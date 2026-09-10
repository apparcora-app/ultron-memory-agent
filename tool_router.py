import json
import logging
from typing import Any

from config import LLMConfig
from mcp_client import MCPManager
from tool_definitions import ULTRON_TOOLS

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
            return [t for t in ULTRON_TOOLS if t["name"] in self.ALWAYS_ON_TOOLS]

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
            import aiohttp
            async with aiohttp.ClientSession() as session:
                actual_model = self.fast_model.replace("openrouter/", "") if self.fast_model.startswith("openrouter/") else self.fast_model
                payload = {
                    "model": actual_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                async with session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        if content.startswith("```json"): content = content[7:-3].strip()
                        elif content.startswith("```"): content = content[3:-3].strip()
                            
                        extracted = json.loads(content)
                        if isinstance(extracted, list):
                            for t in extracted:
                                if isinstance(t, str):
                                    selected_tool_names.add(t)
                    else:
                        err_text = await resp.text()
                        print(f"  [TOOL ROUTER ERROR] OpenRouter API Error {resp.status}: {err_text}")
        except Exception as e:
            print(f"  [TOOL ROUTER ERROR] Failed to triage tools: {e}")
            return all_schemas
            
        final_schemas = [s for s in all_schemas if s["name"] in selected_tool_names]
        print(f"  [TOOL ROUTER] Triaged {len(all_schemas)} total tools down to {len(final_schemas)} active tools.")
        return final_schemas
