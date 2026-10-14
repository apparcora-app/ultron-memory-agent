"""
consolidate_sessions.py — Consolidate authentic user chats into canonical storage and purge test pollution.
"""

import io
import json
import os
import re
import tarfile
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "data" / "sessions"
CANONICAL_DIR.mkdir(parents=True, exist_ok=True)

SRC_SESSIONS_DIR = REPO_ROOT / "src" / "ultron" / "memory" / "data" / "sessions"

load_dotenv(REPO_ROOT / ".env")
key = os.environ.get("BACKUP_ENCRYPTION_KEY")
fernet = Fernet(key.encode()) if key else None

SYNTHETIC_PATTERNS = [
    r"confirm your active",
    r"stitch verification",
    r"pii_session",
    r"pii_terminal",
    r"test_redaction",
    r"terminal_test",
]

def is_synthetic(data: dict) -> bool:
    title = (data.get("title") or "").strip().lower()
    for pat in SYNTHETIC_PATTERNS:
        if re.search(pat, title):
            return True
    # Check messages for synthetic automated ping signatures
    msgs = data.get("messages", [])
    if len(msgs) <= 2 and msgs:
        combined = " ".join([str(m.get("text", "")).lower() for m in msgs])
        if any(re.search(pat, combined) for pat in SYNTHETIC_PATTERNS):
            return True
    return False

def main():
    candidates = {}  # normalized_sid -> dict

    def ingest_session(data: dict, source_label: str):
        if not isinstance(data, dict):
            return
        msgs = data.get("messages", [])
        if len(msgs) == 0:
            return  # Skip empty drafts
        if is_synthetic(data):
            return  # Skip test fixtures

        raw_id = str(data.get("id") or "").strip()
        user_id = (data.get("user_id") or "boss").strip().lower()
        if user_id in ("default_user", ""):
            user_id = "boss"

        clean_user = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)
        # Strip user prefix if present in raw_id
        if raw_id.startswith(f"{clean_user}_"):
            raw_id = raw_id[len(clean_user) + 1 :]
        clean_sid = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_id)
        if not clean_sid:
            return

        msg_count = len(msgs)
        upd = data.get("updated_at") or ""

        if clean_sid not in candidates or msg_count > candidates[clean_sid]["msg_count"]:
            data["id"] = clean_sid
            data["user_id"] = clean_user
            candidates[clean_sid] = {
                "user_id": clean_user,
                "session_id": clean_sid,
                "msg_count": msg_count,
                "updated_at": upd,
                "title": data.get("title", "Untitled Directive"),
                "source": source_label,
                "data": data,
            }

    # 1. Ingest from local filesystem sources
    filesystem_dirs = [
        CANONICAL_DIR,
        SRC_SESSIONS_DIR,
        Path("E:/Personal Data/Apps/AI Agents/ultron-scratch/temp_compare/temp_backup/data/sessions"),
        Path("E:/Personal Data/Apps/AI Agents/data-backup-20261011_083354/sessions"),
        Path("E:/Personal Data/Apps/AI Agents/data-backup-20261011_070853/sessions"),
        Path("E:/Personal Data/Apps/AI Agents/data-backup-20261010_023846/sessions"),
        Path("E:/Personal Data/Apps/AI Agents/data-backup-20261010_021607/sessions"),
    ]

    for d in filesystem_dirs:
        if not d.exists():
            continue
        for p in d.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    ingest_session(json.load(f), str(p))
            except Exception as e:
                print(f"[WARN] Error reading {p}: {e}")

    # 2. Ingest from encrypted remote backups
    if fernet:
        for enc_file in (REPO_ROOT / "mock_remote").glob("*.enc"):
            try:
                with open(enc_file, "rb") as fp:
                    dec = fernet.decrypt(fp.read())
                with tarfile.open(fileobj=io.BytesIO(dec), mode="r:gz") as tar:
                    for m in tar.getmembers():
                        if "sessions/" in m.name and m.name.endswith(".json"):
                            f = tar.extractfile(m)
                            if f:
                                ingest_session(json.load(f), f"{enc_file.name}:{m.name}")
            except Exception as e:
                print(f"[WARN] Error in backup {enc_file.name}: {e}")

    print(f"Total authentic user conversations discovered: {len(candidates)}")

    # 3. Clean up synthetic/empty junk from canonical dir and src sessions dir
    for target_dir in [CANONICAL_DIR, SRC_SESSIONS_DIR]:
        if not target_dir.exists():
            continue
        for p in target_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if is_synthetic(data) or len(data.get("messages", [])) == 0:
                    p.unlink()
                    print(f"  [-] Pruned test artifact: {p.name}")
            except Exception:
                pass

    # 4. Write all consolidated authentic sessions into canonical storage
    # Also mirror into SRC_SESSIONS_DIR so legacy or test runners see the exact same store
    for sid, info in sorted(candidates.items(), key=lambda x: -x[1]["msg_count"]):
        filename = f"{info['user_id']}_{sid}.json"
        target_path = CANONICAL_DIR / filename
        mirror_path = SRC_SESSIONS_DIR / filename

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(info["data"], f, indent=2, ensure_ascii=False)

        if SRC_SESSIONS_DIR.exists():
            with open(mirror_path, "w", encoding="utf-8") as f:
                json.dump(info["data"], f, indent=2, ensure_ascii=False)

        print(f"  [+] Consolidated: {filename:35s} | {info['msg_count']:3d} msgs | {info['title']}")

    print("\n[SUCCESS] Chat session consolidation completed successfully.")

if __name__ == "__main__":
    main()
