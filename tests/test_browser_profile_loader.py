import json
import logging
import os
import tempfile
from unittest.mock import patch
import pytest
from core.tool_definitions import ToolExecutor

def test_browser_profile_loader_scenarios(caplog):
    te = ToolExecutor()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        te._project_root = tmpdir
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir, exist_ok=True)
        profiles_file = os.path.join(data_dir, "browser_profiles.local.json")

        with patch("subprocess.Popen") as mock_popen:
            # 1. Missing file: fallback without warning or crash
            res_missing = te._handle_open_browser({"url": "https://example.com", "profile": "custom_missing"})
            assert res_missing["success"] is True
            assert mock_popen.called
            mock_popen.reset_mock()

            # 2. File with UTF-8 BOM
            with open(profiles_file, "w", encoding="utf-8-sig") as f:
                f.write('{"custom_bom": "Profile 9"}')
            
            res_bom = te._handle_open_browser({"url": "https://example.com", "profile": "custom_bom"})
            assert res_bom["success"] is True
            assert "Profile 'Profile 9'" in res_bom["output"]
            mock_popen.reset_mock()

            # 3. File without BOM
            with open(profiles_file, "w", encoding="utf-8") as f:
                f.write('{"custom_nobom": "Profile 8"}')
            
            res_nobom = te._handle_open_browser({"url": "https://example.com", "profile": "custom_nobom"})
            assert res_nobom["success"] is True
            assert "Profile 'Profile 8'" in res_nobom["output"]
            mock_popen.reset_mock()

            # 4. Invalid JSON: logged warning with file name and error type only
            with open(profiles_file, "w", encoding="utf-8") as f:
                f.write("INVALID_JSON{{{")
            
            with caplog.at_level(logging.WARNING):
                res_invalid = te._handle_open_browser({"url": "https://example.com", "profile": "default"})
                assert res_invalid["success"] is True
                
            assert any(
                "Failed to load browser profiles from browser_profiles.local.json: JSONDecodeError" in record.message
                for record in caplog.records
            )
