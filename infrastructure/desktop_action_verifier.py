import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

@dataclass
class ActionVerification:
    action_succeeded: bool
    pre_state: Dict[str, Any]
    post_state: Dict[str, Any]
    state_changed: bool
    retry_reason: Optional[str]

class DesktopActionVerifier:
    SETTLE_DELAY = 1.0
    MAX_RETRIES = 3

    def capture_window_state(self, window_title: str) -> Dict[str, Any]:
        ps_script = f"""
        Add-Type -AssemblyName UIAutomationClient
        Add-Type -TypeDefinition @'
        using System;
        using System.Runtime.InteropServices;
        public class Win32 {{
            [DllImport("user32.dll")]
            public static extern IntPtr GetForegroundWindow();
        }}
'@
        $root = [System.Windows.Automation.AutomationElement]::RootElement
        $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "{window_title}")
        $window = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
        
        if ($null -eq $window) {{
            Write-Output 'WINDOW_NOT_FOUND'
            exit
        }}
        $fg = [Win32]::GetForegroundWindow()
        $is_focused = ($fg -eq $window.Current.NativeWindowHandle)
        if (-not $is_focused) {{
            Write-Output 'WINDOW_NOT_FOCUSED'
            exit
        }}
        
        $trueCond = [System.Windows.Automation.Condition]::TrueCondition
        $descendants = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $trueCond)
        
        $controls = @()
        foreach ($d in $descendants) {{
            $controls += @{{
                Name = $d.Current.Name
                ControlType = $d.Current.ControlType.ProgrammaticName
                IsEnabled = $d.Current.IsEnabled
            }}
        }}
        
        @{{ found = $true; controls = $controls }} | ConvertTo-Json -Depth 5
        """
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            out = result.stdout.strip()
            if not out or out == 'WINDOW_NOT_FOUND' or out == 'WINDOW_NOT_FOCUSED':
                return {"found": False, "controls": []}
            return json.loads(out)
        except Exception as e:
            print(f"Failed to capture window state: {e}")
            return {"found": False, "controls": []}

    def _states_differ(self, pre: Dict[str, Any], post: Dict[str, Any]) -> bool:
        pre_controls = pre.get("controls", [])
        post_controls = post.get("controls", [])
        
        pre_names = {c.get("Name") for c in pre_controls if c.get("Name")}
        post_names = {c.get("Name") for c in post_controls if c.get("Name")}
        
        return pre_names != post_names

    def verify_action(self, window_title: str, execute_fn: Callable, **kwargs) -> ActionVerification:
        pre_state = self.capture_window_state(window_title)
        
        if not pre_state.get('found'):
            return ActionVerification(False, pre_state, {}, False, 'Target window not found or unfocused before action')
        try:
            execute_fn(**kwargs)
            action_succeeded = True
        except Exception as e:
            action_succeeded = False
            return ActionVerification(False, pre_state, {}, False, str(e))
            
        time.sleep(self.SETTLE_DELAY)
        
        post_state = self.capture_window_state(window_title)
        state_changed = self._states_differ(pre_state, post_state)
        
        return ActionVerification(
            action_succeeded=action_succeeded,
            pre_state=pre_state,
            post_state=post_state,
            state_changed=state_changed,
            retry_reason=None if state_changed else "State unchanged after action"
        )
