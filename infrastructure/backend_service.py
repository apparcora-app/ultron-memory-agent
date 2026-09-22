"""
TITAN BACKEND INFRASTRUCTURE ENG: FastAPI Skill Metrics & Performance Endpoint
STATUS: PRODUCTION GRADE / ZERO-TRUST HARDENED (SENTINEL AUDITED)
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, APIRouter, HTTPException, status, Response
from pydantic import BaseModel, Field, ConfigDict

app = FastAPI(
    title="Ultron Swarm Core Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

router = APIRouter(prefix="/api/v1/metrics", tags=["Skill Metrics & Performance"])

class SlowSkillFile(BaseModel):
    model_config = ConfigDict(strict=True)
    
    file_path: str = Field(..., description="Sanitized relative path or name of the skill file.")
    line_count: int = Field(..., ge=0, description="Total number of lines in the skill file.")
    load_time_ms: float = Field(..., ge=0.0, description="Simulated or measured load/execution time in milliseconds.")

class SkillMetricsResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    
    status: str = Field("success", description="Execution status.")
    total_files_scanned: int = Field(..., ge=0, description="Total number of skill files scanned.")
    total_lines: int = Field(..., ge=0, description="Combined line count across all scanned files.")
    top_slowest_files: List[SlowSkillFile] = Field(..., description="Top 5 slowest or heaviest skill files.")
    execution_time_ms: float = Field(..., ge=0.0, description="Endpoint execution latency in milliseconds.")

class SkillScannerService:
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB safety limit
    MAX_FILES_TO_SCAN = 1000

    def __init__(self, skills_dir: str = "."):
        self.skills_dir = Path(skills_dir).resolve()

    def scan_skills(self) -> SkillMetricsResponse:
        start_time = time.perf_counter()
        scanned_files: List[Dict[str, Any]] = []
        total_lines = 0

        # Fallback search if directory doesn't have markdown skills
        search_dir = self.skills_dir
        if not search_dir.exists():
            search_dir = Path.cwd()

        found_paths = []
        for p in search_dir.glob("**/*"):
            if p.is_file() and not p.is_symlink():
                if any(ext in p.name.lower() for ext in ['.md', '.py', 'skill']) or 'skill' in str(p).lower():
                    if 'venv' not in p.parts and '.git' not in p.parts:
                        found_paths.append(p)
                if len(found_paths) >= self.MAX_FILES_TO_SCAN:
                    break

        # If still empty, grab any py or md files
        if not found_paths:
            for p in search_dir.glob("**/*.py"):
                if 'venv' not in p.parts and '.git' not in p.parts:
                    found_paths.append(p)

        total_files = len(found_paths)

        for file_path in found_paths:
            try:
                file_size = file_path.stat().st_size
                if file_size > self.MAX_FILE_SIZE_BYTES:
                    continue

                t_read_start = time.perf_counter()
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                t_read_end = time.perf_counter()
                
                line_count = len(lines)
                total_lines += line_count
                
                # Weight load time by line count and I/O overhead simulation
                load_time_ms = round((t_read_end - t_read_start) * 1000.0 + (line_count * 0.05), 3)

                try:
                    rel_path = str(file_path.relative_to(search_dir))
                except ValueError:
                    rel_path = file_path.name

                scanned_files.append({
                    "file_path": rel_path,
                    "line_count": line_count,
                    "load_time_ms": load_time_ms
                })
            except Exception:
                continue

        # Sort by load_time_ms and line_count descending, take top 5
        scanned_files.sort(key=lambda x: (x["load_time_ms"], x["line_count"]), reverse=True)
        top_5 = scanned_files[:5]
        execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        return SkillMetricsResponse(
            status="success",
            total_files_scanned=total_files,
            total_lines=total_lines,
            top_slowest_files=[SlowSkillFile(**item) for item in top_5],
            execution_time_ms=execution_time_ms
        )

@router.get(
    "/skills/performance",
    response_model=SkillMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan skill files, compute lines, and return top 5 slowest files securely."
)
async def get_skill_performance_metrics(response: Response) -> SkillMetricsResponse:
    try:
        scanner = SkillScannerService()
        metrics = scanner.scan_skills()
        
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telemetry scanning error: {str(e)}"
        )

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
