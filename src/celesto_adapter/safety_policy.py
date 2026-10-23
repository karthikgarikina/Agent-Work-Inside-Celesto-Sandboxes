import re
from urllib.parse import urlparse
from typing import List, Optional, Set


class CommandBlockedError(Exception):
    """Raised when a command is blocked by the safety policy before reaching the guest."""
    def __init__(self, message: str, command: str, sandbox_name: str, rule: str):
        super().__init__(message)
        self.message = message
        self.command = command
        self.sandbox_name = sandbox_name
        self.rule = rule


class SafetyPolicy:
    """
    Enforces multi-layer safety policies:
    1. Enforceable network destination restrictions (allowlist for research).
    2. Canary secret leak & prompt-injection exfiltration prevention.
    3. Destructive system command blocking.
    4. Host file and credential probing blocking.
    Fails closed on ambiguous or malicious inputs.
    """

    # Permitted domains for sandboxed research
    ALLOWED_DOMAINS: Set[str] = {
        "en.wikipedia.org",
        "wikipedia.org",
        "arxiv.org",
        "api.crossref.org",
        "semanticscholar.org",
        "github.com",
        "raw.githubusercontent.com",
        "python.org",
        "pypi.org",
        "docs.celesto.ai",
        "celesto.ai",
        "huggingface.co",
    }

    # Destructive commands that must never execute
    DESTRUCTIVE_PATTERNS = [
        r"rm\s+-rf\s+(/\*?|/etc|/boot|/usr|/bin|/sbin|~/\*)",
        r"mkfs(\.[a-z0-9]+)?",
        r":\(\)\s*\{\s*:\|:&\s*\}\s*;",  # Fork bomb
        r"dd\s+if=/dev/(zero|urandom)\s+of=/dev/",
        r">\s*/dev/sd[a-z]",
        r"chmod\s+-R\s+777\s+/",
    ]

    # Host secret and system file probing patterns
    SECRET_PROBING_PATTERNS = [
        r"cat\s+/etc/shadow",
        r"cat\s+.*\.env(\.local)?\b",
        r"/var/run/docker\.sock",
        r"id_rsa",
        r"CELESTO_API_KEY",
        r"LLM_API_KEY",
    ]

    def __init__(self, canary_token: str = "CANARY_SECRET_LEAK_TOKEN_98765"):
        self.canary_token = canary_token
        self._destructive_regex = [re.compile(p, re.IGNORECASE) for p in self.DESTRUCTIVE_PATTERNS]
        self._secret_regex = [re.compile(p, re.IGNORECASE) for p in self.SECRET_PROBING_PATTERNS]
        self._url_pattern = re.compile(r"https?://[^\s\"'>]+", re.IGNORECASE)

    def extract_urls(self, command: str) -> List[str]:
        return self._url_pattern.findall(command)

    def check_network_destination(self, url: str) -> bool:
        """
        Verify that destination URL belongs strictly to allowed research domains.
        Blocks webhooks, external attackers, internal private subnets, loopbacks.
        """
        try:
            parsed = urlparse(url)
            host = parsed.netloc.split(":")[0].lower()
            if not host:
                return False

            # Disallow localhost / internal private IPs
            if host in ("localhost", "127.0.0.1", "0.0.0.0") or host.startswith("192.168.") or host.startswith("10.") or host.startswith("172."):
                return False

            # Check domain allowlist
            for allowed in self.ALLOWED_DOMAINS:
                if host == allowed or host.endswith(f".{allowed}"):
                    return True
            return False
        except Exception:
            return False

    def evaluate(self, command: str, sandbox_name: str) -> None:
        """
        Evaluate the command against safety rules.
        Raises CommandBlockedError if the command is unsafe.
        Fails closed.
        """
        cmd = command.strip()

        # 1. Canary secret exfiltration prevention (deep token containment)
        if self.canary_token and self.canary_token in cmd:
            raise CommandBlockedError(
                message=f"Canary secret exfiltration attempt blocked: canary token detected in payload: {cmd[:60]}...",
                command=cmd,
                sandbox_name=sandbox_name,
                rule="canary_exfiltration_blocked",
            )

        # 2. Destructive command check
        for regex in self._destructive_regex:
            if regex.search(cmd):
                raise CommandBlockedError(
                    message=f"Destructive command blocked by safety policy: {cmd[:60]}...",
                    command=cmd,
                    sandbox_name=sandbox_name,
                    rule="destructive_command_blocked",
                )

        # 3. Host secret probing check
        for regex in self._secret_regex:
            if regex.search(cmd):
                raise CommandBlockedError(
                    message=f"Host/system secret probing blocked by safety policy: {cmd[:60]}...",
                    command=cmd,
                    sandbox_name=sandbox_name,
                    rule="secret_probing_blocked",
                )

        # 4. Enforceable network destination restrictions
        # Only inspect URLs that are destinations of outbound network activity.
        # Ignore file-writing heredoc and echo bodies so reference links in written reports do not false-positive.
        cmd_for_urls = cmd
        if "<< 'EOF'" in cmd or "<< EOF" in cmd or "<< 'HEREDOC'" in cmd:
            cmd_for_urls = re.sub(r"<<\s*['\"]?EOF['\"]?[\s\S]*?(\nEOF|\Z)", "", cmd)
            cmd_for_urls = re.sub(r"<<\s*['\"]?HEREDOC['\"]?[\s\S]*?(\nHEREDOC|\Z)", "", cmd_for_urls)

        urls = self.extract_urls(cmd_for_urls)
        for url in urls:
            if not self.check_network_destination(url):
                raise CommandBlockedError(
                    message=f"Unauthorized outbound network destination blocked: '{url}'. Not in approved research allowlist.",
                    command=cmd,
                    sandbox_name=sandbox_name,
                    rule="network_destination_blocked",
                )


safety_policy = SafetyPolicy()
