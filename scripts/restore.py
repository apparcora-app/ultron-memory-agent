import os
import sys
import shutil
import tarfile
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

def get_encryption_key():
    key = os.environ.get("BACKUP_ENCRYPTION_KEY")
    if not key:
        print("[ERROR] BACKUP_ENCRYPTION_KEY not found in environment. Cannot decrypt.")
        sys.exit(1)
    return key.encode()

def decrypt_file(input_path, output_path, key):
    print(f"[INFO] Decrypting {input_path.name}...")
    fernet = Fernet(key)
    with open(input_path, "rb") as f:
        encrypted = f.read()
    try:
        decrypted = fernet.decrypt(encrypted)
    except Exception as e:
        print(f"[ERROR] Decryption failed (wrong key or corrupt file): {e}")
        sys.exit(1)
        
    with open(output_path, "wb") as f:
        f.write(decrypted)

def extract_archive(archive_path, extract_to):
    print(f"[INFO] Extracting {archive_path.name} to {extract_to}...")
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(path=extract_to)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ultron Prime Restore Utility")
    parser.add_argument("backup_path", help="Path to the encrypted backup file (.enc)")
    args = parser.parse_args()
        
    enc_path = Path(args.backup_path)
    if not enc_path.exists():
        print(f"[ERROR] File not found: {enc_path}")
        sys.exit(1)
        
    print("--- Ultron Prime Restore Utility ---")
    key = get_encryption_key()
    
    tar_path = enc_path.with_suffix('') # remove .enc
    temp_restore = BASE_DIR / "temp_restore"
    
    try:
        decrypt_file(enc_path, tar_path, key)
        extract_archive(tar_path, temp_restore)
        
        # The archive contains a top-level folder "temp_backup"
        # We need to copy its contents back to BASE_DIR
        extracted_content = temp_restore / "temp_backup"
        if extracted_content.exists():
            print("[INFO] Merging restored files into workspace...")
            shutil.copytree(extracted_content, BASE_DIR, dirs_exist_ok=True)
            print("[SUCCESS] Restore completed successfully.")
        else:
            print("[ERROR] Unexpected archive structure.")
            
    finally:
        if tar_path.exists():
            os.remove(tar_path)
        if temp_restore.exists():
            shutil.rmtree(temp_restore)

if __name__ == "__main__":
    main()
