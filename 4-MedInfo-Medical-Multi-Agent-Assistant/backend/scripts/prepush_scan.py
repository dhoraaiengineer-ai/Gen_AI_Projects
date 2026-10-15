"""Pre-push scan: secrets and anything that looks like real patient data, across the working tree
(and git history when this is a git repository). Exits non-zero on findings that are not allow-listed.

Usage: python scripts/prepush_scan.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repository root
SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv-eval",
    ".venv-ui",
    ".venv-ragas",
    ".terraform",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "mlruns",
    "node_modules",
    "runs",
}
SKIP_FILES = {".env", "mlflow.db"}  # gitignored local files: secrets and the MLflow store
BINARY = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".pptx", ".xlsx", ".onnx", ".pyc", ".hcl"}

SECRETS = {
    "openai/sk key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "euri key": r"\beuri-[0-9a-f]{32,}",
    "groq key": r"\bgsk_[A-Za-z0-9]{30,}",
    "tavily key": r"\btvly-(?:dev-)?[A-Za-z0-9]{20,}",
    "supabase secret": r"\bsb_secret_[A-Za-z0-9_-]{20,}",
    "gemini key": r"\bAQ\.[A-Za-z0-9_-]{30,}|\bAIza[0-9A-Za-z_-]{35}",
    "aws key": r"\bAKIA[0-9A-Z]{16}\b",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "db url with password": r"postgres(?:ql)?(?:\+psycopg)?://[^:\s/]+:(?!YOUR-PASSWORD|<password>|p@|ci-only-password)[^@\s]{6,}@",
}
# Patient-like data. Synthetic values used on purpose (tests, probes, the synthetic dataset) are allow-listed.
PHI = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "mrn": r"\b(?:MRN|UHID)[\s:#-]*[A-Z0-9-]{4,}",
    "dob": r"\b(?:DOB|date of birth)[\s:.-]*\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}",
    "phone (10-digit mobile)": r"\b[6-9]\d{9}\b",
}
ALLOWED = [
    r"@example\.(?:test|com)",
    r"noreply@anthropic\.com",
    r"\b9999999999\b",  # JWT expiry timestamp in tests, not a phone number
    r"sk-ABCDEFGHIJKLMNOPQRSTUVWX123",  # deliberately fake key used by the secret-redaction test
    r"SYN-\d+",
    r"MRN: \[ID\]",
    r"\[DOB\]",
    r"9876543210",
    r"9123456780",
    r"12/05/1990",
    r"01/02/1980",
    r"MRN[\s:#-]*SYN",
    r"UHID\|",
    r"MRN\|",
    r"\(\?:MRN",
]


def files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.name in SKIP_FILES or p.suffix.lower() in BINARY:
            continue
        out.append(p)
    return out


def allowed(text: str) -> bool:
    return any(re.search(a, text) for a in ALLOWED)


def scan_text(label: str, text: str) -> list[str]:
    findings = []
    for name, pat in SECRETS.items():
        for m in re.finditer(pat, text):
            if not allowed(m.group(0)):
                findings.append(f"SECRET {name}: {label}: {m.group(0)[:12]}...")
    for name, pat in PHI.items():
        for m in re.finditer(pat, text):
            ctx = text[max(0, m.start() - 40) : m.end() + 40]
            if not allowed(m.group(0)) and not allowed(ctx):
                findings.append(f"PHI? {name}: {label}: {m.group(0)[:40]}")
    return findings


def main() -> int:
    findings: list[str] = []
    checked = 0
    for p in files():
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        checked += 1
        findings += scan_text(str(p.relative_to(ROOT)), text)
    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        log = subprocess.run(  # noqa: S603 - fixed argv, resolved git
            [git, "log", "-p", "--all"], cwd=ROOT, capture_output=True, text=True, check=False
        )
        findings += scan_text("git history", log.stdout)
        tracked = subprocess.run(  # noqa: S603 - fixed argv, resolved git
            [git, "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout
        if ".env" in tracked.splitlines():
            findings.append("SECRET .env is tracked by git")
    print(
        f"scanned {checked} text files"
        + (" + git history" if (ROOT / ".git").exists() else " (no git repository yet)")
    )
    for f in findings:
        print(f)
    print("clean" if not findings else f"{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
