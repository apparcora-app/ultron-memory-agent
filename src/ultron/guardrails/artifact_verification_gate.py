import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactContract:
    contract_type: str
    expected_artifacts: list[str] = field(default_factory=list)
    min_output_length: int = 50

@dataclass
class VerificationResult:
    passed: bool
    contract_type: str
    violations: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

class ArtifactVerificationGate:
    def infer_contract(self, user_input: str, tool_actions: list[dict[str, Any]]) -> ArtifactContract:
        contract_type = "INFO_QUERY"
        expected_artifacts = []
        min_output_length = 50

        user_input_lower = user_input.lower()
        analysis_keywords = ['analyze', 'reconcil', 'audit', 'check', 'excel', 'xlsx', 'csv', 'data']
        has_analysis_keyword = any(kw in user_input_lower for kw in analysis_keywords)

        for action in tool_actions:
            tool_name = action.get('name', '')
            kwargs = action.get('args', {})

            if tool_name == 'file_operation' and kwargs.get('operation') in ['write', 'create']:
                contract_type = "FILE_WRITE"
                if 'path' in kwargs:
                    expected_artifacts.append(kwargs['path'])

            elif tool_name == 'run_python' and has_analysis_keyword:
                contract_type = "FILE_ANALYSIS"
                min_output_length = 100

            elif tool_name == 'send_email':
                contract_type = "EMAIL_SEND"

            elif tool_name in ['control_desktop_gui', 'open_application']:
                contract_type = "DESKTOP_ACTION"

        return ArtifactContract(
            contract_type=contract_type,
            expected_artifacts=expected_artifacts,
            min_output_length=min_output_length
        )

    def verify(self, contract: ArtifactContract, tool_actions: list[dict[str, Any]], draft_reply: str) -> VerificationResult:
        if contract.contract_type == "FILE_WRITE":
            return self._verify_file_write(contract)
        elif contract.contract_type == "FILE_ANALYSIS":
            return self._verify_file_analysis(contract, tool_actions)
        elif contract.contract_type == "EMAIL_SEND":
            return self._verify_email(tool_actions)
        elif contract.contract_type == "DESKTOP_ACTION":
            return self._verify_desktop(tool_actions)
        else:
            return VerificationResult(passed=True, contract_type=contract.contract_type)

    def _verify_file_write(self, contract: ArtifactContract) -> VerificationResult:
        violations = []
        evidence = {}
        for path in contract.expected_artifacts:
            if not os.path.exists(path):
                violations.append(f"File not created: {path}")
            elif os.path.getsize(path) == 0:
                violations.append(f"File is empty: {path}")
            else:
                evidence[path] = {"size": os.path.getsize(path)}

        passed = len(violations) == 0
        return VerificationResult(passed=passed, contract_type=contract.contract_type, violations=violations, evidence=evidence)

    def _verify_file_analysis(self, contract: ArtifactContract, tool_actions: list[dict[str, Any]]) -> VerificationResult:
        violations = []
        evidence = {}
        for action in tool_actions:
            if action.get('name') == 'run_python':
                output = action.get('output', '')
                evidence['output_length'] = len(output)
                if len(output) < contract.min_output_length:
                    violations.append(f"Output length {len(output)} is less than minimum {contract.min_output_length}")
                if "script executed" in output.lower() and len(output) < contract.min_output_length * 2:
                     violations.append("Output appears to just confirm execution without substantial analysis")

        passed = len(violations) == 0
        return VerificationResult(passed=passed, contract_type=contract.contract_type, violations=violations, evidence=evidence)

    def _verify_email(self, tool_actions: list[dict[str, Any]]) -> VerificationResult:
        violations = []
        for action in tool_actions:
            if action.get('name') == 'send_email':
                output = action.get('output', '')
                if '250 OK' not in output and '250 2.0.0 OK' not in output:
                    violations.append(f"SMTP 250 OK not found in output: {output}")
        passed = len(violations) == 0
        return VerificationResult(passed=passed, contract_type="EMAIL_SEND", violations=violations)

    def _verify_desktop(self, tool_actions: list[dict[str, Any]]) -> VerificationResult:
        violations = []
        for action in tool_actions:
            if action.get('name') in ['control_desktop_gui', 'open_application']:
                output = action.get('output', {})
                if isinstance(output, dict) and not output.get('success', False):
                    violations.append(f"Desktop action failed: {action.get('name')}")
                elif isinstance(output, str) and 'error' in output.lower():
                    violations.append(f"Desktop action reported error: {output}")
        passed = len(violations) == 0
        return VerificationResult(passed=passed, contract_type="DESKTOP_ACTION", violations=violations)
