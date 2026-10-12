import asyncio
import json

import aiohttp

from core.config import LLMConfig


async def chat_with_fallback(prompt, system_prompt="", max_tokens=1024, temperature=0.1, model_override=None, tools=None, client_data=False, response_format=None):
    """
    Tries providers configured in cfg.providers in order (default: ['freellmapi']).
    Raises 'No approved provider for client data' when client_data=True.
    Returns (content, tool_actions, provider_name).
    """
    if client_data:
        raise ValueError("No approved provider for client data")

    cfg = LLMConfig()
    active_providers = getattr(cfg, "providers", ["freellmapi"])

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for provider in active_providers:
        # 1. FreeLLMAPI
        if provider == "freellmapi" and cfg.freellmapi_enabled:
            base_url = cfg.freellmapi_base_url or "http://localhost:31415/v1"
            api_key = cfg.freellmapi_api_key or cfg.openrouter_api_key or "sk-dummy"
            if not model_override or model_override in ("freellmapi", "local-fallback-chain", "auto"):
                target_model = "auto"
            else:
                target_model = model_override.replace("freellmapi/", "").strip()
                if target_model in ("freellmapi", ""):
                    target_model = "auto"
            print(f'FreeLLMAPI model selected: {target_model}')

            if len(system_prompt) > 8000:
                system_prompt = system_prompt[:8000] + '\n[TRUNCATED]'
            if len(prompt) > 4000:
                prompt = prompt[:4000] + '\n[TRUNCATED]'
            payload = {
                "model": target_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            if response_format:
                payload["response_format"] = response_format
            if tools:
                formatted_tools = []
                for t in tools:
                    if isinstance(t, dict):
                        if "function" in t:
                            if "type" not in t:
                                formatted_tools.append({"type": "function", "function": t["function"]})
                            else:
                                formatted_tools.append(t)
                        elif "name" in t:
                            formatted_tools.append({
                                "type": "function",
                                "function": {
                                    "name": t["name"],
                                    "description": t.get("description", ""),
                                    "parameters": t.get("input_schema") or t.get("parameters") or {"type": "object", "properties": {}}
                                }
                            })
                        else:
                            formatted_tools.append(t)
                payload["tools"] = formatted_tools

            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            msg = data["choices"][0]["message"]
                            content = msg.get("content") or ""
                            tool_actions = []
                            if "tool_calls" in msg and msg["tool_calls"]:
                                for tc in msg["tool_calls"]:
                                    if tc["type"] == "function":
                                        tool_actions.append({
                                            "name": tc["function"]["name"],
                                            "arguments": json.loads(tc["function"]["arguments"])
                                        })
                            print("  [LLM Chain] Served by FreeLLMAPI")
                            return content, tool_actions, "freellmapi"
                        else:
                            text = await resp.text()
                            print(f"  [LLM Chain] FreeLLMAPI failed ({resp.status}): {text[:100]}")
            except Exception as e:
                print(f"  [LLM Chain] FreeLLMAPI error: {e}")

        # 2. OpenRouter (disabled unless added to cfg.providers)
        elif provider == "openrouter" and cfg.openrouter_api_key:
            try:
                openrouter_model = model_override or "meta-llama/llama-3.3-70b-instruct:free"
                payload = {
                    "model": openrouter_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                if tools:
                    payload["tools"] = tools
                headers = {"Authorization": f"Bearer {cfg.openrouter_api_key}", "Content-Type": "application/json"}
                async with aiohttp.ClientSession() as session:
                    async with session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            msg = data["choices"][0]["message"]
                            content = msg.get("content") or ""
                            print("  [LLM Chain] Served by OpenRouter")
                            return content, [], "openrouter"
                        else:
                            text = await resp.text()
                            print(f"  [LLM Chain] OpenRouter failed ({resp.status}): {text[:100]}")
            except Exception as e:
                print(f"  [LLM Chain] OpenRouter error: {e}")

        # 3. Gemini Direct (disabled unless added to cfg.providers)
        elif provider == "gemini" and cfg.gemini_api_key:
            try:
                import google.genai as genai
                from google.genai.types import FunctionDeclaration, GenerateContentConfig, Tool

                # Timeout changed to 30000 milliseconds
                client = genai.Client(api_key=cfg.gemini_api_key, http_options={'timeout': 30000})
                model = cfg.gemini_model_flash

                combined_prompt = ""
                if system_prompt:
                    combined_prompt += f"System: {system_prompt}\n\n"
                combined_prompt += prompt

                gemini_tools = []
                if tools:
                    for t in tools:
                        f = t["function"]
                        fd = FunctionDeclaration(
                            name=f["name"],
                            description=f.get("description", ""),
                            parameters=f.get("parameters", {})
                        )
                        gemini_tools.append(Tool(function_declarations=[fd]))

                _c, _m, _p, _t = client, model, combined_prompt, gemini_tools
                def sync_call(
                    c=_c,
                    m=_m,
                    p=_p,
                    tools=_t,
                    temp=temperature,
                    toks=max_tokens,
                ):
                    return c.models.generate_content(
                        model=m,
                        contents=p,
                        config=GenerateContentConfig(
                            temperature=temp,
                            max_output_tokens=toks,
                            tools=tools if tools else None,
                        ),
                    )

                response = await asyncio.to_thread(sync_call)

                tool_actions = []
                content = ""
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            content += part.text
                        elif part.function_call:
                            args = {}
                            if part.function_call.args:
                                for k, v in part.function_call.args.items():
                                    args[k] = v
                            tool_actions.append({
                                "name": part.function_call.name,
                                "arguments": args
                            })

                print("  [LLM Chain] Served by Gemini Direct")
                return content, tool_actions, "gemini"
            except Exception as e:
                print(f"  [LLM Chain] Gemini Direct failed: {e}")

    raise Exception("All providers in the LLM fallback chain failed.")
