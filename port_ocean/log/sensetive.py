import re
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record

# https://github.com/h33tlit/secret-regex-list
secret_patterns = {
    "Password in URL": r"[a-zA-Z]{3,10}:\/\/[^\/\\s:@]{3,20}:[^\/\\s:@]{3,20}@.{1,100}[\"'\\s]",
    "Generic API Key": r"[a|A][p|P][i|I][_]?[k|K][e|E][y|Y].*['|\"][0-9a-zA-Z]{32,45}['|\"]",
    "Generic Secret": r"[s|S][e|E][c|C][r|R][e|E][t|T].*['|\"][0-9a-zA-Z]{32,45}['|\"]",
    "Google API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Firebase URL": r".*firebaseio\.com",
    "RSA private key": r"-----BEGIN RSA PRIVATE KEY-----",
    "SSH (DSA) private key": r"-----BEGIN DSA PRIVATE KEY-----",
    "SSH (EC) private key": r"-----BEGIN EC PRIVATE KEY-----",
    "PGP private key block": r"-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "Amazon AWS Access Key ID": r"AKIA[0-9A-Z]{16}",
    "Amazon MWS Auth Token": r"amzn\\.mws\\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "AWS API Key": r"AKIA[0-9A-Z]{16}",
    "GitHub": r"[g|G][i|I][t|T][h|H][u|U][b|B].*['|\"][0-9a-zA-Z]{35,40}['|\"]",
    "Google Cloud Platform API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Google Cloud Platform OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\\.apps\\.googleusercontent\\.com",
    "Google (GCP) Service-account": r'"type": "service_account"',
    "Google OAuth Access Token": r"ya29\\.[0-9A-Za-z\\-_]+",
    "Connection String": r"[a-zA-Z]+:\/\/[^/\s]+:[^/\s]+@[^/\s]+\/[^/\s]+",
}


class SensitiveLogFilter:
    compiled_patterns = [re.compile(pattern) for pattern in secret_patterns.values()]

    def hide_sensitive_strings(self, *tokens: str) -> None:
        self.compiled_patterns.extend(
            [re.compile(re.escape(token.strip())) for token in tokens if token.strip()]
        )

    def create_filter(self, full_hide: bool = False) -> Callable[["Record"], bool]:
        def _filter(record: "Record") -> bool:
            for pattern in self.compiled_patterns:
                replace: Callable[[re.Match[str]], str] | str = (
                    "[REDACTED]"
                    if full_hide
                    else lambda match: match.group()[:6] + "[REDACTED]"
                )
                record["message"] = pattern.sub(replace, record["message"])

            return True

        return _filter


sensitive_log_filter = SensitiveLogFilter()
