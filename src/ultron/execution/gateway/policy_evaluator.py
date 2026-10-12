"""
policy_evaluator.py — Zero-Trust Security Gateway Policy Evaluator for Ultron Computer Execution.

Enforces a strict default-deny, allowlist-first security model with secondary hard-deny
layers for shell commands, network targets, DNS rebinding prevention, and host secret isolation.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import urllib.parse
from collections.abc import Callable, Sequence

from ultron.execution.computer_contracts import ActionType, ComputerAction, PolicyRule

# Safe system environment variables permitted for execution passthrough
SAFE_ENV_PASSTHROUGH = frozenset({
    "PATH", "PATHEXT", "LANG", "LC_ALL", "LC_CTYPE", "TERM",
    "TMP", "TEMP", "TMPDIR", "SYSTEMROOT", "COMSPEC",
    "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "USERNAME", "USER",
    "SHELL", "PWD", "EDITOR",
})

# Substrings in variable names that indicate secret/credential material
SENSITIVE_ENV_SUBSTRINGS = (
    "KEY", "SECRET", "TOKEN", "PASS", "PASSWORD", "AUTH",
    "CREDENTIAL", "PRIVATE", "DATABASE_URL", "CONN_STR", "SIGNING",
)

# Known metadata hostnames (cloud provider instance metadata services)
METADATA_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.azure.com",
    "instance-data",
    "metadata",
})

# Prohibited IPv4 networks (Loopback, Link-Local/Metadata, Private RFC 1918, CGNAT, Reserved)
PROHIBITED_IPV4_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
)

# Prohibited IPv6 networks (Loopback, Link-Local, Unique Local RFC 4193, Multicast)
PROHIBITED_IPV6_NETWORKS = (
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("2001:db8::/32"),
)


# Note: Pattern matching alone cannot catch all obfuscation (base64-encoded payloads, unicode homoglyphs, variable-expansion tricks) — this is defense-in-depth on top of the allowlist, not a substitute for it.
SHELL_HARD_DENY_PATTERNS = (
    # rm -rf and recursive destructive deletions
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b", re.IGNORECASE), "rm -rf recursive force deletion"),
    (re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b", re.IGNORECASE), "rm -rf recursive force deletion"),
    (re.compile(r"\brm\s+.*--recursive.*--force", re.IGNORECASE), "rm --recursive --force deletion"),
    (re.compile(r"\brm\s+.*--force.*--recursive", re.IGNORECASE), "rm --force --recursive deletion"),
    (re.compile(r"\brmdir\s+/[sS]\b", re.IGNORECASE), "Windows recursive rmdir"),
    (re.compile(r"\bdel\s+/[sS]?[fFqQ]\b", re.IGNORECASE), "Windows force deletion"),
    # Filesystem creation / formatting
    (re.compile(r"\bmkfs(\.[a-zA-Z0-9]+)?\b", re.IGNORECASE), "Filesystem creation (mkfs)"),
    (re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE), "Disk formatting (format drive:)"),
    (re.compile(r"\bformat\.com\b", re.IGNORECASE), "Windows format.com utility"),
    (re.compile(r"\b(fdisk|gdisk|parted|diskpart)\b", re.IGNORECASE), "Disk partitioning utility"),
    # Fork bombs
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE), "Bash fork bomb"),
    (re.compile(r":\(\)\{.*:\|:&\};:", re.IGNORECASE), "Compact fork bomb"),
    # System power state changes
    (re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.IGNORECASE), "System shutdown/reboot/halt"),
    (re.compile(r"\binit\s+[06]\b", re.IGNORECASE), "SysV init halt/reboot"),
    # Raw disk block overwrites
    (re.compile(r"\bdd\b.*\bof=/dev/", re.IGNORECASE), "Raw device overwrite via dd"),
    # Privilege escalation attempts
    (re.compile(r"\b(sudo|doas|runas)\b", re.IGNORECASE), "Privilege escalation (sudo/doas/runas)"),
    (re.compile(r"\bsu\b", re.IGNORECASE), "Switch user (su)"),
    (re.compile(r"\bchmod\s+[ugoa]*\+s\b", re.IGNORECASE), "SUID/SGID bit setting"),
    (re.compile(r"\bchown\s+root\b", re.IGNORECASE), "Root ownership change"),
    # Pipe-to-shell execution patterns
    (re.compile(r"(curl|wget|fetch)\b.*\|\s*(ba|z)?sh\b", re.IGNORECASE), "Pipe web content to shell (curl/wget | sh)"),
    (re.compile(r"(curl|wget|fetch)\b.*\|\s*powershell\b", re.IGNORECASE), "Pipe web content to PowerShell"),
    (re.compile(r"\|\s*(ba|z)?sh\b", re.IGNORECASE), "Pipe to shell interpreter"),
    (re.compile(r"\|\s*powershell\b", re.IGNORECASE), "Pipe to PowerShell interpreter"),
    (re.compile(r"\|\s*iex\b", re.IGNORECASE), "PowerShell Invoke-Expression pipe (| iex)"),
    (re.compile(r"\biex\s*\(", re.IGNORECASE), "PowerShell iex invocation"),
    (re.compile(r"\bInvoke-Expression\b", re.IGNORECASE), "PowerShell Invoke-Expression cmdlet"),
    (re.compile(r"python\b.*\|\s*(ba|z)?sh\b", re.IGNORECASE), "Python stdout piped to shell"),
)


class PolicyEvaluator:
    """
    Zero-Trust Security Gateway Policy Evaluator for Ultron Computer Actions.

    Architecture:
      1. Default-Deny, Allowlist-First: Actions are refused unless an explicit ALLOW PolicyRule
         matches the action_type and pattern.
      2. Secondary Hard-Deny Layer: An allow match never overrides a deny match. Non-negotiable
         blocks on destructive shell commands, SSRF/private networks, cloud metadata services,
         and DNS rebinding.
      3. Environment Sanitization: Strips host environment variables and secrets to prevent leaks.
    """

    def __init__(
        self,
        rules: Sequence[PolicyRule] | None = None,
        dns_resolver: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.rules: list[PolicyRule] = list(rules) if rules is not None else []
        self.dns_resolver: Callable[[str], list[str]] = dns_resolver or self._default_dns_resolver

    @staticmethod
    def _default_dns_resolver(hostname: str) -> list[str]:
        """Resolve a hostname to IPv4/IPv6 addresses using socket.getaddrinfo."""
        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            # info[4][0] contains the IP address string
            return sorted(list({info[4][0] for info in addr_info}))
        except socket.gaierror as exc:
            raise RuntimeError(f"DNS resolution failed for '{hostname}': {exc}") from exc

    def add_rule(self, rule: PolicyRule) -> None:
        """Register a new policy rule."""
        self.rules.append(rule)

    def sanitize_environment(self, env: dict[str, str] | None = None) -> dict[str, str]:
        """
        Strip host environment variables and system secrets.
        Only allows known-safe passthrough variables with non-sensitive values.
        """
        sanitized: dict[str, str] = {}
        source_env = env if env is not None else os.environ

        for k, v in source_env.items():
            k_upper = k.upper()
            # Must be in safe passthrough list
            if k_upper not in SAFE_ENV_PASSTHROUGH:
                continue
            # Must not contain secret indicator substrings
            if any(sub in k_upper for sub in SENSITIVE_ENV_SUBSTRINGS):
                continue
            sanitized[k] = v

        return sanitized

    def sanitize_action(self, action: ComputerAction) -> ComputerAction:
        """
        Return a copy of the action with stripped environment variables and purged secrets.
        """
        cleaned_payload = dict(action.payload)
        if "env" in cleaned_payload and isinstance(cleaned_payload["env"], dict):
            cleaned_payload["env"] = self.sanitize_environment(cleaned_payload["env"])
        if "environment" in cleaned_payload and isinstance(cleaned_payload["environment"], dict):
            cleaned_payload["environment"] = self.sanitize_environment(cleaned_payload["environment"])

        return ComputerAction(
            action_type=action.action_type,
            target=action.target,
            payload=cleaned_payload,
            bot_id=action.bot_id,
            session_id=action.session_id,
        )

    def _extract_command_strings(self, action: ComputerAction) -> list[str]:
        """Extract all candidate command text from an action's target and payload."""
        candidates = [action.target]
        for key in ("command", "cmd", "script", "args", "executable"):
            val = action.payload.get(key)
            if isinstance(val, str) and val.strip():
                candidates.append(val)
            elif isinstance(val, (list, tuple)):
                candidates.append(" ".join(str(item) for item in val))
        return candidates

    def _evaluate_shell_hard_deny(self, action: ComputerAction) -> tuple[bool, str]:
        """
        Inspect shell commands against hard-denied destruction and privilege-escalation patterns.
        Note: Pattern matching alone cannot catch all obfuscation (base64-encoded payloads,
        unicode homoglyphs, variable-expansion tricks) — this is defense-in-depth on top of
        the allowlist, not a substitute for it.
        """
        command_texts = self._extract_command_strings(action)
        for cmd_text in command_texts:
            for pattern, description in SHELL_HARD_DENY_PATTERNS:
                if pattern.search(cmd_text):
                    return (
                        False,
                        f"Hard-Deny (Shell): Prohibited pattern detected ({description}) in '{cmd_text}'.",
                    )
        return (True, "")

    def _evaluate_network_hard_deny(self, action: ComputerAction) -> tuple[bool, str]:
        """
        Inspect outbound targets against SSRF, metadata IPs, loopback, private subnets,
        and DNS rebinding attacks.
        """
        raw_target = action.target.strip()

        # 1. Literal check for cloud metadata IP 169.254.169.254 in any part of target
        if "169.254.169.254" in raw_target:
            return (
                False,
                "Hard-Deny (Network): Cloud metadata IP 169.254.169.254 is strictly prohibited.",
            )

        # 2. Extract hostname and port
        if "://" in raw_target:
            parsed = urllib.parse.urlsplit(raw_target)
        else:
            parsed = urllib.parse.urlsplit("//" + raw_target)

        # Non-network schemes (file://, about:, data:) do not route through remote network IP stacks
        if parsed.scheme in ("file", "about", "data"):
            return (True, "")

        hostname = parsed.hostname
        if not hostname:
            token = raw_target.split("/")[0].split(":")[0].strip("[]")
            hostname = token or None

        if not hostname:
            return (False, "Hard-Deny (Network): Unable to extract valid hostname or IP from target.")

        hostname_lower = hostname.lower()

        # 3. Check loopback hostname
        if hostname_lower == "localhost" or hostname_lower.endswith(".localhost"):
            return (
                False,
                f"Hard-Deny (Network): Loopback hostname '{hostname}' is strictly prohibited.",
            )

        # 4. Check known cloud metadata hostnames
        if hostname_lower in METADATA_HOSTNAMES or hostname_lower.endswith(".internal"):
            return (
                False,
                f"Hard-Deny (Network): Metadata hostname '{hostname}' is strictly prohibited.",
            )

        # 5. DNS Resolution before evaluation (DNS Rebinding defense)
        # Attempt resolution via injected or default resolver
        try:
            # If hostname is already a valid IP literal, parse directly
            try:
                ipaddress.ip_address(hostname_lower)
                resolved_ips = [hostname_lower]
            except ValueError:
                resolved_ips = self.dns_resolver(hostname_lower)
        except Exception as exc:
            return (
                False,
                f"Hard-Deny (Network): DNS resolution failed for hostname '{hostname}': {exc}",
            )

        if not resolved_ips:
            return (
                False,
                f"Hard-Deny (Network): No IP addresses resolved for hostname '{hostname}'.",
            )

        # 6. Validate every resolved IP against prohibited networks
        for ip_str in resolved_ips:
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                return (
                    False,
                    f"Hard-Deny (Network): Invalid IP address resolved: '{ip_str}'",
                )

            # Check IPv4-mapped IPv6 addresses (e.g. ::ffff:169.254.169.254)
            if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
                check_ip: ipaddress.IPv4Address | ipaddress.IPv6Address = ip_obj.ipv4_mapped
            else:
                check_ip = ip_obj

            # Check loopback, private, link-local, reserved
            if (
                check_ip.is_loopback
                or check_ip.is_private
                or check_ip.is_link_local
                or check_ip.is_reserved
                or check_ip.is_unspecified
                or check_ip.is_multicast
            ):
                return (
                    False,
                    f"Hard-Deny (Network): Target '{action.target}' resolved to prohibited IP '{ip_str}'.",
                )

            # Check explicit IPv4 networks
            if isinstance(check_ip, ipaddress.IPv4Address):
                for network in PROHIBITED_IPV4_NETWORKS:
                    if check_ip in network:
                        return (
                            False,
                            f"Hard-Deny (Network): Target '{action.target}' resolved to prohibited IP '{ip_str}' in subnet {network}.",
                        )

            # Check explicit IPv6 networks
            if isinstance(check_ip, ipaddress.IPv6Address):
                for network in PROHIBITED_IPV6_NETWORKS:
                    if check_ip in network:
                        return (
                            False,
                            f"Hard-Deny (Network): Target '{action.target}' resolved to prohibited IPv6 '{ip_str}' in subnet {network}.",
                        )

        return (True, "")

    def evaluate(self, action: ComputerAction) -> tuple[bool, str]:
        """
        Evaluate a ComputerAction against the policy rules and secondary hard-deny layers.

        Returns:
            Tuple[bool, str]: (is_permitted, reason)
        """
        # Step 1: Evaluate explicit user/operator PolicyRules
        applicable_rules = [r for r in self.rules if r.action_type == action.action_type]

        # Check explicit custom DENY rules first
        for rule in applicable_rules:
            if rule.effect == "DENY":
                if re.search(rule.pattern, action.target, re.IGNORECASE):
                    return (
                        False,
                        f"Policy-Deny: Action matched explicit DENY rule '{rule.name}' with pattern '{rule.pattern}'.",
                    )
                # For shell commands, also check payload commands
                if action.action_type == ActionType.SHELL_EXEC:
                    for cmd in self._extract_command_strings(action):
                        if re.search(rule.pattern, cmd, re.IGNORECASE):
                            return (
                                False,
                                f"Policy-Deny: Action payload matched explicit DENY rule '{rule.name}' with pattern '{rule.pattern}'.",
                            )

        # Step 2: Evaluate Secondary Hard-Deny Layers
        # (An allow match never overrides a deny match or security layer)
        if action.action_type == ActionType.SHELL_EXEC:
            shell_ok, shell_reason = self._evaluate_shell_hard_deny(action)
            if not shell_ok:
                return (False, shell_reason)

        if action.action_type == ActionType.BROWSER_NAVIGATE:
            net_ok, net_reason = self._evaluate_network_hard_deny(action)
            if not net_ok:
                return (False, net_reason)

        # Also check network safety if target is a URL or IP regardless of action type
        if "://" in action.target or "169.254.169.254" in action.target:
            net_ok, net_reason = self._evaluate_network_hard_deny(action)
            if not net_ok:
                return (False, net_reason)

        # Step 3: Default-Deny, Allowlist-First verification
        # An action is refused unless an explicit ALLOW rule matches
        matched_allow_rule: PolicyRule | None = None
        for rule in applicable_rules:
            if rule.effect == "ALLOW":
                if re.search(rule.pattern, action.target, re.IGNORECASE):
                    matched_allow_rule = rule
                    break
                if action.action_type == ActionType.SHELL_EXEC:
                    for cmd in self._extract_command_strings(action):
                        if re.search(rule.pattern, cmd, re.IGNORECASE):
                            matched_allow_rule = rule
                            break
                    if matched_allow_rule:
                        break

        if not matched_allow_rule:
            return (
                False,
                f"Default-Deny: Action of type '{action.action_type.value}' on target '{action.target}' is not permitted by any explicit ALLOW rule.",
            )

        return (
            True,
            f"Permitted: Matched explicit ALLOW rule '{matched_allow_rule.name}' and passed all hard-deny security layers.",
        )
