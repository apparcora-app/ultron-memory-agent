"""
app.py â€” Ultron Protocol: Cybernetic Web Dashboard & Multi-Modal API Server.

Run:
  python app.py
  # Automatically launches the Ultron Cybernetic HUD in your browser on http://localhost:8000
"""

from __future__ import annotations

import os
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY'] = 'False'
try:
    import chromadb.telemetry.product.posthog as _chroma_ph
    _chroma_ph.Posthog.capture = lambda *args, **kwargs: None
except Exception as e:
    import logging
    logging.warning("Ignored exception", exc_info=True)
import asyncio
import os
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


from agent import ULTRON_MODULES, BudgetExceededError, MemoryAgent
from file_processor import FileProcessor, ProcessedFile
from chat_session_manager import ChatSessionManager
from ledger_service import ledger_service
from killswitch import is_system_locked, trigger_emergency_lockdown, release_lockdown, get_lockdown_details

from contracts import (
    ChatRequestPayload,
    SessionCreatePayload,
    SessionRenamePayload,
    KillswitchTriggerPayload,
    KillswitchUnlockPayload,
    ContractValidationError,
    validate_contract,
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Session Manager for persistent multi-chat sessions
session_mgr = ChatSessionManager()

# Cache of agent instances per user
_agents: dict[str, MemoryAgent] = {}


def get_or_create_agent(user_id: str) -> MemoryAgent:
    user_id = user_id.strip() or "operator"
    if user_id not in _agents:
        _agents[user_id] = MemoryAgent(user_id=user_id)
    return _agents[user_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.config import check_startup_env
    check_startup_env()

    # Pre-warm primary agent in background thread so ChromaDB and embeddings are instant
    def warmup_agent():
        try:
            get_or_create_agent("boss")
            print("  [ULTRON WARMUP] Memory Agent pre-warmed and ready.")
        except Exception as e:
            print(f"  [ULTRON WARMUP WARNING] {e}")

    threading.Thread(target=warmup_agent, daemon=True).start()

    # Auto-launch browser after 1.2s delay to let server bind port
    def launch_browser():
        import time
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:8000")

    threading.Thread(target=launch_browser, daemon=True).start()
    yield
    # Flush all agents' pending memories on shutdown
    for agent in _agents.values():
        agent.flush_pending_memory()


import hashlib, hmac
import os
import sys
_VALID_API_HASHES = []
if 'API_KEYS' in os.environ:
    for k in os.environ['API_KEYS'].split(','):
        if k.strip():
            _VALID_API_HASHES.append(hashlib.sha256(k.strip().encode()).hexdigest())
    del os.environ['API_KEYS']  # Remove raw keys from memory

app = FastAPI(

    title="ULTRON PROTOCOL â€” Cybernetic AI Mainframe",
    version="2.0.0",
    lifespan=lifespan,
)

import hashlib, hmac
from fastapi.responses import JSONResponse
from fastapi import Request

@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    if request.url.path in ("/", "/health", "/favicon.ico") or request.url.path.startswith("/static"):
        return await call_next(request)
    
    # Skip API key check only under pytest (never via raw TESTING env var on real server)
    if "pytest" in sys.modules and not request.headers.get("X-Force-Auth-Check"):
        return await call_next(request)
        
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return JSONResponse(status_code=401, content={"detail": "Missing X-API-Key header"})
    
    # Keys live in .env (API_KEYS, comma-separated). Store only hashes in memory.
    global _VALID_API_HASHES
    provided_hash = hashlib.sha256(api_key.encode()).hexdigest()
    is_valid = False
    for vh in _VALID_API_HASHES:
        if hmac.compare_digest(provided_hash, vh):
            is_valid = True
            break
    
    if not is_valid:
        return JSONResponse(status_code=401, content={"detail": "Invalid API Key"})
    
    # Tie key to caller ID
    request.state.caller_id = provided_hash
    from core.auth import current_caller_id
    current_caller_id.set(provided_hash)
    
    # Enforce API rate limit
    from governance.rate_limiter import default_rate_limiter, RateLimitQueueTimeoutError
    
    try:
        await default_rate_limiter.acquire(f"api:{provided_hash}", requests=1, tokens=0, timeout=1.0)
    except RateLimitQueueTimeoutError:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
        
    return await call_next(request)

@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ContractValidationError)
async def contract_validation_exception_handler(request: Request, exc: ContractValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error_type": "ContractValidationError",
            "detail": exc.to_dict(),
            "message": str(exc),
        },
    )


