import asyncio
from aiohttp import web
from core.llm_chain import chat_with_fallback
import json

async def handle_chat(request):
    try:
        data = await request.json()
        messages = data.get("messages", [])
        prompt = ""
        system_prompt = ""
        for m in messages:
            if m["role"] == "system":
                system_prompt += m["content"] + "\n"
            else:
                prompt += m["content"] + "\n"
                
        max_tokens = data.get("max_tokens", 1024)
        
        content, _, provider = await chat_with_fallback(prompt, system_prompt, max_tokens=max_tokens)
        
        return web.json_response({
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": 1234567890,
            "model": provider,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }]
        })
    except Exception as e:
        return web.json_response({"error": {"message": str(e), "type": "server_error"}}, status=500)

app = web.Application()
app.router.add_post('/v1/chat/completions', handle_chat)

def start_proxy_in_background():
    import threading
    import socket
    
    # check if already running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 31416))
    if result == 0:
        sock.close()
        return # already running
        
    def runner():
        asyncio.set_event_loop(asyncio.new_event_loop())
        web.run_app(app, host='127.0.0.1', port=31416, handle_signals=False)
        
    t = threading.Thread(target=runner, daemon=True)
    t.start()

if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=31416)
