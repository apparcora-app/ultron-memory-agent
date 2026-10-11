import logging
import os
from unittest.mock import patch
import pytest
from core.config import check_startup_env

def test_startup_env_check_temp_environments(caplog):
    # 1. Temp env with PERSONAL_EMAIL_USER but missing PERSONAL_EMAIL_PASSWORD
    temp_env_1 = {
        "EMAIL_ENABLED": "false",
        "PERSONAL_EMAIL_USER": "testuser@example.com",
    }
    with patch.dict(os.environ, temp_env_1, clear=True):
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            missing = check_startup_env()
        assert "PERSONAL_EMAIL_PASSWORD" in missing
        # Verify log message names the variable and never the value
        assert any("Missing required environment variable for configured feature: PERSONAL_EMAIL_PASSWORD" in r.message for r in caplog.records)
        assert not any("testuser@example.com" in r.message for r in caplog.records)

    # 2. Temp env with EMAIL_ENABLED=true but missing both personal user and password
    temp_env_2 = {
        "EMAIL_ENABLED": "true",
        "EMAIL_IMAP_HOST": "imap.example.com",
        "EMAIL_SMTP_HOST": "smtp.example.com",
    }
    with patch.dict(os.environ, temp_env_2, clear=True):
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            missing = check_startup_env()
        assert "PERSONAL_EMAIL_USER" in missing
        assert "PERSONAL_EMAIL_PASSWORD" in missing
        assert any("Missing required environment variable for configured feature: PERSONAL_EMAIL_USER" in r.message for r in caplog.records)
        assert any("Missing required environment variable for configured feature: PERSONAL_EMAIL_PASSWORD" in r.message for r in caplog.records)

    # 3. Temp env with WORK_EMAIL_USER set without WORK_EMAIL_PASSWORD
    temp_env_3 = {
        "WORK_EMAIL_USER": "work@example.com",
    }
    with patch.dict(os.environ, temp_env_3, clear=True):
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            missing = check_startup_env()
        assert "WORK_EMAIL_PASSWORD" in missing
        assert any("Missing required environment variable for configured feature: WORK_EMAIL_PASSWORD" in r.message for r in caplog.records)
        assert not any("work@example.com" in r.message for r in caplog.records)