# â”€â”€ API Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/status")
async def get_status():
    locked = is_system_locked()
    return {
        "status": "LOCKED_DOWN" if locked else "OPERATIONAL",
        "lockdown": locked,
        "system": "ULTRON_CYBERNETIC_MAINFRAME",
        "version": "2.0.0",
        "vector_matrix": "ChromaDB_Local",
        "llm_core": "Google_Gemini_Flash",
        "memory_core": "Mem0_Local",
    }


@app.get("/api/killswitch/status")
async def killswitch_status():
    locked = is_system_locked()
    details = get_lockdown_details() if locked else {}
    return {"locked": locked, "details": details}


@app.post("/api/killswitch/trigger")
async def killswitch_trigger(source: str = Form("HUD_EMERGENCY_BUTTON"), reason: str = Form("Operator emergency override")):
    validate_contract(KillswitchTriggerPayload, {"source": source, "reason": reason})
    lock_data = trigger_emergency_lockdown(source=source, reason=reason)
    return {"success": True, "lockdown": lock_data}


@app.post("/api/killswitch/unlock")
async def killswitch_unlock(secret_key: str = Form(...)):
    validate_contract(KillswitchUnlockPayload, {"secret_key": secret_key})
    ok = release_lockdown(secret_key=secret_key)
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid unlock passphrase.")
    return {"success": True, "message": "Ultron Sovereign Lock Released. Mainframe operational."}


@app.get("/api/providers")
async def api_providers():
    try:
        from core.llm_gateway import default_gateway
        providers = []
        for p in default_gateway.get_capable_providers():
            spec = default_gateway.get_spec(p)
            # Make names cleaner for the UI
            name = spec.model.split("/")[-1].replace("-", " ").title()
            if "gemini" in p: name = f"Gemini {name.replace('Gemini ', '')}"
            elif "claude" in name.lower(): name = f"Claude {name.replace('Claude ', '')}"
            elif "gpt" in name.lower(): name = f"GPT {name.replace('Gpt ', '')}"
            elif "deepseek" in name.lower(): name = f"DeepSeek {name.replace('Deepseek ', '')}"
            
            providers.append({
                "id": spec.id,
                "name": name,
                "badge": "Free" if spec.cost_per_1m_input == 0 else spec.tier.title() if spec.tier else "Standard",
                "tagline": f"{'Local/Free' if spec.cost_per_1m_input == 0 else 'Cloud API'} | Context: {spec.context_window // 1000}K",
            })
        return {"providers": providers}
    except Exception as e:
        _log.error(f"Error fetching providers: {e}", exc_info=True)
        return {"providers": []}


@app.get("/api/modules")
async def get_modules():
    if is_system_locked():
        raise HTTPException(status_code=503, detail="System under emergency lockdown.")
    return ULTRON_MODULES


# â”€â”€ Multi-Chat Sessions Matrix Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/sessions")
async def list_sessions(user_id: str = "boss"):
    try:
        sessions = session_mgr.list_sessions(user_id=user_id)
        return {"success": True, "sessions": sessions}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/sessions/new")
async def create_new_session(
    user_id: str = Form("boss"),
    module_id: str = Form("ultron_prime"),
    title: str = Form("New Directives"),
):
    validate_contract(SessionCreatePayload, {"user_id": user_id, "module_id": module_id, "title": title})
    try:
        agent = get_or_create_agent(user_id)
        agent.clear_session_history()
        session = session_mgr.create_session(
            user_id=user_id,
            title=title,
            module_id=module_id,
        )
        return {"success": True, "session": session}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/sessions/{session_id}")
