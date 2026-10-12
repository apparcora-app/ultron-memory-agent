import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ultron.core.config import AgentConfig


def get_cutoff_date(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)

EXEMPT_RECORDS = {
    # Specifically exempt the 8 items restored from the backup
    "boss_chat_1788554265_23452d.json",
    "agent_log_1788599901_33a11b.json",
    "boss_chat_1788771190_123bca.json",
    "task_eval_1788910023_88ff91.json",
    "boss_chat_1789052144_0b24dc.json",
    "context_1788554265.json",
    "state_1788771190.json",
    "tel_1788554265_ab12",  # Event ID
    "8820",  # Request ID
}

def parse_iso_date(date_str: str) -> datetime:
    try:
        # Python 3.11 fromisoformat supports Z and offsets natively
        return datetime.fromisoformat(date_str).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def purge_telemetry(db_path: Path, cutoff: datetime, dry_run: bool) -> tuple[int, list[str]]:
    if not db_path.exists():
        return 0, []
    cutoff_ts = cutoff.timestamp()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT event_id FROM audit_logs WHERE timestamp < ? AND event_id NOT IN ('tel_1788554265_ab12') ORDER BY timestamp ASC",
        (cutoff_ts,)
    )
    rows = cur.fetchall()
    candidate_ids = [r[0] for r in rows if r[0] not in EXEMPT_RECORDS]
    count = len(candidate_ids)
    samples = candidate_ids[:5]

    if count > 0 and not dry_run:
        cur.execute(
            "DELETE FROM audit_logs WHERE timestamp < ? AND event_id NOT IN ('tel_1788554265_ab12')",
            (cutoff_ts,)
        )
        conn.commit()
        cur.execute("VACUUM")
    conn.close()
    return count, samples

