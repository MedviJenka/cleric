from pathlib import Path

from src.automation.runner import FailureArtifact

_MAX_DOM_CHARS = 20_000
_REDACTED = "[REDACTED]"
_SECRET_MARKERS = ("password", "token", "secret", "api_key", "apikey", "authorization")


def format_failure_packet(artifact: FailureArtifact) -> str:
    """Create the evidence-only prompt payload for the analyst crew."""
    dom_snapshot = _read_text(Path(artifact.dom_snapshot_path))
    return "\n".join(
        [
            "Automation failure packet",
            f"workflow_id={artifact.workflow_id or ''}",
            f"run_id={artifact.run_id}",
            f"failed_step_id={artifact.failed_step_id}",
            f"failed_step_intent={artifact.failed_step_intent}",
            f"current_url={artifact.current_url or ''}",
            f"expected_outcome={artifact.expected_outcome}",
            f"risk={artifact.risk}",
            f"error={artifact.error}",
            f"screenshot_path={artifact.screenshot_path}",
            "dom_snapshot:",
            _redact(dom_snapshot[:_MAX_DOM_CHARS]),
        ]
    )


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _redact(value: str) -> str:
    redacted_lines: list[str] = []
    for line in value.splitlines():
        if any(marker in line.lower() for marker in _SECRET_MARKERS):
            redacted_lines.append(_REDACTED)
        else:
            redacted_lines.append(line)
    return "\n".join(redacted_lines)