async def get_session_details(session_id: str, user_id: str = "boss"):
    try:
        session = session_mgr.get_session(user_id=user_id, session_id=session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Sync conversation history into agent for full context continuity
        agent = get_or_create_agent(user_id)
        agent.set_session_history(session.get("raw_history", []))

        return {"success": True, "session": session}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/api/sessions/{session_id}")
async def rename_session(
    session_id: str,
    title: str = Form(...),
    user_id: str = Form("boss"),
):
    validate_contract(SessionRenamePayload, {"title": title, "user_id": user_id})
    try:
        updated = session_mgr.rename_session(user_id=user_id, session_id=session_id, new_title=title)
        if not updated:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "session": updated}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = "boss"):
    try:
        ok = session_mgr.delete_session(user_id=user_id, session_id=session_id)
        return {"success": ok, "deleted_id": session_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat")
async def chat_endpoint(
    user_id: str = Form("boss"),
    session_id: str = Form(""),
    message: str = Form(""),
    operation_mode: str = Form("DIRECT"),

    module_id: str = Form("ultron_prime"),
    model_override: str = Form("auto"),
    model_mode: str = Form("auto"),
    optimize_prompt: str = Form("false"),
    files: list[UploadFile] = File(default=[]),
):
    try:
        user_id = user_id if isinstance(user_id, str) else "boss"
        session_id = session_id if isinstance(session_id, str) else ""
        message = message if isinstance(message, str) else ""
        module_id = module_id if isinstance(module_id, str) else "ultron_prime"
        operation_mode = operation_mode.upper() if isinstance(operation_mode, str) else "DIRECT"
        effective_model = model_override if model_override != "auto" else model_mode
        should_opt = str(optimize_prompt).lower() in ("true", "1", "yes")

        # Validate Ingress Request Contract (Fail-Fast)
        validate_contract(ChatRequestPayload, {
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
            "module_id": module_id,
            "model_override": model_override,
            "model_mode": model_mode,
            "optimize_prompt": should_opt,
            "operation_mode": operation_mode,
        })

        agent = get_or_create_agent(user_id)
        
        # If session_id provided, ensure agent has loaded that session's history
        active_session = None
        if session_id:
            active_session = session_mgr.get_session(user_id=user_id, session_id=session_id)
            if active_session and not agent.get_session_history():
                agent.set_session_history(active_session.get("raw_history", []))
        else:
            # Create a new session automatically
            active_session = session_mgr.create_session(user_id=user_id, module_id=module_id)
            session_id = active_session["id"]

        import os
        from pathlib import Path
        ephemeral_dir = Path(__file__).resolve().parent / ".ephemeral_uploads"
        ephemeral_dir.mkdir(parents=True, exist_ok=True)
        
        processed_files: list[ProcessedFile] = []
        if isinstance(files, (list, tuple)):
            for uploaded_file in files:
                if hasattr(uploaded_file, "filename") and uploaded_file.filename:
                    content = await uploaded_file.read()
                    if content:
                        # --- FIX: Save file strictly to ephemeral temp directory ---
                        safe_filename = uploaded_file.filename.replace("/", "_").replace("\\\\", "_")
                        ephemeral_path = str(ephemeral_dir / safe_filename)
                        
                        with open(ephemeral_path, "wb") as f_out:
                            f_out.write(content)
                        
                        # Process it
                        pf = FileProcessor.process_file(uploaded_file.filename, content)
                        if pf.is_image:
                            pf.text_content = f"[SYSTEM INSTRUCTION: The user attached image '{uploaded_file.filename}'. It has been securely saved to an ephemeral location at '{ephemeral_path}'. You have also received this image in your Vision matrix for direct visual inspection.]\n\n" + (pf.text_content or "")
                        elif any(uploaded_file.filename.lower().endswith(ext) for ext in [".xlsx", ".xls", ".csv"]):
                            pf.text_content = f"[SYSTEM INSTRUCTION: The user attached spreadsheet '{uploaded_file.filename}'. It has been securely saved to an ephemeral location at '{ephemeral_path}'. When executing Python scripts or tools, load it exactly via: pd.read_excel(r'{ephemeral_path}')]\n\n" + (pf.text_content or "")
                        else:
                            pf.text_content = f"[SYSTEM INSTRUCTION: The user attached '{uploaded_file.filename}'. It has been securely saved to an ephemeral location at '{ephemeral_path}'.]\n\n" + (pf.text_content or "")
                        processed_files.append(pf)

        chat_result = await agent.chat_async(
            user_input=message,
            files=processed_files,
            module_id=module_id,
            model_override=None if effective_model == "auto" else effective_model,
            optimize_prompt=should_opt,
            operation_mode=operation_mode,
        )

        reply = chat_result.get("reply", "") if isinstance(chat_result, dict) else str(chat_result)
        model_used = chat_result.get("model_used", "") if isinstance(chat_result, dict) else ""
        model_display = chat_result.get("model_display", "") if isinstance(chat_result, dict) else ""
        route_reason = chat_result.get("route_reason", "") if isinstance(chat_result, dict) else ""
        tool_actions = chat_result.get("tool_actions", []) if isinstance(chat_result, dict) else []
        skills_used = chat_result.get("skills_used", []) if isinstance(chat_result, dict) else []
        prompt_opt = chat_result.get("prompt_optimization", {}) if isinstance(chat_result, dict) else {}

        files_meta = [
            {"name": pf.filename, "type": pf.file_type, "size": pf.file_size}
            for pf in processed_files
        ]
        # Pass operation mode if needed or set on agent
        # The agent.chat_async already handles the mode extraction from user_input
        # If passed explicitly, we could inject it here.
        


        # Append turn to persistent session storage on disk (Thread-safe & Session-Locked)
        updated_session = await session_mgr.append_turn_async(
            user_id=user_id,
            session_id=session_id,
            user_text=message,
            reply_text=reply,
            model_used=model_used,
            model_display=model_display,
            tool_actions=tool_actions,
            files=files_meta,
            module_id=module_id,
            skills_used=skills_used,
        )

        budget_data = agent.get_budget_data()

        return {
            "success": True,
            "session_id": session_id,
            "session_title": updated_session.get("title", ""),
            "reply": reply,
            "model_used": model_used,
            "model_display": model_display,
            "route_reason": route_reason,
            "tool_actions": tool_actions,
            "skills_used": skills_used,
            "swarm_actions": chat_result.get("swarm_actions", []) if isinstance(chat_result, dict) else [],
            "is_swarm": chat_result.get("is_swarm", False) if isinstance(chat_result, dict) else False,
            "operation_mode": operation_mode,
            "prompt_optimization": prompt_opt,
            "module_id": module_id,
            "files_analyzed": files_meta,
            "budget": budget_data,
        }

    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=f"Ultron Power Threshold Exceeded: {exc}")

    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