def purge_jsonl(file_path: Path, cutoff: datetime, dry_run: bool) -> tuple[int, list[str]]:
    if not file_path.exists():
        return 0, []

    purged_ids = []
    kept_lines = []

    with open(file_path, encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                ts_str = data.get("timestamp", "")
                req_id = str(data.get("req_id", "") or data.get("event_id", "") or data.get("task_id", "") or f"line_{idx}")

                if ts_str and parse_iso_date(ts_str) < cutoff:
                    if req_id not in EXEMPT_RECORDS and str(data.get("req_id", "")) not in EXEMPT_RECORDS:
                        purged_ids.append(req_id)
                    else:
                        kept_lines.append(line)
                else:
                    kept_lines.append(line)
            except json.JSONDecodeError:
                kept_lines.append(line)

    count = len(purged_ids)
    samples = purged_ids[:5]

    if count > 0 and not dry_run:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(kept_lines)

    return count, samples

def purge_json_dir(dir_path: Path, cutoff: datetime, dry_run: bool) -> tuple[int, list[str]]:
    if not dir_path.exists():
        return 0, []
    candidate_names = []
    for item in dir_path.glob("*.json"):
        if not item.is_file():
            continue

        mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff and item.name not in EXEMPT_RECORDS:
            candidate_names.append(item.name)
            if not dry_run:
                item.unlink()
    return len(candidate_names), candidate_names[:5]

def purge_mem0_chroma(data_dir: Path, cutoff: datetime, dry_run: bool, enabled: bool) -> tuple[int, list[str]]:
    if not enabled:
        return 0, []

    chroma_dir = data_dir / "chroma"
    if not chroma_dir.exists():
        return 0, []

    purged_ids = []
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collections = client.list_collections()
        target_cols = [c for c in collections if "mem0" in c.name]

        for col in target_cols:
            all_records = col.get(include=["metadatas"])
            ids = all_records.get("ids", [])
            metadatas = all_records.get("metadatas", [])

            ids_to_delete = []
            for mem_id, meta in zip(ids, metadatas, strict=False):
                if mem_id in EXEMPT_RECORDS:
                    continue
                created_at_str = (meta or {}).get("created_at") or (meta or {}).get("updated_at")
                if created_at_str:
                    try:
                        mem_date = parse_iso_date(created_at_str)
                        if mem_date < cutoff:
                            purged_ids.append(mem_id)
                            ids_to_delete.append(mem_id)
                    except Exception:
                        pass

            if ids_to_delete and not dry_run:
                col.delete(ids=ids_to_delete)
    except Exception:
        # Fallback to MemoryManager if direct chromadb access errors
        try:
            from ultron.memory.memory_manager import MemoryManager
            for uid in ["boss", "reach", "default_user", "operator", "dave_test2"]:
                manager = MemoryManager(user_id=uid)
                if not manager.mem:
                    continue
                try:
                    memories = manager.mem.get_all(filters={"user_id": uid})
                    if isinstance(memories, dict):
                        memories = memories.get("results", [])
                except Exception:
                    memories = []
                for mem in memories or []:
                    m_id = mem.get("id")
                    if m_id in EXEMPT_RECORDS:
                        continue
                    c_str = mem.get("created_at") or mem.get("updated_at")
                    if c_str and parse_iso_date(c_str) < cutoff:
                        purged_ids.append(m_id)
                        if not dry_run:
                            manager.delete(m_id)
        except Exception:
            pass

    return len(purged_ids), purged_ids[:5]

def run_pii_cleanup(dry_run: bool = False):
    config = AgentConfig()

    sessions_retention = config.sessions_retention_days
    telemetry_retention = config.telemetry_retention_days
    audit_log_retention = config.audit_log_retention_days
    blackboard_retention = config.blackboard_retention_days
    purge_mem0 = config.purge_mem0

    # Calculate cutoffs
    s_cutoff = get_cutoff_date(sessions_retention)
    t_cutoff = get_cutoff_date(telemetry_retention)
    a_cutoff = get_cutoff_date(audit_log_retention)
    b_cutoff = get_cutoff_date(blackboard_retention)
    m_cutoff = get_cutoff_date(sessions_retention)  # 90-day retention if Mem0 enabled

    mode_str = "[DRY-RUN]" if dry_run else "[LIVE]"
    print("======================================================================")
    print(f"--- {mode_str} Automated Data Retention & PII Lifecycle Purge ---")
    print("Settings in use:")
    print(f"  • SESSIONS_RETENTION_DAYS:   {sessions_retention:3d} days (cutoff: {s_cutoff.isoformat()})")
    print(f"  • TELEMETRY_RETENTION_DAYS:  {telemetry_retention:3d} days (cutoff: {t_cutoff.isoformat()})")
    print(f"  • AUDIT_LOG_RETENTION_DAYS: {audit_log_retention:3d} days (cutoff: {a_cutoff.isoformat()})")
    print(f"  • BLACKBOARD_RETENTION_DAYS: {blackboard_retention:3d} days (cutoff: {b_cutoff.isoformat()})")
    mem0_status = "ENABLED" if purge_mem0 else "DISABLED (retained for personal use)"
    print(f"  • PURGE_MEM0:               {str(purge_mem0):5s} ({mem0_status})")
    print("======================================================================")

    base_dir = Path(__file__).resolve().parent
    data_dir = Path(os.environ.get("ULTRON_DATA_DIR", base_dir / "data"))
    print(f"Data directory: {data_dir}")
    print()

    # 1. Telemetry DB
    t_count, t_samples = purge_telemetry(data_dir / "telemetry.db", t_cutoff, dry_run)
    print(f"{mode_str} Telemetry DB (telemetry.db):")
    print(f"  Count: {t_count} records purged")
    print(f"  First 5 event IDs: {t_samples}")
    print()

    # 2. Computer Audit JSONL
    a_count, a_samples = purge_jsonl(data_dir / "logs" / "computer_audit.jsonl", a_cutoff, dry_run)
    print(f"{mode_str} Computer Audit Log (logs/computer_audit.jsonl):")
    print(f"  Count: {a_count} records purged")
    print(f"  First 5 request IDs: {a_samples}")
    print()

    # 3. Sessions
    s_count, s_samples = purge_json_dir(data_dir / "sessions", s_cutoff, dry_run)
    print(f"{mode_str} Sessions (data/sessions/):")
    print(f"  Count: {s_count} files purged")
    print(f"  First 5 session files: {s_samples}")
    print()

    # 4. Blackboard
    b_count, b_samples = purge_json_dir(data_dir / "blackboard", b_cutoff, dry_run)
    print(f"{mode_str} Blackboard (data/blackboard/):")
    print(f"  Count: {b_count} files purged")
    print(f"  First 5 blackboard files: {b_samples}")
    print()

    # 5. Mem0/Chroma
    m_count, m_samples = purge_mem0_chroma(data_dir, m_cutoff, dry_run, enabled=purge_mem0)
    print(f"{mode_str} Mem0/Chroma Vector Store:")
    if not purge_mem0:
        print("  Count: 0 entries purged (SKIPPED: PURGE_MEM0=false)")
    else:
        print(f"  Count: {m_count} entries purged")
    print(f"  First 5 memory IDs: {m_samples}")
    print()

    total = t_count + a_count + s_count + b_count + m_count
    print("----------------------------------------------------------------------")
    print(f"{mode_str} Total records/files purged across all categories: {total}")
    if dry_run:
        print(f"{mode_str} Real deletion was SKIPPED. Zero files or database records were modified.")
    print("======================================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated PII Retention Purge")
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without executing")
    args = parser.parse_args()

    run_pii_cleanup(dry_run=args.dry_run)
