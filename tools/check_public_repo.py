#!/usr/bin/env python3
"""
Pre-publication safety check: make sure no personal data or secrets are
in what would be published.

    python3 tools/check_public_repo.py               # tracked files (working tree)
    python3 tools/check_public_repo.py --history     # + every file in every commit
    python3 tools/check_public_repo.py --env .env    # + make sure the real values in
                                                     #   this .env appear nowhere
                                                     #   (values are never printed)

Exits 1 if anything is found. Prints file names and the kind of problem,
never the matching content.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 3 * 1024 * 1024

FORBIDDEN_PATHS = [
    (re.compile(r"(^|/)\.env($|\.)(?!example$)"), "environment file (secrets)"),
    (re.compile(r"\.(db|sqlite|sqlite3|db-journal|db-wal)$", re.I), "database file"),
    (re.compile(r"(^|/)(data|backups|exports)/"), "personal data folder"),
    (re.compile(r"\.log$", re.I), "log file"),
    (re.compile(r"\.(xlsx|xls|csv)$", re.I), "spreadsheet (may contain personal data)"),
    (re.compile(r"kaisenos-export-", re.I), "data export"),
    (re.compile(r"(^|/)settings\.local\.json$"), "machine-specific settings"),
    (re.compile(r"\.pdf$", re.I), "PDF (check you have the right to publish it)"),
]

SECRET_PATTERNS = [
    (re.compile(rb"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"), "private key"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,}"), "GitHub token"),
    (re.compile(rb"sk-[A-Za-z0-9]{32,}"), "API secret key"),
    (re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"), "JWT / access token"),
    (re.compile(rb"GARMIN_PERSONAL_API_KEY\s*=\s*['\"]?(?!your-key-here|\s|$|['\"]|\.\.\.)[A-Za-z0-9_\-]{12,}"), "Garmin API key value"),
]

PERSONAL_PATTERNS = [
    (re.compile(rb"/Users/(?!runner\b|me\b|you\b|alice\b|<)[A-Za-z0-9._-]+/"), "personal macOS path"),
    (re.compile(rb"/home/(?!runner\b|user\b|<)[A-Za-z0-9._-]+/"), "personal Linux path"),
    (re.compile(rb"C:\\\\Users\\\\(?!<)[A-Za-z0-9._-]+"), "personal Windows path"),
    (re.compile(rb"[A-Za-z0-9._%+-]+@(?!example\.|anthropic\.com|users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "email address"),
]

ALLOW_FILES = {"tools/check_public_repo.py"}  # contains the patterns themselves
SQLITE_MAGIC = b"SQLite format 3\x00"


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def check_blob(path: str, data: bytes, secrets: list[bytes]) -> list[str]:
    problems = []
    for pattern, why in FORBIDDEN_PATHS:
        if pattern.search(path):
            problems.append(why)
    if data.startswith(SQLITE_MAGIC):
        problems.append("SQLite database content")
    if len(data) > MAX_BYTES:
        problems.append(f"large file ({len(data) // 1024} KB)")
    if path not in ALLOW_FILES:
        for pattern, why in SECRET_PATTERNS + PERSONAL_PATTERNS:
            if pattern.search(data):
                problems.append(why)
    for value in secrets:
        if value and value in data:
            problems.append("contains a value from your .env")
    return problems


def env_values(env_file: Path) -> list[bytes]:
    values = []
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            value = line.split("=", 1)[1].strip().strip("'\"")
            if len(value) >= 8:
                values.append(value.encode())
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true", help="also scan every commit")
    parser.add_argument("--env", type=Path, help="a .env whose real values must not appear anywhere")
    args = parser.parse_args()
    secrets = env_values(args.env) if args.env else []

    findings: dict[str, set[str]] = {}

    for path in git("ls-files", "-z").decode().split("\0"):
        if path and (ROOT / path).is_file():
            for why in check_blob(path, (ROOT / path).read_bytes(), secrets):
                findings.setdefault(path, set()).add(why)

    commits = 0
    if args.history:
        for commit in git("rev-list", "--all").decode().split():
            commits += 1
            for entry in git("ls-tree", "-r", "-z", commit).decode().split("\0"):
                if not entry:
                    continue
                meta, path = entry.split("\t", 1)
                sha = meta.split()[2]
                for why in check_blob(path, git("cat-file", "-p", sha), secrets):
                    findings.setdefault(f"{path} (history {commit[:7]})", set()).add(why)
        for line in git("log", "--all", "--format=%an <%ae>").decode().splitlines():
            if "noreply" not in line:
                findings.setdefault("commit author", set()).add(f"author email is public: {line.split('<')[-1].rstrip('>')}")

    scope = f"tracked files{f' + {commits} commit(s)' if args.history else ''}{' + .env values' if secrets else ''}"
    if not findings:
        print(f"OK: no personal data or secrets found ({scope}).")
        return 0
    print(f"FOUND {len(findings)} problem(s) in {scope}:")
    for where, why in sorted(findings.items()):
        print(f"  {where}: {', '.join(sorted(why))}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