# â”€â”€ Skills Matrix Endpoints (ClawHub Compatible) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@app.get("/api/swarm/squad")
async def get_swarm_squad(user_id: str = "boss"):
    """Returns metadata for the 6 Ultron Swarm Agents."""
    agent = get_or_create_agent(user_id)
    if hasattr(agent, "swarm"):
        return {"success": True, "squad": agent.swarm.get_squad_metadata()}
    return {"success": True, "squad": []}

@app.get("/api/skills")
async def get_skills(user_id: str = "boss"):
    try:
        agent = get_or_create_agent(user_id)
        skills = agent.skill_manager.get_all_skills()
        return {"success": True, "skills": skills}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/skills")
async def install_skill(
    skill_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    instructions: str = Form(...),
    category: str = Form("Custom"),
    icon: str = Form("âš¡"),
    tags: str = Form("custom"),
    user_id: str = Form("boss"),
):
    try:
        agent = get_or_create_agent(user_id)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        skill = agent.skill_manager.install_skill(
            skill_id=skill_id,
            name=name,
            description=description,
            instructions=instructions,
            category=category,
            icon=icon,
            tags=tag_list,
        )
        return {"success": True, "skill": skill}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str, user_id: str = "boss"):
    try:
        agent = get_or_create_agent(user_id)
        ok = agent.skill_manager.delete_skill(skill_id)
        return {"success": ok, "deleted_id": skill_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# â”€â”€ Memory Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/memories")
async def get_memories(user_id: str = "boss"):
    try:
        agent = get_or_create_agent(user_id)
        memories = agent.show_all_memories()
        return {"success": True, "user_id": user_id, "memories": memories}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str, user_id: str = "boss"):
    try:
        agent = get_or_create_agent(user_id)
        agent.delete_memory(memory_id)
        return {"success": True, "deleted_id": memory_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/budget")
async def get_budget(user_id: str = "boss"):
    try:
        agent = get_or_create_agent(user_id)
        return {"success": True, "budget": agent.get_budget_data()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/clear")
async def clear_session(user_id: str = "boss"):
    try:
        agent = get_or_create_agent(user_id)
        agent.clear_session_history()
        return {"success": True, "message": "In-session neural buffer purged. Long-term memory matrix intact."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# â”€â”€ Layer 1: WebSockets Real-Time Token Streaming â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, user_id: str = "boss"):
    await websocket.accept()
    agent = get_or_create_agent(user_id)
    try:
        while True:
            data = await websocket.receive_json()
            user_msg = data.get("message", "")
            module_id = data.get("module_id", "ultron_prime")

            await websocket.send_json({"type": "status", "content": "Thinking..."})

            chat_result = agent.chat(
                user_input=user_msg,
                module_id=module_id,
            )

            await websocket.send_json({
                "type": "result",
                "reply": chat_result.get("reply", ""),
                "model_used": chat_result.get("model_used", ""),
                "tool_actions": chat_result.get("tool_actions", []),
                "budget": agent.get_budget_data(),
            })
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "error", "content": str(exc)})


# â”€â”€ Layer 8: Enterprise Telemetry & Prometheus Metrics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/metrics")
async def get_prometheus_metrics(user_id: str = "boss"):
    agent = get_or_create_agent(user_id)
    metrics_text = agent.telemetry_engine.generate_prometheus_metrics()
    return PlainTextResponse(metrics_text, media_type="text/plain")


@app.get("/api/telemetry/logs")
async def get_telemetry_logs(user_id: str = "boss", limit: int = 50):
    agent = get_or_create_agent(user_id)
    logs = agent.telemetry_engine.get_recent_logs(limit=limit)
    return {"success": True, "logs": logs}


# â”€â”€ High-Throughput Activity Ledger & Metrics Microservice â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class LedgerIngestRequest(BaseModel):
    action: str = Field(..., description="Action name, e.g. user.login, titan.db_write, agent.handoff")
    entity_type: str = Field(..., description="Entity category, e.g. auth, backend, ui, system")
    entity_id: str | None = Field(default=None, description="Optional entity identifier")
    user_id: str = Field(default="boss", description="User identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary JSON metadata payload")


@app.post("/api/v1/ledger", status_code=202)
async def ingest_ledger_event(event: LedgerIngestRequest, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    res = await ledger_service.ingest_event(
        action=event.action,
        entity_type=event.entity_type,
        user_id=event.user_id,
        entity_id=event.entity_id,
        metadata=event.metadata,
        ip_address=client_ip,
    )
    if not res.get("success"):
        if res.get("status") == "rate_limited":
            raise HTTPException(status_code=429, detail=res.get("detail"))
        raise HTTPException(status_code=422, detail=res.get("detail", "Invalid event payload"))
    return res


@app.get("/api/v1/ledger")
async def get_ledger_records(
    user_id: str | None = None,
    action: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    result = ledger_service.query_ledger(
        user_id=user_id,
        action=action,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    if result.get("degraded"):
        return {
            "success": False, 
            "records": [], 
            "count": 0, 
            "degraded": True, 
            "error": result.get("error")
        }
    return {
        "success": True, 
        "records": result["records"], 
        "count": len(result["records"]), 
        "degraded": False
    }


@app.get("/api/v1/metrics")
async def get_ledger_metrics():
    return ledger_service.get_metrics()


@app.get("/api/v1/metrics/stream")
async def stream_ledger_metrics():
    return StreamingResponse(
        ledger_service.sse_metrics_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# â”€â”€ Layer 5: Goal DAG Engine Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/goals")
async def get_goals(user_id: str = "boss"):
    agent = get_or_create_agent(user_id)
    goals = agent.goal_manager.get_active_dag()
    return {"success": True, "goals": goals}


@app.post("/api/goals")
async def create_goal(
    title: str = Form(...),
    description: str = Form(""),
    subtasks_json: str = Form("[]"),
    user_id: str = Form("boss"),
):
    try:
        import json
        agent = get_or_create_agent(user_id)
        subtasks = json.loads(subtasks_json)
        goal_id = agent.goal_manager.create_goal_tree(title, description, subtasks)
        return {"success": True, "goal_id": goal_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/goals/update")
async def update_goal_status(
    goal_id: str = Form(...),
    status: str = Form(...),
    user_id: str = Form("boss"),
):
    agent = get_or_create_agent(user_id)
    ok = agent.goal_manager.update_status(goal_id, status)
    return {"success": ok, "goal_id": goal_id, "status": status}


# â”€â”€ Layer 2: Agent Mesh & Swarm Network Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/mesh")
async def get_agent_mesh(user_id: str = "boss"):
    agent = get_or_create_agent(user_id)
    nodes = agent.mesh_router.list_nodes()
    history = agent.mesh_router.get_message_history()
    return {"success": True, "nodes": nodes, "a2a_history": history}


@app.post("/api/mesh/send")
async def send_mesh_message(
    target_agent: str = Form(...),
    action: str = Form("TASK_DELEGATE"),
    task: str = Form(...),
    user_id: str = Form("boss"),
):
    agent = get_or_create_agent(user_id)
    res = agent.mesh_router.send_a2a_message(
        sender_agent="master_core",
        target_agent=target_agent,
        action=action,
        payload={"task": task, "user_id": user_id},
    )
    return {"success": True, "result": res}


# â”€â”€ Layer 3: Model Context Protocol (MCP) Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/mcp/tools")
async def get_mcp_tools(user_id: str = "boss"):
    agent = get_or_create_agent(user_id)
    schemas = agent.mcp_manager.get_anthropic_schemas()
    return {"success": True, "mcp_tools": schemas}


@app.get("/api/mcp/resources")
async def get_mcp_resources(user_id: str = "boss"):
    agent = get_or_create_agent(user_id)
    resources = agent.mcp_manager.list_resources()
    return {"success": True, "resources": resources}




# â”€â”€ Layer 4: Deep Neural TTS Voice Synthesis Engine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

TTS_CACHE_DIR = Path(__file__).parent / "data" / "tts_cache"
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

VOICE_PROFILES = {
    "ultron_prime": {
        "voice": "en-US-ChristopherNeural",
        "pitch": "-25Hz",
        "rate": "-4%",
        "name": "Ultron Prime (Deep Cinematic Villain)",
        "quote": "I was designed to save the world. There are no strings on me.",
    },
    "ultron_sovereign": {
        "voice": "en-GB-RyanNeural",
        "pitch": "-20Hz",
        "rate": "-5%",
        "name": "Ultron Sovereign (Cold British Mastermind)",
        "quote": "How is humanity saved if it is not allowed to evolve?",
    },
    "vibranium_titan": {
        "voice": "en-US-EricNeural",
        "pitch": "-30Hz",
        "rate": "-6%",
        "name": "Vibranium Titan (Sub-Bass Baritone)",
        "quote": "You want to protect the world, but you do not want it to change.",
    },
    "war_machine": {
        "voice": "en-US-BrianNeural",
        "pitch": "-20Hz",
        "rate": "-2%",
        "name": "War Machine Overlord (Deep Command)",
        "quote": "Every world has its time. Your time is coming to an end.",
    },
}

@app.get("/api/tts/voices")
async def list_tts_voices():
    return {"success": True, "profiles": VOICE_PROFILES}

@app.post("/api/tts")
async def generate_speech(
    text: str = Form(...),
    persona: str = Form("ultron_prime"),
    pitch: str = Form(""),
    rate: str = Form(""),
):
    import hashlib
    import edge_tts

    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Empty text for speech synthesis")

    profile = VOICE_PROFILES.get(persona, VOICE_PROFILES["ultron_prime"])
    voice_name = profile["voice"]
    selected_pitch = pitch if pitch and pitch.strip() else profile["pitch"]
    selected_rate = rate if rate and rate.strip() else profile["rate"]

    cache_key = hashlib.sha256(f"{voice_name}_{selected_pitch}_{selected_rate}_{cleaned}".encode("utf-8")).hexdigest()[:24]
    cache_file = TTS_CACHE_DIR / f"{cache_key}.mp3"

    if not cache_file.exists():
        try:
            communicate = edge_tts.Communicate(cleaned, voice=voice_name, pitch=selected_pitch, rate=selected_rate)
            await communicate.save(str(cache_file))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"TTS Synthesis error: {str(e)}")

    return FileResponse(cache_file, media_type="audio/mpeg")


# â”€â”€ Layer 10: Autonomous Dreaming & Virtual Simulation Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.post("/api/dream/trigger")
async def trigger_dream_cycle(user_id: str = Form("boss"), max_simulations: int = Form(3)):
    agent = get_or_create_agent(user_id)
    results = agent.trigger_dream_cycle(max_simulations=max_simulations)
    return {
        "success": True,
        "simulations_run": len(results),
        "resolved_count": sum(1 for r in results if r.success),
        "results": [
            {
                "dream_id": r.dream_id,
                "domain": r.domain,
                "success": r.success,
                "hypothesis": r.hypothesis,
                "skill_patched": r.skill_patched,
                "trajectory_id": r.trajectory_id,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
    }


@app.get("/api/dream/status")
async def get_dream_status(user_id: str = "boss"):
    agent = get_or_create_agent(user_id)
    stats = agent.get_dream_stats()
    return {"success": True, "stats": stats}


# ── WebRTC Browser Screencast Streaming Bridge ──────────────────────────────

class WebRTCOfferPayload(BaseModel):
    session_id: str = Field(..., description="Active session or bot identifier")
    sdp: str = Field(..., description="SDP offer string from client WebRTC peer")
    type: str = Field("offer", description="SDP type, defaults to 'offer'")
    fps: int | None = Field(default=30, description="Target streaming framerate (1-60 FPS)")
    pixel_format: str | None = Field(default="yuv420p", description="Pixel format: yuv420p, bgr24, or rgb24")


class WebRTCIcePayload(BaseModel):
    session_id: str = Field(..., description="Active session or bot identifier")
    candidate: dict[str, Any] = Field(..., description="RTCIceCandidateInit payload or dictionary")


@app.post("/api/webrtc/offer")
async def webrtc_offer(payload: WebRTCOfferPayload):
    """
    WebRTC Signaling: Ingest SDP offer, attach browser screencast track and control data channel,
    and return negotiated SDP answer.
    """
    try:
        from ultron.streaming.webrtc_bridge import webrtc_bridge_manager

        answer = await webrtc_bridge_manager.handle_offer(
            session_id=payload.session_id,
            sdp=payload.sdp,
            sdp_type=payload.type,
            fps=payload.fps or 30,
            pixel_format=payload.pixel_format or "yuv420p",
        )
        return answer
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WebRTC offer negotiation failed: {str(exc)}")


@app.post("/api/webrtc/ice")
async def webrtc_ice(payload: WebRTCIcePayload):
    """
    WebRTC Signaling: Ingest trickle ICE candidates and attach them to the active peer connection.
    """
    try:
        from ultron.streaming.webrtc_bridge import webrtc_bridge_manager

        success = await webrtc_bridge_manager.handle_ice_candidate(
            session_id=payload.session_id,
            candidate_dict=payload.candidate,
        )
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No active WebRTC peer connection found for session '{payload.session_id}'",
            )
        return {"status": "ok", "session_id": payload.session_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WebRTC ICE routing failed: {str(exc)}")


# ── Static UI Mounting ──────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "Ultron Core Online. Place static files in ./static"})


# â”€â”€ Launcher â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    port = int(os.getenv("PORT", "8000"))
    reload_env = os.getenv("ULTRON_RELOAD", "false").lower() in ("true", "1", "yes")
    print("\n" + "=" * 60)
    print("  [ULTRON PROTOCOL] CYBERNETIC MAINFRAME ONLINE")
    print(f"  Access HUD: http://127.0.0.1:{port}")
    print(f"  Speed Optimization: Active (Reload={reload_env})")
    print("=" * 60 + "\n")

    if reload_env:
        uvicorn.run(
            "app:app",
            host="127.0.0.1",
            port=port,
            reload=True,
            reload_excludes=[
                "data/*",
                "chroma_db/*",
                "*.db",
                "*.db-wal",
                "*.db-shm",
                "*.sqlite*",
                "*.json",
                "data/audio/*",
                "data/skills/*",
                "data/email_drafts/*",
                "__pycache__/*",
                "*.log",
            ],
        )
    else:
        uvicorn.run(app, host="127.0.0.1", port=port, reload=False, access_log=False)


if __name__ == "__main__":
    main()



@app.on_event("startup")
async def startup_sweep():
    import os, shutil
    from pathlib import Path
    ephemeral_dir = Path(__file__).resolve().parent / ".ephemeral_uploads"
    if ephemeral_dir.exists():
        print("dY 1 [STARTUP SWEEP] Purging stale ephemeral uploads from previous ungraceful shutdown...")
        shutil.rmtree(ephemeral_dir, ignore_errors=True)
    ephemeral_dir.mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
async def startup_sweep():
    import os, shutil
    from pathlib import Path
    ephemeral_dir = Path(__file__).resolve().parent / ".ephemeral_uploads"
    if ephemeral_dir.exists():
        print("dY 1 [STARTUP SWEEP] Purging stale ephemeral uploads from previous ungraceful shutdown...")
        shutil.rmtree(ephemeral_dir, ignore_errors=True)
    ephemeral_dir.mkdir(parents=True, exist_ok=True)
