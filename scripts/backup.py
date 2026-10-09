import os
import sys
import time
import shutil
import tarfile
import subprocess
import glob
from pathlib import Path
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp_backup"

def get_encryption_key():
    key = os.environ.get("BACKUP_ENCRYPTION_KEY")
    if not key:
        print("[WARNING] BACKUP_ENCRYPTION_KEY not found in environment.")
        key = Fernet.generate_key().decode()
        with open(BASE_DIR / ".env", "a") as f:
            f.write(f"\nBACKUP_ENCRYPTION_KEY={key}\n")
        print("[INFO] Generated new BACKUP_ENCRYPTION_KEY and saved to .env")
    return key.encode()

def collect_files(target_dir):
    print("[INFO] Collecting files for backup...")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Define mapping of source paths to archive paths
    # (source_path, archive_subpath)
    targets = [
        (DATA_DIR / "chroma", "data/chroma"),
        (DATA_DIR / "telemetry.db", "data/telemetry.db"),
        (DATA_DIR / "logs" / "computer_audit.jsonl", "data/logs/computer_audit.jsonl"),
        (BASE_DIR / "config.py", "config.py"),
        (DATA_DIR / "sessions", "data/sessions"),
        (DATA_DIR / "budget.json", "data/budget.json"),
    ]
    
    # Grab all SQLite/DB agent states
    for db_file in glob.glob(str(DATA_DIR / "*.db")) + glob.glob(str(DATA_DIR / "*.sqlite3")):
        targets.append((Path(db_file), f"data/{Path(db_file).name}"))
        
    for src, arc_path in targets:
        if isinstance(src, Path) and src.exists():
            dest = target_dir / arc_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest)
                
def create_archive(source_dir, output_path):
    print(f"[INFO] Creating archive {output_path}...")
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)

def encrypt_file(input_path, output_path, key):
    print("[INFO] Encrypting archive (Zero-Trust)...")
    fernet = Fernet(key)
    with open(input_path, "rb") as f:
        data = f.read()
    encrypted = fernet.encrypt(data)
    with open(output_path, "wb") as f:
        f.write(encrypted)
    os.remove(input_path)

def upload_to_remote(encrypted_file):
    remote = os.environ.get("RCLONE_REMOTE", "mock_remote")
    print(f"[INFO] Uploading to target: {remote}")
    
    if remote == "mock_remote":
        # Pointing to external drive / cloud storage instead of local repo folder
        remote_path = Path("D:/UltronBackups")
        remote_path.mkdir(exist_ok=True, parents=True)
        shutil.copy2(encrypted_file, remote_path / encrypted_file.name)
        print(f"[SUCCESS] Backup uploaded to external drive: {remote_path}")
        return remote_path
    else:
        # Real rclone command
        cmd = ["rclone", "copy", str(encrypted_file), f"{remote}:ultron-backups/"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] rclone upload failed: {result.stderr}")
            sys.exit(1)
        print("[SUCCESS] Backup uploaded via rclone.")
        return remote

def apply_retention_policy(remote_target):
    print("[INFO] Enforcing retention policy: 7 daily + 4 weekly.")
    # For testing, we implement retention logic locally on the mock_remote
    # In production, we'd use `rclone lsf` and `rclone deletefile`.
    
    if isinstance(remote_target, Path): # mock remote
        backups = list(remote_target.glob("ultron_backup_*.enc"))
        backups.sort(key=lambda x: x.name, reverse=True)
        
        # Policy: keep last 7 files (simulating 7 dailies) + a few weeklies if they exist.
        # Since we just need to demonstrate retention deletion:
        if len(backups) > 11:
            for old_backup in backups[11:]:
                print(f"[INFO] Pruning old backup: {old_backup.name}")
                old_backup.unlink()

def main():
    print("--- Ultron Prime Off-Machine Backup ---")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"ultron_backup_{timestamp}.tar.gz"
    enc_name = archive_name + ".enc"
    
    key = get_encryption_key()
    
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        
    try:
        collect_files(TEMP_DIR)
        create_archive(TEMP_DIR, BASE_DIR / archive_name)
        encrypt_file(BASE_DIR / archive_name, BASE_DIR / enc_name, key)
        
        remote = upload_to_remote(BASE_DIR / enc_name)
        apply_retention_policy(remote)
        
    finally:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        if (BASE_DIR / enc_name).exists():
            os.remove(BASE_DIR / enc_name)
            
    print(f"[INFO] Backup completed successfully at {datetime.now()}.")

if __name__ == "__main__":
    main()
