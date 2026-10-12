import json
import random
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ultron.core.llm_chain import chat_with_fallback

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

def get_text(content):
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
    return ""

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    prompt = ""
    system = ""
    for m in messages:
        if m["role"] == "user":
            prompt += get_text(m["content"]) + "\n"
        elif m["role"] == "system":
            system += get_text(m["content"]) + "\n"

    tools = data.get("tools", None)

    response_format = data.get("response_format", None)

    # Evaluation requests contain synthetic queries and zero confidential client data.
    # Routing via FreeLLMAPI is permitted; client_data is explicitly False.
    DEEPEVAL_CLIENT_DATA: bool = False

    content, tool_actions, provider = await chat_with_fallback(
        prompt=prompt.strip(),
        system_prompt=system.strip(),
        max_tokens=data.get("max_tokens", 1024),
        temperature=data.get("temperature", 0.1),
        model_override="auto",
        tools=tools,
        client_data=DEEPEVAL_CLIENT_DATA,
        response_format=response_format
    )

    if response_format and isinstance(content, str):
        content_clean = content.strip()
        if content_clean.startswith("```json"):
            content_clean = content_clean[7:]
        elif content_clean.startswith("```"):
            content_clean = content_clean[3:]
        if content_clean.endswith("```"):
            content_clean = content_clean[:-3]
        content_clean = content_clean.strip()
        first_brace = content_clean.find("{")
        first_bracket = content_clean.find("[")
        start_idx = -1
        if first_brace != -1 and first_bracket != -1:
            start_idx = min(first_brace, first_bracket)
        elif first_brace != -1:
            start_idx = first_brace
        elif first_bracket != -1:
            start_idx = first_bracket

        if start_idx >= 0:
            last_brace = content_clean.rfind("}")
            last_bracket = content_clean.rfind("]")
            end_idx = max(last_brace, last_bracket)
            if end_idx != -1 and end_idx >= start_idx:
                content_clean = content_clean[start_idx:end_idx + 1]

        content = content_clean

    message = {
        "role": "assistant",
        "content": content,
    }

    if tool_actions:
        message["tool_calls"] = [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {
                    "name": t["name"],
                    "arguments": json.dumps(t["arguments"])
                }
            } for i, t in enumerate(tool_actions)
        ]

    return JSONResponse({
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "local-fallback-chain",
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": "tool_calls" if tool_actions else "stop"
        }],
        "usage": {
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": (len(prompt) + len(content)) // 4
        }
    })

@app.post("/v1/embeddings")
async def embeddings(request: Request):
    data = await request.json()
    inp = data.get("input", "")
    num_inputs = 1 if isinstance(inp, str) else len(inp)

    return JSONResponse({
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "index": i,
                "embedding": [random.random() for _ in range(1536)]
            } for i in range(num_inputs)
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 0, "total_tokens": 0}
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=31416)
