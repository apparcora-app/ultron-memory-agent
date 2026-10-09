import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from app import chat_endpoint
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

async def run():
    print("--- ADVERSARIAL TEST 2: Swallowed Exception in File Upload ---")
    
    # We mock 'builtins.open' to throw PermissionError ONLY when writing our test file.
    original_open = open
    def fake_open(file, *args, **kwargs):
        if 'test_upload.txt' in str(file):
            raise PermissionError("Simulated permission denied for testing swallowed exception")
        return original_open(file, *args, **kwargs)

    mock_file = MagicMock()
    mock_file.filename = "test_upload.txt"
    
    # For await uploaded_file.read()
    async def mock_read():
        return b"dummy content"
    mock_file.read = mock_read

    with patch('builtins.open', side_effect=fake_open):
        try:
            await chat_endpoint(
                user_id="boss",
                session_id=None,
                message="Analyze this file",
                module_id="none",
                model_override="",
                model_mode="",
                optimize_prompt='false',
                operation_mode="chat",
                files=[mock_file]
            )
            print("Failed! Handled the exception silently and returned successfully.")
        except HTTPException as e:
            print(f"Success! Caught HTTPException: {e.status_code} - {e.detail}")

if __name__ == "__main__":
    asyncio.run(run())
