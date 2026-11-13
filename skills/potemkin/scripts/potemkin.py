#!/usr/bin/env python3
"""Potemkin: Deterministic fake-readiness, stub, dead-wire & AI reward-hacking auditor.

Zero external dependencies (Python 3.10+ stdlib only). Works standalone inside an Agent
Skill (`skills/potemkin/scripts/potemkin.py`), via CLI (`potemkin`), or in GitHub Actions.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VERSION = "1.0.1"
MAX_FILE_BYTES = 512 * 1024
SKIP_FILE_SUFFIXES = (
    ".min.js",
    ".min.mjs",
    ".min.cjs",
    ".bundle.js",
    ".d.ts",
    ".d.mts",
    ".d.cts",
)

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SEVERITY_PENALTY = {"critical": 18, "high": 9, "medium": 4, "low": 1}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".astro",
    "dist",
    "build",
    "out",
    "coverage",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".cache",
    ".tox",
    ".eggs",
    "target",
    "vendor",
    ".audit-venv",
    "storybook-static",
}

TEST_OR_FIXTURE_SEGMENTS = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
    "__mocks__",
    "mocks",
    "mock",
    "fixture",
    "fixtures",
    "stories",
    "storybook",
    "e2e",
    "playwright",
    "cypress",
    "benchmark",
    "benchmarks",
    "eval",
    "evals",
    "example",
    "examples",
    "sample",
    "samples",
    "seed",
    "seeds",
    "migrations",
    "docs",
    "doc",
}

TEST_FILE_RE = re.compile(
    r"(^test_.*\.py$|_test\.py$|^conftest\.py$|"
    r"\.(test|spec|stories|fixture|mock)\.[^.]+$|"
    r"^seed\.[^.]+$)",
    re.IGNORECASE,
)

JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
UI_EXTENSIONS = {".jsx", ".tsx", ".vue", ".svelte"}
PY_EXTENSIONS = {".py"}
CODE_EXTENSIONS = JS_EXTENSIONS | PY_EXTENSIONS | {".vue", ".svelte"}

STD_ENV_VARS = {
    "NODE_ENV",
    "PORT",
    "HOST",
    "HOSTNAME",
    "HOME",
    "PATH",
    "PWD",
    "USER",
    "SHELL",
    "TERM",
    "TZ",
    "LANG",
    "CI",
    "DEBUG",
    "LOG_LEVEL",
    "ENVIRONMENT",
    "ENV",
    "APP_ENV",
    "VERCEL",
    "VERCEL_ENV",
    "VERCEL_URL",
    "VERCEL_REGION",
    "NEXT_RUNTIME",
    "NEXT_PHASE",
    "GITHUB_ACTIONS",
    "GITHUB_WORKSPACE",
    "GITHUB_SHA",
    "GITHUB_REF",
    "GITHUB_REPOSITORY",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "UV_CACHE_DIR",
    "NPM_CONFIG_CACHE",
    "VITEST",
    "JEST_WORKER_ID",
    "TEST",
    "PYTEST_CURRENT_TEST",
}

PUBLIC_ENV_PREFIXES = (
    "NEXT_PUBLIC_",
    "VITE_",
    "EXPO_PUBLIC_",
    "NUXT_PUBLIC_",
    "REACT_APP_",
    "PUBLIC_",
)

SENSITIVE_ENV_TOKEN_RE = re.compile(
    r"(SECRET|PRIVATE|PASSWORD|PASSWD|SERVICE_ROLE|DATABASE_URL|REDIS_URL|"
    r"ENCRYPTION_KEY|SIGNING_KEY|ADMIN_KEY|MASTER_KEY|JWT_KEY|AUTH_SECRET|"
    r"WEBHOOK_SECRET|SESSION_SECRET|API_SECRET|CLIENT_SECRET)",
    re.IGNORECASE,
)

SAFE_PUBLIC_KEY_RE = re.compile(
    r"(PUBLISHABLE|PUBLIC_KEY|ANON_KEY|SITE_KEY|MEASUREMENT_ID|POSTHOG_KEY|"
    r"MAPBOX_TOKEN|API_URL|APP_URL|SITE_URL|WS_URL|LIVEKIT_URL)",
    re.IGNORECASE,
)

HEALTH_OR_INFRA_ROUTE_RE = re.compile(
    r"(^|/)(healthz?|readyz?|livez?|ping|metrics|docs|redoc|openapi\.json|"
    r"favicon\.ico|robots\.txt|sitemap\.xml|api/auth(/.*)?|webhooks?(/.*)?|stripe/webhook)$",
    re.IGNORECASE,
)

MOCK_IDENT_RE = re.compile(
    r"\b(?:(?:MOCK|FAKE|DEMO|SAMPLE|DUMMY|PLACEHOLDER)_[A-Z0-9_]+|"
    r"(?:mock|fake|demo|sample|dummy|placeholder)_[a-z0-9_]+|"
    r"(?:mock|fake|demo|sample|dummy)(?:Users|Data|Items|Rows|List|Orders|Patients|Products|Posts|Response|Results))\b"
)

PLACEHOLDER_TEXT_RE = re.compile(
    r"(['\"])(test@example\.com|user@example\.com|admin@example\.com|john\.doe@|"
    r"coming\s+soon!?|not\s+implemented(?:\s+yet)?|todo:\s*implement|"
    r"placeholder\s+data)\1",
    re.IGNORECASE,
)

IGNORE_DIRECTIVE_RE = re.compile(
    r"(?://|#|\{\s*/\*)\s*potemkin-ignore(?:\s*:\s*([A-Z0-9_,\s-]+?))?(?:\*/\s*\}|--|$)",
    re.IGNORECASE,
)

RULE_META: dict[str, dict[str, str]] = {
    "POT001": {
        "pillar": "HOLLOW_UI",
        "severity": "high",
        "title": "Hollow UI event handler",
        "help": "Wire the handler to real state/API/action logic or remove the control if unimplemented.",
    },
    "POT002": {
        "pillar": "HOLLOW_UI",
        "severity": "medium",
        "title": "Dead placeholder link (`#`)",
        "help": "Point href/to at a real route, valid `#section-id` anchor, or interactive button.",
    },
    "POT003": {
        "pillar": "HOLLOW_UI",
        "severity": "high",
        "title": "Theater submit handler (simulated timer/toast without persistence)",
        "help": "Connect form submission to a real API request, Server Action, or state mutation.",
    },
    "POT004": {
        "pillar": "FAKE_FALLBACK",
        "severity": "critical",
        "title": "Deceptive error fallback returning mock/fake success",
        "help": "Log and propagate or return a real error response instead of faking success/mock data.",
    },
    "POT005": {
        "pillar": "FAKE_FALLBACK",
        "severity": "high",
        "title": "Silent catch/except swallowing errors",
        "help": "Handle, log, or rethrow exceptions explicitly so runtime failures are never hidden.",
    },
    "POT006": {
        "pillar": "FAKE_FALLBACK",
        "severity": "critical",
        "title": "Webhook handler lacks cryptographic signature verification",
        "help": "Verify provider HMAC/webhook signature headers before trusting payloads or returning 200 OK.",
    },
    "POT007": {
        "pillar": "MOCK_IN_PROD",
        "severity": "high",
        "title": "Mock fixture, placeholder literal, or NotImplemented stub in runtime code",
        "help": "Replace stub/fixture data in runtime modules with real data loading or raise only in ABCs.",
    },
    "POT008": {
        "pillar": "WIRE_GAP",
        "severity": "high",
        "title": "Frontend request calls missing backend route or mismatched HTTP method",
        "help": "Align the frontend endpoint/method with a real backend route handler.",
    },
    "POT009": {
        "pillar": "WIRE_GAP",
        "severity": "medium",
        "title": "Orphan backend route with zero repo callers or test references",
        "help": "Wire the endpoint to UI/tests or remove dead scaffolded routes.",
    },
    "POT010": {
        "pillar": "WIRE_GAP",
        "severity": "medium",
        "title": "Hardcoded localhost URL in runtime code without env override",
        "help": "Read host/base URL from an environment variable with explicit prod configuration.",
    },
    "POT011": {
        "pillar": "ENV_TRUTH",
        "severity": "critical",
        "title": "Insecure hardcoded fallback for security-sensitive secret",
        "help": "Fail fast at startup if required secret env vars are unset in production.",
    },
    "POT012": {
        "pillar": "ENV_TRUTH",
        "severity": "critical",
        "title": "Sensitive secret variable exposed with client-bundle public prefix",
        "help": "Remove NEXT_PUBLIC_/VITE_/PUBLIC_ prefix and keep secrets strictly server-side.",
    },
    "POT013": {
        "pillar": "ENV_TRUTH",
        "severity": "medium",
        "title": "Required runtime env var missing from .env.example template",
        "help": "Document the variable in .env.example so fresh environments boot cleanly.",
    },
    "POT014": {
        "pillar": "DIFF_CHEAT",
        "severity": "critical",
        "title": "Agent reward hacking: skipped/disabled test added in git diff",
        "help": "Fix the underlying failure rather than adding .skip / xit / pytest.mark.skip.",
    },
    "POT015": {
        "pillar": "DIFF_CHEAT",
        "severity": "high",
        "title": "Type/lint/hook suppression introduced in git diff",
        "help": "Resolve type or lint violations cleanly instead of adding @ts-ignore / type: ignore / --no-verify.",
    },
    "POT016": {
        "pillar": "DIFF_CHEAT",
        "severity": "high",
        "title": "Hollowed test assertions in git diff",
        "help": "Restore real behavioral assertions rather than deleting checks or asserting trivially.",
    },
}


@dataclass
class Finding:
    rule_id: str
    pillar: str
    severity: str
    file: str
    line: int
    title: str
    message: str
    snippet: str = ""
    help: str = ""
    fingerprint: str = ""

    def compute_fingerprint(self) -> str:
        raw = f"{self.rule_id}|{self.file}|{self.snippet.strip()}"
        self.fingerprint = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return self.fingerprint


@dataclass
class Endpoint:
    method: str
    path: str
    normalized: str
    file: str
    line: int
    framework: str


@dataclass
class ClientCall:
    method: str
    path: str
    normalized: str
    file: str
    line: int


@dataclass
class ScanConfig:
    exclude_globs: list[str] = field(default_factory=list)
    ignore_rules: set[str] = field(default_factory=set)
    strict_env_drift: bool = True
    strict_orphan_routes: bool = True


def load_config(root: Path) -> ScanConfig:
    cfg = ScanConfig()
    ignore_file = root / ".potemkinignore"
    if ignore_file.is_file():
        for raw in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                cfg.exclude_globs.append(line.rstrip("/"))
    json_cfg = root / ".potemkin.json"
    if json_cfg.is_file():
        try:
            data = json.loads(json_cfg.read_text(encoding="utf-8"))
            cfg.exclude_globs.extend(str(p).rstrip("/") for p in data.get("exclude", []))
            cfg.ignore_rules.update(str(r).upper() for r in data.get("ignoreRules", []))
            if "envDrift" in data:
                cfg.strict_env_drift = bool(data["envDrift"])
            if "orphanRoutes" in data:
                cfg.strict_orphan_routes = bool(data["orphanRoutes"])
        except Exception:
            pass
    return cfg


def is_excluded(rel_path: str, cfg: ScanConfig) -> bool:
    parts = Path(rel_path).parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return True
    for pattern in cfg.exclude_globs:
        if fnmatch.fnmatch(rel_path, pattern) or rel_path == pattern or rel_path.startswith(pattern + "/"):
            return True
    return False


def is_test_or_fixture_path(rel_path: str) -> bool:
    p = Path(rel_path)
    if any(seg.lower() in TEST_OR_FIXTURE_SEGMENTS for seg in p.parts[:-1]):
        return True
    return bool(TEST_FILE_RE.search(p.name))


def mask_js_comments(source: str) -> str:
    """Replace JS/TS/JSX line and block comments with spaces while preserving line numbers."""
    out: list[str] = []
    n = len(source)
    i = 0
    state = "code"
    quote = ""
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                out.append("  ")
                i += 2
                state = "line_comment"
                continue
            if ch == "/" and nxt == "*":
                out.append("  ")
                i += 2
                state = "block_comment"
                continue
            if ch in ("'", '"', "`"):
                quote = ch
                out.append(ch)
                i += 1
                state = "string"
                continue
            out.append(ch)
            i += 1
        elif state == "line_comment":
            if ch == "\n":
                out.append("\n")
                state = "code"
            else:
                out.append(" ")
            i += 1
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                out.append("  ")
                i += 2
                state = "code"
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        elif state == "string":
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if ch == quote:
                state = "code"
            i += 1
    return "".join(out)


def find_matching_brace(text: str, open_idx: int) -> int | None:
    """Given index of `{` in JS/TS source, find its matching `}` respecting strings/comments."""
    n = len(text)
    if open_idx >= n or text[open_idx] != "{":
        return None
    depth = 0
    i = open_idx
    state = "code"
    quote = ""
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch in ("'", '"', "`"):
                quote = ch
                state = "string"
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        elif state == "line_comment":
            if ch == "\n":
                state = "code"
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        elif state == "string":
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                state = "code"
        i += 1
    return None


def line_number_at(text: str, index: int) -> int:
    return text.count("\n", 0, max(0, index)) + 1


def line_text_at(lines: list[str], line_no: int) -> str:
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


def is_suppressed(lines: list[str], line_no: int, rule_id: str) -> bool:
    for check_ln in (line_no, line_no - 1):
        txt = line_text_at(lines, check_ln)
        if not txt:
            continue
        m = IGNORE_DIRECTIVE_RE.search(txt)
        if m:
            codes = m.group(1)
            if not codes:
                return True
            allowed = {c.strip().upper() for c in re.split(r"[,\s]+", codes) if c.strip()}
            if rule_id.upper() in allowed:
                return True
    return False


def add_finding(
    findings: list[Finding],
    cfg: ScanConfig,
    raw_lines: list[str],
    rule_id: str,
    rel_path: str,
    line_no: int,
    message: str,
    snippet: str = "",
) -> None:
    if rule_id in cfg.ignore_rules:
        return
    if is_suppressed(raw_lines, line_no, rule_id):
        return
    meta = RULE_META[rule_id]
    snip = (snippet or line_text_at(raw_lines, line_no))[:180]
    f = Finding(
        rule_id=rule_id,
        pillar=meta["pillar"],
        severity=meta["severity"],
        file=rel_path,
        line=line_no,
        title=meta["title"],
        message=message,
        snippet=snip,
        help=meta["help"],
    )
    f.compute_fingerprint()
    findings.append(f)


def normalize_route_path(raw_path: str) -> str:
    path = raw_path.split("?", 1)[0].split("#", 1)[0].strip()
    # Strip template expression prefix before leading slash (e.g. ${API_BASE}/api/users -> /api/users)
    path = re.sub(r"^\$\{[^}]+\}", "", path)
    if not path.startswith("/"):
        m = re.search(r"/(api|v\d+|[a-zA-Z0-9_-]+)(/.*)?$", path)
        if m and not path.startswith("http"):
            path = m.group(0)
        elif path.startswith(("http://", "https://")):
            m2 = re.match(r"https?://[^/]+(/.*)$", path)
            path = m2.group(1) if m2 else "/"
        else:
            path = "/" + path
    path = re.sub(r"/+", "/", path)
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"\[\.\.\.[^]]+\]|\[\[?\.\.\.[^]]+\]\]?", "{param}", path)
    path = re.sub(r"\[[^\]]+\]", "{param}", path)
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    path = re.sub(r":[a-zA-Z_][a-zA-Z0-9_]*", "{param}", path)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def has_concrete_segment(normalized_path: str) -> bool:
    segs = [s for s in normalized_path.split("/") if s]
    return any(s != "{param}" for s in segs)


def routes_match(client_norm: str, server_norm: str) -> bool:
    if client_norm == server_norm:
        return True
    c_parts = [s for s in client_norm.split("/") if s]
    s_parts = [s for s in server_norm.split("/") if s]
    if len(c_parts) == len(s_parts):
        return all(
            cp == sp or cp == "{param}" or sp == "{param}"
            for cp, sp in zip(c_parts, s_parts, strict=True)
        )
    return False


# ---------------------------------------------------------------------------
# JS / TS / JSX / TSX Scanner
# ---------------------------------------------------------------------------

EVENT_HANDLER_RE = re.compile(
    r"\b(onClick|onSubmit|onChange|onPress|onTap)\s*=\s*\{\s*(?:\(\s*(?:[a-zA-Z_$][\w$]*)?\s*\)|[a-zA-Z_$][\w$]*)\s*=>\s*",
    re.MULTILINE,
)

DEAD_HREF_RE = re.compile(r"""\b(?:href|to)\s*=\s*(?:["'](#?)["']|\{\s*["'](#?)["']\s*\})""")

SUBMIT_HANDLER_DEF_RE = re.compile(
    r"(?:const|let|async\s+function|function)\s+(handleSubmit|onSubmit)\b[^={]*?(?:=\s*(?:async\s*)?\([^)]*\)\s*=>|\([^)]*\))\s*\{"
)

CATCH_HEADER_RE = re.compile(r"\bcatch\s*(?:\(\s*([^)]*)\s*\))?\s*\{")

LOCALHOST_URL_RE = re.compile(r"""["'`]https?://(?:localhost|127\.0\.0\.1)(?::\d+)?[^"'`]*["'`]""")

JS_SECRET_FALLBACK_RE = re.compile(
    r"""process\.env\.([A-Z0-9_]*(?:SECRET|PRIVATE_KEY|SIGNING_KEY|ENCRYPTION_KEY|AUTH_KEY|WEBHOOK_SECRET|JWT_SECRET|SESSION_SECRET)[A-Z0-9_]*)\s*(?:\|\||\?\?)\s*(['"][^'"]{2,}['"])"""
)

JS_ENV_READ_RE = re.compile(r"""\bprocess\.env\.([A-Z][A-Z0-9_]{1,})\b|\bimport\.meta\.env\.([A-Z][A-Z0-9_]{1,})\b""")

NEXT_EXPORT_METHOD_RE = re.compile(
    r"export\s+(?:async\s+function|const|let)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b"
)

EXPRESS_ROUTE_RE = re.compile(
    r"\b([a-zA-Z_$][\w$]*)\.(get|post|put|patch|delete|all)\s*\(\s*(['\"`])(/[^'\"`]*)\3"
)

JS_FETCH_RE = re.compile(
    r"""\bfetch\s*\(\s*(`[^`]+`|'[^']+'|"[^"]+")(?:\s*,\s*\{([\s\S]{0,240}?)\})?"""
)

JS_AXIOS_RE = re.compile(
    r"""\b(?:axios|apiClient|httpClient)\.(get|post|put|patch|delete)\s*(?:<[^>]+>)?\s*\(\s*(`[^`]+`|'[^']+'|"[^"]+")"""
)


def extract_next_app_route(rel_path: str) -> str | None:
    norm = rel_path.replace("\\", "/")
    m = re.search(r"(?:^|/)(?:src/)?app/(.+)/route\.[^.]+$", norm)
    if not m:
        return None
    segs = [s for s in m.group(1).split("/") if s and not (s.startswith("(") and s.endswith(")"))]
    return "/" + "/".join(segs)


def extract_next_pages_api_route(rel_path: str) -> str | None:
    norm = rel_path.replace("\\", "/")
    m = re.search(r"(?:^|/)(?:src/)?pages/(api(?:/.*)?)\.[^.]+$", norm)
    if not m:
        return None
    sub = re.sub(r"/index$", "", m.group(1))
    return "/" + sub


def is_webhook_file_or_context(rel_path: str, masked_text: str) -> bool:
    low_path = rel_path.lower()
    if "webhook" in low_path and any(k in low_path for k in ("route", "api", "handler", "controller", "server")):
        return True
    return bool(
        re.search(r"['\"/].*webhooks?/.*['\"]", masked_text, re.IGNORECASE)
        and any(k in low_path for k in ("route", "api", "handler", "controller", "server"))
    )


def has_webhook_verification(text: str) -> bool:
    return bool(
        re.search(
            r"(constructEvent|createHmac|timingSafeEqual|verifyWebhook|verify_signature|"
            r"svix|stripe-signature|x-hub-signature|hmac\.new|compare_digest|Webhook\.verify)",
            text,
            re.IGNORECASE,
        )
    )


def scan_js_ts_file(
    rel_path: str,
    raw_text: str,
    cfg: ScanConfig,
    is_test: bool,
    findings: list[Finding],
    endpoints: list[Endpoint],
    client_calls: list[ClientCall],
    env_vars_used: dict[str, list[tuple[str, int, bool]]],
) -> None:
    raw_lines = raw_text.splitlines()
    masked = mask_js_comments(raw_text)

    # Env var usage + POT012 public prefix leak + POT011 secret fallback
    for m in JS_ENV_READ_RE.finditer(masked):
        var_name = m.group(1) or m.group(2)
        ln = line_number_at(masked, m.start())
        line_str = line_text_at(raw_lines, ln)
        guarded = bool(
            re.search(rf"\b{re.escape(var_name)}\b\s*(?:\|\||\?\?|\?|===|!==|&&)", line_str)
            or re.search(rf"(?:\bif\s*\(|!\s*process\.env\.|Boolean\s*\().*\b{re.escape(var_name)}\b", line_str)
        )
        if not is_test:
            env_vars_used[var_name].append((rel_path, ln, guarded))
            if (
                any(var_name.startswith(p) for p in PUBLIC_ENV_PREFIXES)
                and SENSITIVE_ENV_TOKEN_RE.search(var_name)
                and not SAFE_PUBLIC_KEY_RE.search(var_name)
            ):
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "POT012",
                    rel_path,
                    ln,
                    f"`{var_name}` uses a public client-bundle prefix for a sensitive secret name.",
                )

    if is_test:
        return

    for m in JS_SECRET_FALLBACK_RE.finditer(masked):
        ln = line_number_at(masked, m.start())
        add_finding(
            findings,
            cfg,
            raw_lines,
            "POT011",
            rel_path,
            ln,
            f"Hardcoded fallback `{m.group(2)}` supplied for secret `{m.group(1)}`.",
        )

    # POT001: Hollow event handlers
    for m in EVENT_HANDLER_RE.finditer(masked):
        ln = line_number_at(masked, m.start())
        rest = masked[m.end() :]
        if rest.startswith("{"):
            end_brace = find_matching_brace(masked, m.end())
            if end_brace is None:
                continue
            body = masked[m.end() + 1 : end_brace].strip()
        else:
            semi = rest.find("}")
            body = rest[:semi].strip() if semi != -1 else rest[:120].strip()

        clean_body = re.sub(r"[;\s]+", " ", body).strip()
        is_hollow = False
        reason = ""
        if clean_body in ("", "null", "undefined", "void 0"):
            is_hollow = True
            reason = f"Event `{m.group(1)}` has an empty/no-op handler body."
        elif re.fullmatch(r"(?:console\.(?:log|debug|info|warn)|alert)\s*\([^)]*\)", clean_body):
            is_hollow = True
            reason = f"Event `{m.group(1)}` only calls `{clean_body.split('(')[0]}(...)` without updating state or calling an API."
        if is_hollow:
            add_finding(findings, cfg, raw_lines, "POT001", rel_path, ln, reason)

    # POT002: Dead `#` href in JSX/UI files (skip SPA anchors with an active onClick/onPress handler)
    if Path(rel_path).suffix.lower() in UI_EXTENSIONS:
        for m in DEAD_HREF_RE.finditer(masked):
            val = m.group(1) if m.group(1) is not None else m.group(2)
            if val in ("#", ""):
                tag_start = masked.rfind("<", max(0, m.start() - 240), m.start())
                tag_end = masked.find(">", m.end(), min(len(masked), m.end() + 400))
                tag_slice = masked[tag_start : tag_end + 1] if tag_start != -1 and tag_end != -1 else line_text_at(raw_lines, line_number_at(masked, m.start()))
                if re.search(r"\b(?:onClick|onPress)\s*=", tag_slice):
                    continue
                ln = line_number_at(masked, m.start())
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "POT002",
                    rel_path,
                    ln,
                    "Dead placeholder `href=\"#\"` or empty link without a destination route or `#section` ID.",
                )

    # POT003: Theater submit handlers (setTimeout fake saves)
    for m in SUBMIT_HANDLER_DEF_RE.finditer(masked):
        open_idx = masked.find("{", m.start())
        if open_idx == -1:
            continue
        end_idx = find_matching_brace(masked, open_idx)
        if end_idx is None:
            continue
        body = masked[open_idx + 1 : end_idx]
        if (
            "setTimeout" in body
            and not re.search(
                r"\b(fetch|axios|mutate|action|submit|dispatch|onSubmit|save|api|trpc|client\.|supabase\.|prisma\.)\b",
                body,
                re.IGNORECASE,
            )
            and re.search(r"(toast|alert|setSuccess|setSaved|setSubmitted|setDone)", body, re.IGNORECASE)
        ):
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "POT003",
                rel_path,
                ln,
                f"`{m.group(1)}` fakes completion with `setTimeout` and UI feedback without calling an API or store mutation.",
            )

    # POT004 / POT005: catch blocks returning mock data or silently swallowing
    for m in CATCH_HEADER_RE.finditer(masked):
        brace_idx = masked.find("{", m.start())
        if brace_idx == -1:
            continue
        end_idx = find_matching_brace(masked, brace_idx)
        if end_idx is None:
            continue
        body = masked[brace_idx + 1 : end_idx].strip()
        raw_brace = raw_text[brace_idx + 1 : end_idx].strip()
        ln = line_number_at(masked, m.start())
        if (re.search(r"\breturn\b", body) and MOCK_IDENT_RE.search(body)) or re.search(
            r"\breturn\s+(?:(?:Next)?Response\.)?json\s*\(\s*\{\s*(?:ok|success|received)\s*:\s*true", body
        ) or re.search(
            r"\breturn\s+(?:res|reply)\.(?:status\s*\(\s*200\s*\)\s*\.)?(?:json|send)\s*\(\s*\{\s*(?:ok|success|received)\s*:\s*true",
            body,
        ):
            add_finding(
                findings,
                cfg,
                raw_lines,
                "POT004",
                rel_path,
                ln,
                "`catch` block masks failure by returning mock data or fake `{ ok: true }` success.",
            )
        elif not body and "ignore" not in raw_brace.lower() and "expected" not in raw_brace.lower() and "cleanup" not in raw_brace.lower():
            # Skip tiny best-effort cleanup catches if preceding try is <= 1 line of cleanup
            try_prefix = masked[max(0, m.start() - 160) : m.start()]
            if not re.search(r"\b(close|destroy|unlink|rmSync|remove|abort|focus)\s*\(", try_prefix):
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "POT005",
                    rel_path,
                    ln,
                    "Empty `catch` block silently swallows runtime errors.",
                )

    # POT006: Webhook verification check
    if (
        is_webhook_file_or_context(rel_path, masked)
        and not has_webhook_verification(masked)
        and re.search(r"\b(POST|post|received|200)\b", masked)
    ):
        add_finding(
            findings,
            cfg,
            raw_lines,
            "POT006",
            rel_path,
            1,
            "Webhook route/handler appears to accept POST requests without cryptographic signature verification.",
        )

    # POT007: Mock fixtures or placeholders in runtime code
    seen_mock_decls: set[tuple[int, str]] = set()
    for m in MOCK_IDENT_RE.finditer(masked):
        ln = line_number_at(masked, m.start())
        ident = m.group(0)
        if (ln, ident) in seen_mock_decls:
            continue
        line_str = line_text_at(raw_lines, ln)
        if re.match(r"^(export\s+)?(const|let|var)\s+" + re.escape(ident) + r"\s*(?::[^=]+)?=\s*[\[{]", line_str):
            seen_mock_decls.add((ln, ident))
            add_finding(
                findings,
                cfg,
                raw_lines,
                "POT007",
                rel_path,
                ln,
                f"Runtime file defines fixture constant `{ident}` outside test/mock directories.",
            )

    for m in PLACEHOLDER_TEXT_RE.finditer(masked):
        ln = line_number_at(masked, m.start())
        add_finding(
            findings,
            cfg,
            raw_lines,
            "POT007",
            rel_path,
            ln,
            f"Placeholder literal `{m.group(0)}` found inside runtime source.",
        )

    if re.search(r"\bthrow\s+new\s+Error\s*\(\s*['\"]not\s+implemented['\"]", masked, re.IGNORECASE):
        for m in re.finditer(r"\bthrow\s+new\s+Error\s*\(\s*['\"]not\s+implemented['\"]", masked, re.IGNORECASE):
            ln = line_number_at(masked, m.start())
            add_finding(
                findings,
                cfg,
                raw_lines,
                "POT007",
                rel_path,
                ln,
                "`throw new Error(\"Not implemented\")` stub in runtime code.",
            )

    # POT010: Hardcoded localhost without env var fallback on the same or nearby expression
    seen_localhost_lines: set[int] = set()
    for m in LOCALHOST_URL_RE.finditer(masked):
        ln = line_number_at(masked, m.start())
        if ln in seen_localhost_lines:
            continue
        ctx = masked[max(0, m.start() - 140) : m.start()]
        if re.search(r"(process\.env\.|import\.meta\.env\.|\|\||\?\?|config\.dev|\bisDev\b|\bdevMode\b|NODE_ENV)", ctx):
            continue
        if Path(rel_path).name.startswith(("vite.config", "next.config", "playwright", "vitest", "jest")):
            continue
        seen_localhost_lines.add(ln)
        add_finding(
            findings,
            cfg,
            raw_lines,
            "POT010",
            rel_path,
            ln,
            f"Hardcoded `{m.group(0)}` without an environment variable override.",
        )

    # Route extraction: Next.js App Router
    next_app = extract_next_app_route(rel_path)
    if next_app:
        norm_p = normalize_route_path(next_app)
        for m in NEXT_EXPORT_METHOD_RE.finditer(masked):
            ln = line_number_at(masked, m.start())
            endpoints.append(
                Endpoint(
                    method=m.group(1).upper(),
                    path=next_app,
                    normalized=norm_p,
                    file=rel_path,
                    line=ln,
                    framework="nextjs-app",
                )
            )

    # Route extraction: Next.js Pages API
    next_pages = extract_next_pages_api_route(rel_path)
    if next_pages:
        norm_p = normalize_route_path(next_pages)
        endpoints.append(
            Endpoint(
                method="ANY",
                path=next_pages,
                normalized=norm_p,
                file=rel_path,
                line=1,
                framework="nextjs-pages",
            )
        )

    # Route extraction: Express / Fastify / Hono
    for m in EXPRESS_ROUTE_RE.finditer(masked):
        obj_name, method, _, route_path = m.groups()
        # Skip axios/client calls (client objects checked separately)
        if obj_name.lower() in {"axios", "apiclient", "httpclient", "client", "got", "ky"}:
            client_calls.append(
                ClientCall(
                    method=method.upper(),
                    path=route_path,
                    normalized=normalize_route_path(route_path),
                    file=rel_path,
                    line=line_number_at(masked, m.start()),
                )
            )
            continue
        if obj_name.lower() in {"app", "router", "fastify", "server", "api", "hono", "v1"} or re.search(
            r"(express|Fastify|Hono|Router)\s*\(", masked
        ):
            ln = line_number_at(masked, m.start())
            endpoints.append(
                Endpoint(
                    method=method.upper() if method.lower() != "all" else "ANY",
                    path=route_path,
                    normalized=normalize_route_path(route_path),
                    file=rel_path,
                    line=ln,
                    framework="express/fastify/hono",
                )
            )

    # Client calls: fetch(...)
    for m in JS_FETCH_RE.finditer(masked):
        raw_url = m.group(1)[1:-1]
        opts = m.group(2) or ""
        if raw_url.startswith(("http://", "https://")) and "localhost" not in raw_url and "127.0.0.1" not in raw_url:
            continue
        norm = normalize_route_path(raw_url)
        if not has_concrete_segment(norm):
            continue
        if not (norm.startswith("/api/") or "/api/" in raw_url or raw_url.startswith("/")):
            continue
        # Only track app API routes (/api/ or /v1/ etc.), skip static assets
        if re.search(r"\.(png|jpg|jpeg|svg|css|js|json|woff2?|ico|txt|md)$", norm, re.IGNORECASE):
            continue
        mm = re.search(r"""method\s*:\s*['"]([A-Za-z]+)['"]""", opts)
        method = mm.group(1).upper() if mm else "GET"
        client_calls.append(
            ClientCall(
                method=method,
                path=raw_url,
                normalized=norm,
                file=rel_path,
                line=line_number_at(masked, m.start()),
            )
        )

    # Client calls: axios / apiClient
    for m in JS_AXIOS_RE.finditer(masked):
        method, raw_lit = m.groups()
        raw_url = raw_lit[1:-1]
        if raw_url.startswith(("http://", "https://")) and "localhost" not in raw_url:
            continue
        norm = normalize_route_path(raw_url)
        if not has_concrete_segment(norm):
            continue
        if re.search(r"\.(png|jpg|jpeg|svg|css|js|json|woff2?)$", norm, re.IGNORECASE):
            continue
        client_calls.append(
            ClientCall(
                method=method.upper(),
                path=raw_url,
                normalized=norm,
                file=rel_path,
                line=line_number_at(masked, m.start()),
            )
        )


# ---------------------------------------------------------------------------
# Python AST Scanner
# ---------------------------------------------------------------------------

def _unparse_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_unparse_name(node.value)}.{node.attr}"
    return ""


def _class_is_abstract(cls: ast.ClassDef) -> bool:
    for b in cls.bases:
        bn = _unparse_name(b)
        if bn.endswith(("ABC", "Protocol")):
            return True
    return False


def _stmt_is_cleanup(stmts: list[ast.stmt]) -> bool:
    if len(stmts) > 2:
        return False
    text = " ".join(ast.unparse(s) for s in stmts if hasattr(ast, "unparse"))
    return bool(re.search(r"\b(close|unlink|remove|rmdir|mkdir|kill|terminate|import |pass|__)\b", text))


def _node_returns_mock_or_fake_ok(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and sub.value is not None:
            ret_src = ast.unparse(sub.value) if hasattr(ast, "unparse") else ""
            if MOCK_IDENT_RE.search(ret_src):
                return True
            if isinstance(sub.value, ast.Dict):
                keys = [
                    k.value.lower()
                    for k in sub.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                ]
                vals = [
                    v.value
                    for v in sub.value.values
                    if isinstance(v, ast.Constant)
                ]
                if any(k in {"ok", "success", "received"} for k in keys) and True in vals:
                    return True
    return False


def _extract_py_router_prefixes(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """Return local APIRouter/Blueprint prefixes (`router -> '/users'`) and include_router mounts."""
    var_prefixes: dict[str, str] = {}
    include_mounts: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if isinstance(node.value, ast.Call):
                fn = _unparse_name(node.value.func)
                if fn.endswith(("APIRouter", "Blueprint")):
                    for kw in node.value.keywords:
                        if kw.arg in {"prefix", "url_prefix"} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            var_prefixes[target] = kw.value.value
        elif isinstance(node, ast.Call):
            fn = _unparse_name(node.func)
            if fn.endswith("include_router") and node.args:
                router_ref = _unparse_name(node.args[0])
                prefix = ""
                for kw in node.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        prefix = kw.value.value
                if router_ref and prefix:
                    include_mounts[router_ref] = prefix
    return var_prefixes, include_mounts


def scan_python_file(
    rel_path: str,
    raw_text: str,
    cfg: ScanConfig,
    is_test: bool,
    findings: list[Finding],
    endpoints: list[Endpoint],
    env_vars_used: dict[str, list[tuple[str, int, bool]]],
    py_include_mounts: dict[str, str],
) -> None:
    raw_lines = raw_text.splitlines()
    try:
        tree = ast.parse(raw_text, filename=rel_path)
    except SyntaxError:
        return

    var_prefixes, local_mounts = _extract_py_router_prefixes(tree)
    for k, v in local_mounts.items():
        py_include_mounts[k] = v

    # Extract env reads & POT011 secret defaults via AST
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn_name = _unparse_name(node.func)
            if (
                fn_name in {"os.getenv", "os.environ.get"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                var_name = node.args[0].value
                if not is_test:
                    # .get / getenv safely returns None; treat direct subscript or explicit strict helpers as required
                    env_vars_used[var_name].append((rel_path, node.lineno, True))
                    if SENSITIVE_ENV_TOKEN_RE.search(var_name):
                        default_val = None
                        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                            default_val = node.args[1].value
                        for kw in node.keywords:
                            if kw.arg == "default" and isinstance(kw.value, ast.Constant):
                                default_val = kw.value.value
                        if isinstance(default_val, str) and len(default_val) >= 2:
                            add_finding(
                                findings,
                                cfg,
                                raw_lines,
                                "POT011",
                                rel_path,
                                node.lineno,
                                f"Hardcoded default `'{default_val}'` supplied for secret `{var_name}`.",
                            )
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and _unparse_name(node.value) == "os.environ"
        ):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and not is_test:
                env_vars_used[sl.value].append((rel_path, node.lineno, False))

    if is_test:
        return

    # Track parent classes so @abstractmethod / ABC stubs aren't flagged as POT007
    abstract_fn_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _class_is_abstract(node):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    abstract_fn_ids.add(id(item))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if _unparse_name(dec).endswith("abstractmethod"):
                    abstract_fn_ids.add(id(node))

    # Walk AST functions for NotImplementedError, try/except, webhook, routes
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Route decorator inspection
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    dec_name = _unparse_name(dec.func)
                    parts = dec_name.split(".")
                    if len(parts) == 2 and parts[1].lower() in {"get", "post", "put", "patch", "delete", "route"}:
                        obj_var, verb = parts
                        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            rpath = dec.args[0].value
                            prefix = var_prefixes.get(obj_var, "")
                            full = f"{prefix}{rpath}" if prefix and not rpath.startswith(prefix) else rpath
                            methods = [verb.upper()]
                            if verb.lower() == "route":
                                methods = ["GET"]
                                for kw in dec.keywords:
                                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                        methods = [
                                            e.value.upper()
                                            for e in kw.value.elts
                                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                                        ] or ["ANY"]
                            for m in methods:
                                endpoints.append(
                                    Endpoint(
                                        method=m,
                                        path=full,
                                        normalized=normalize_route_path(full),
                                        file=rel_path,
                                        line=node.lineno,
                                        framework="fastapi/flask",
                                    )
                                )

            # POT007: raise NotImplementedError outside ABCs
            if id(node) not in abstract_fn_ids:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Raise) and sub.exc is not None:
                        exc_name = _unparse_name(sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc)
                        if exc_name == "NotImplementedError":
                            add_finding(
                                findings,
                                cfg,
                                raw_lines,
                                "POT007",
                                rel_path,
                                sub.lineno,
                                f"`raise NotImplementedError` inside runtime function `{node.name}`.",
                            )

        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if _node_returns_mock_or_fake_ok(handler):
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "POT004",
                        rel_path,
                        handler.lineno,
                        "`except` block returns mock fixture or fake `ok: True` success.",
                    )
                elif (
                    (handler.type is None or _unparse_name(handler.type) in {"Exception", "BaseException"})
                    and len(handler.body) == 1
                    and isinstance(handler.body[0], ast.Pass)
                    and not _stmt_is_cleanup(node.body)
                    and len(node.body) >= 2
                ):
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "POT005",
                        rel_path,
                        handler.lineno,
                        "Broad silent `except ...: pass` swallows runtime errors on multi-step block.",
                    )

        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (
                    isinstance(tgt, ast.Name)
                    and MOCK_IDENT_RE.fullmatch(tgt.id)
                    and isinstance(node.value, (ast.List, ast.Dict))
                ):
                    add_finding(
                        findings,
                        cfg,
                        raw_lines,
                        "POT007",
                        rel_path,
                        node.lineno,
                        f"Runtime file declares mock fixture `{tgt.id}` outside test directories.",
                    )

    # Webhook route check in Python
    if (
        is_webhook_file_or_context(rel_path, raw_text)
        and not has_webhook_verification(raw_text)
        and any("/webhook" in ep.path.lower() or "webhook" in rel_path.lower() for ep in endpoints if ep.file == rel_path)
    ):
        add_finding(
            findings,
            cfg,
            raw_lines,
            "POT006",
            rel_path,
            1,
            "Python webhook handler lacks cryptographic signature verification.",
        )

    # Hardcoded localhost + placeholder literals line scan (strings inside runtime file)
    for ln, line in enumerate(raw_lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m_loc = LOCALHOST_URL_RE.search(line)
        if (
            m_loc
            and not re.search(r"(os\.getenv|os\.environ|\.get\()", line)
            and Path(rel_path).name not in {"settings.py", "config.py"}
        ):
            add_finding(
                findings,
                cfg,
                raw_lines,
                "POT010",
                rel_path,
                ln,
                f"Hardcoded `{m_loc.group(0)}` without an environment variable override.",
            )
        m_ph = PLACEHOLDER_TEXT_RE.search(line)
        if m_ph:
            add_finding(
                findings,
                cfg,
                raw_lines,
                "POT007",
                rel_path,
                ln,
                f"Placeholder literal `{m_ph.group(0)}` found inside runtime source.",
            )


# ---------------------------------------------------------------------------
# Full-Stack Wiring & Env Audit Post-Processors
# ---------------------------------------------------------------------------

def resolve_wire_gaps(
    cfg: ScanConfig,
    file_texts: dict[str, str],
    endpoints: list[Endpoint],
    client_calls: list[ClientCall],
    findings: list[Finding],
) -> dict[str, Any]:
    """Compare discovered backend routes against client fetches."""
    summary: dict[str, Any] = {
        "backend_routes": len(endpoints),
        "client_calls": len(client_calls),
        "dead_client_calls": 0,
        "orphan_routes": 0,
    }
    if not endpoints:
        return summary

    # POT008: Check frontend calls against backend routes
    for call in client_calls:
        path_matches = [ep for ep in endpoints if routes_match(call.normalized, ep.normalized)]
        if not path_matches:
            # Guard: only flag `/api/...` calls so internal page navigations aren't falsely flagged
            if call.normalized.startswith("/api/"):
                raw_lines = file_texts[call.file].splitlines()
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "POT008",
                    call.file,
                    call.line,
                    f"`{call.method} {call.path}` targets no matching backend route handler.",
                )
                summary["dead_client_calls"] += 1
        else:
            method_ok = any(ep.method == "ANY" or ep.method == call.method for ep in path_matches)
            if not method_ok:
                avail = sorted({ep.method for ep in path_matches})
                raw_lines = file_texts[call.file].splitlines()
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "POT008",
                    call.file,
                    call.line,
                    f"`{call.method} {call.path}` method mismatch; backend exposes {', '.join(avail)}.",
                )
                summary["dead_client_calls"] += 1

    # POT009: Orphan backend routes (only when repo has multiple routes and some callers or client code)
    if cfg.strict_orphan_routes and len(endpoints) >= 1 and client_calls:
        other_corpus = "\n".join(file_texts.values())
        for ep in endpoints:
            if HEALTH_OR_INFRA_ROUTE_RE.search(ep.normalized):
                continue
            matched = any(routes_match(c.normalized, ep.normalized) for c in client_calls)
            if matched:
                continue
            # Also check static base path occurrence outside definition file
            base_probe = re.sub(r"/\{param\}.*$", "", ep.normalized)
            refs = 0
            if len(base_probe) >= 4:
                for path_key, content in file_texts.items():
                    if path_key != ep.file and base_probe in content:
                        refs += 1
                        break
            if refs == 0 and len(other_corpus) > 0:
                raw_lines = file_texts[ep.file].splitlines()
                add_finding(
                    findings,
                    cfg,
                    raw_lines,
                    "POT009",
                    ep.file,
                    ep.line,
                    f"Backend route `{ep.method} {ep.path}` has no matching frontend or test references.",
                )
                summary["orphan_routes"] += 1

    return summary


def resolve_env_drift(
    root: Path,
    cfg: ScanConfig,
    file_texts: dict[str, str],
    env_vars_used: dict[str, list[tuple[str, int, bool]]],
    findings: list[Finding],
) -> dict[str, Any]:
    template_candidates = [root / ".env.example", root / ".env.sample", root / ".env.template"]
    template = next((p for p in template_candidates if p.is_file()), None)
    result: dict[str, Any] = {
        "template_file": str(template.relative_to(root)) if template else None,
        "vars_referenced": len(env_vars_used),
        "missing_from_template": [],
    }
    if not template or not cfg.strict_env_drift:
        return result

    declared: set[str] = set()
    for line in template.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=", line)
        if m:
            declared.add(m.group(1))

    for var_name, occurrences in sorted(env_vars_used.items()):
        if (
            var_name in STD_ENV_VARS
            or var_name.startswith(("GITHUB_", "VERCEL_", "NO_COLOR", "FORCE_COLOR", "npm_", "PYTHON"))
            or var_name in declared
        ):
            continue
        # Only flag if at least one occurrence is required (no fallback default)
        required_hits = [occ for occ in occurrences if not occ[2]]
        if not required_hits:
            continue
        first_file, first_line, _ = required_hits[0]
        result["missing_from_template"].append(var_name)
        raw_lines = file_texts[first_file].splitlines()
        add_finding(
            findings,
            cfg,
            raw_lines,
            "POT013",
            first_file,
            first_line,
            f"Required env var `{var_name}` is missing from `{result['template_file']}`.",
        )

    return result


# ---------------------------------------------------------------------------
# Git Diff Reward-Hacking Guard (POT014, POT015, POT016)
# ---------------------------------------------------------------------------

DIFF_SKIP_RE = re.compile(
    r"(\b(?:it|test|describe)\.(?:skip|only)\s*\(|"
    r"\b(?:xit|xtest|xdescribe)\s*\(|"
    r"@pytest\.mark\.(?:skip|skipif|xfail)\b|"
    r"@unittest\.skip\b|"
    r"\bpytest\.skip\s*\(|"
    r"\bt\.Skip\s*\()"
)

DIFF_SUPPRESS_RE = re.compile(
    r"(@ts-ignore|@ts-nocheck|\bas\s+any\b|#\s*type:\s*ignore\b|"
    r"#\s*noqa\b|eslint-disable|--no-verify|\|\|\s*true\b)"
)

TRIVIAL_ASSERT_RE = re.compile(
    r"(\bassert\s+True\b|\bexpect\s*\(\s*true\s*\)\.toBe\s*\(\s*true\s*\)|"
    r"\bexpect\s*\(\s*1\s*\)\.toBe\s*\(\s*1\s*\))"
)

ASSERTION_LINE_RE = re.compile(r"(\bassert\b|\bassert_\w+|\bexpect\s*\(|self\.assert)")


def scan_git_diff(root: Path, diff_ref: str | None, staged: bool, cfg: ScanConfig, findings: list[Finding]) -> dict[str, Any]:
    cmd = ["git", "-C", str(root), "diff", "--unified=0", "--no-color"]
    if staged:
        cmd.append("--staged")
    elif diff_ref:
        cmd.append(diff_ref)
    else:
        cmd.append("HEAD")

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"ran": False, "error": proc.stderr.strip()}

    cur_file = ""
    cur_line = 0
    test_assert_delta: dict[str, tuple[int, int, int]] = {}  # file -> (added, removed, first_rm_line)
    in_hunk = False

    for line in proc.stdout.splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:]
            cur_line = 0
            in_hunk = False
        elif line.startswith("@@ "):
            m = re.search(r"\+(\d+)", line)
            cur_line = int(m.group(1)) if m else 1
            in_hunk = True
        elif in_hunk and cur_file and not is_excluded(cur_file, cfg):
            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                raw_lines = [content]
                # Skip scanning potemkin itself / documentation prose unless test file
                if not cur_file.endswith((".md", ".rst", ".txt")) and "potemkin-ignore" not in content:
                    if DIFF_SKIP_RE.search(content):
                        add_finding(
                            findings,
                            cfg,
                            raw_lines,
                            "POT014",
                            cur_file,
                            cur_line,
                            "Added skipped/disabled test annotation in diff.",
                            snippet=content.strip(),
                        )
                    elif DIFF_SUPPRESS_RE.search(content) and not cur_file.endswith("potemkin.py"):
                        add_finding(
                            findings,
                            cfg,
                            raw_lines,
                            "POT015",
                            cur_file,
                            cur_line,
                            "Added type/lint/hook suppression or `|| true` masking in diff.",
                            snippet=content.strip(),
                        )
                    elif TRIVIAL_ASSERT_RE.search(content):
                        add_finding(
                            findings,
                            cfg,
                            raw_lines,
                            "POT016",
                            cur_file,
                            cur_line,
                            "Added trivial no-op assertion (`assert True` / `expect(true).toBe(true)`).",
                            snippet=content.strip(),
                        )
                if is_test_or_fixture_path(cur_file) and ASSERTION_LINE_RE.search(content):
                    a, r, fl = test_assert_delta.get(cur_file, (0, 0, cur_line))
                    test_assert_delta[cur_file] = (a + 1, r, fl)
                cur_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                content = line[1:]
                if is_test_or_fixture_path(cur_file) and ASSERTION_LINE_RE.search(content):
                    a, r, fl = test_assert_delta.get(cur_file, (0, 0, cur_line))
                    test_assert_delta[cur_file] = (a, r + 1, fl if r > 0 else cur_line)

    for tf, (added, removed, fl) in test_assert_delta.items():
        if removed > added and removed >= 2:
            add_finding(
                findings,
                cfg,
                [""],
                "POT016",
                tf,
                max(1, fl),
                f"Test file removed {removed} assertion lines while only adding {added}.",
                snippet=f"assertions -{removed} / +{added}",
            )

    return {"ran": True, "ref": "--staged" if staged else (diff_ref or "HEAD")}


# ---------------------------------------------------------------------------
# Baseline, Scoring & Output Formatters
# ---------------------------------------------------------------------------

def score_findings(findings: list[Finding]) -> tuple[int, str]:
    penalty = sum(SEVERITY_PENALTY.get(f.severity, 1) for f in findings)
    score = max(0, 100 - penalty)
    if score >= 90 and not any(f.severity == "critical" for f in findings):
        grade = "VERIFIED"
    elif score >= 70:
        grade = "CAUTION"
    else:
        grade = "POTEMKIN ALERT"
    return score, grade


def load_baseline(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(x) for x in data.get("fingerprints", [])}


def save_baseline(path: Path, findings: list[Finding]) -> None:
    payload = {
        "tool": "potemkin",
        "version": VERSION,
        "count": len(findings),
        "fingerprints": sorted({f.fingerprint for f in findings}),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_report(
    target: Path,
    findings: list[Finding],
    files_scanned: int,
    wire_summary: dict[str, Any],
    env_summary: dict[str, Any],
    diff_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    pillars: dict[str, int] = defaultdict(int)
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
        pillars[f.pillar] += 1
    score, grade = score_findings(findings)
    findings_sorted = sorted(
        findings,
        key=lambda f: (-SEVERITY_ORDER.get(f.severity, 0), f.file, f.line, f.rule_id),
    )
    return {
        "tool": "potemkin",
        "version": VERSION,
        "target": str(target),
        "score": score,
        "grade": grade,
        "files_scanned": files_scanned,
        "counts": counts,
        "pillars": dict(sorted(pillars.items())),
        "wire_graph": wire_summary,
        "env_audit": env_summary,
        "diff_audit": diff_summary,
        "findings": [asdict(f) for f in findings_sorted],
    }


def format_text(report: dict[str, Any], use_color: bool = True) -> str:
    def c(code: str, txt: str) -> str:
        return f"\033[{code}m{txt}\033[0m" if use_color else txt

    sev_color = {"critical": "1;31", "high": "31", "medium": "33", "low": "36"}
    score_color = "32" if report["score"] >= 90 else ("33" if report["score"] >= 70 else "31")
    score_label = f"{report['score']}/100 ({report['grade']})"
    lines = [
        c("1", f"Potemkin v{report['version']} — Real-Code Verification Report"),
        f"Target: {report['target']} | Files scanned: {report['files_scanned']} | Backend routes: {report['wire_graph']['backend_routes']} | Client calls: {report['wire_graph']['client_calls']}",
        f"Score:  {c(score_color, score_label)}  "
        f"[critical={report['counts']['critical']} high={report['counts']['high']} medium={report['counts']['medium']} low={report['counts']['low']}]",
        "",
    ]
    if not report["findings"]:
        lines.append(c("32", "No Potemkin stubs, fake fallbacks, dead wires, or reward-hacking detected."))
        return "\n".join(lines)

    for f in report["findings"]:
        tag = c(sev_color.get(f["severity"], "0"), f"[{f['severity'].upper():8s}] {f['rule_id']}")
        lines.append(f"{tag} {f['file']}:{f['line']} — {f['message']}")
        if f["snippet"]:
            lines.append(f"    code: {f['snippet']}")
        lines.append(f"    fix:  {f['help']}")
    return "\n".join(lines)


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"## Potemkin Real-Code Audit — **{report['score']}/100 ({report['grade']})**",
        "",
        f"- **Files scanned:** {report['files_scanned']}",
        f"- **Wire graph:** {report['wire_graph']['backend_routes']} backend routes, {report['wire_graph']['client_calls']} client calls",
        f"- **Findings:** {report['counts']['critical']} critical, {report['counts']['high']} high, {report['counts']['medium']} medium, {report['counts']['low']} low",
        "",
    ]
    if not report["findings"]:
        lines.append("All checked runtime files passed without Potemkin stubs, deceptive fallbacks, dead wires, or test-cheating.")
        return "\n".join(lines)

    lines.extend([
        "| Severity | Rule | Location | Finding |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for f in report["findings"]:
        loc = f"`{f['file']}:{f['line']}`"
        msg = f["message"].replace("|", "\\|")
        lines.append(f"| `{f['severity'].upper()}` | `{f['rule_id']}` | {loc} | {msg} |")
    return "\n".join(lines)


def format_sarif(report: dict[str, Any]) -> str:
    rules_arr = [
        {
            "id": rid,
            "shortDescription": {"text": meta["title"]},
            "help": {"text": meta["help"]},
            "properties": {"pillar": meta["pillar"], "severity": meta["severity"]},
        }
        for rid, meta in RULE_META.items()
    ]
    sev_to_level = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
    results = [
        {
            "ruleId": f["rule_id"],
            "level": sev_to_level.get(f["severity"], "warning"),
            "message": {"text": f["message"]},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f["file"]},
                        "region": {"startLine": max(1, int(f["line"]))},
                    }
                }
            ],
            "partialFingerprints": {"potemkinFingerprint/v1": f["fingerprint"]},
        }
        for f in report["findings"]
    ]
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Potemkin",
                        "version": VERSION,
                        "informationUri": "https://github.com/codesphere-u/potemkin",
                        "rules": rules_arr,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


def run_scan(
    target: Path,
    *,
    diff_ref: str | None = None,
    with_diff: bool = False,
    staged: bool = False,
    ignore_rules: Iterable[str] = (),
    baseline_path: Path | None = None,
) -> dict[str, Any]:
    root = target.resolve()
    cfg = load_config(root)
    cfg.ignore_rules.update(r.upper() for r in ignore_rules)

    file_texts: dict[str, str] = {}
    findings: list[Finding] = []
    endpoints: list[Endpoint] = []
    client_calls: list[ClientCall] = []
    env_vars_used: dict[str, list[tuple[str, int, bool]]] = defaultdict(list)
    py_include_mounts: dict[str, str] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for fname in sorted(filenames):
            if fname.lower().endswith(SKIP_FILE_SUFFIXES):
                continue
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() not in CODE_EXTENSIONS:
                continue
            try:
                if fpath.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            rel_path = fpath.relative_to(root).as_posix()
            if is_excluded(rel_path, cfg):
                continue
            # Avoid flagging potemkin's own detection regex constants if scanning self
            if rel_path == "skills/potemkin/scripts/potemkin.py":
                continue
            try:
                raw_text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            file_texts[rel_path] = raw_text
            test_flag = is_test_or_fixture_path(rel_path)

            if fpath.suffix.lower() in PY_EXTENSIONS:
                scan_python_file(
                    rel_path,
                    raw_text,
                    cfg,
                    test_flag,
                    findings,
                    endpoints,
                    env_vars_used,
                    py_include_mounts,
                )
            else:
                scan_js_ts_file(
                    rel_path,
                    raw_text,
                    cfg,
                    test_flag,
                    findings,
                    endpoints,
                    client_calls,
                    env_vars_used,
                )

    wire_summary = resolve_wire_gaps(cfg, file_texts, endpoints, client_calls, findings)
    env_summary = resolve_env_drift(root, cfg, file_texts, env_vars_used, findings)

    diff_summary = None
    if with_diff or staged or diff_ref is not None:
        diff_summary = scan_git_diff(root, diff_ref, staged, cfg, findings)

    if baseline_path is not None:
        known = load_baseline(baseline_path)
        if known:
            findings = [f for f in findings if f.fingerprint not in known]

    return build_report(root, findings, len(file_texts), wire_summary, env_summary, diff_summary)


def should_fail(findings: list[dict[str, Any]], score: int, fail_on: str, min_score: int | None) -> bool:
    if min_score is not None and score < min_score:
        return True
    if fail_on == "none":
        return False
    threshold = 1 if fail_on == "any" else SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER.get(f["severity"], 0) >= threshold for f in findings)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="potemkin",
        description="Expose Potemkin stubs, fake fallbacks, dead wires & AI reward-hacking.",
    )
    p.add_argument("target", nargs="?", default=".", help="Repository directory to scan (default: .)")
    p.add_argument("--format", choices=["text", "markdown", "json", "sarif"], default="text")
    p.add_argument("--diff", nargs="?", const="", default=None, metavar="REF", help="Also audit git diff (default: HEAD)")
    p.add_argument("--staged", action="store_true", help="Audit staged git diff")
    p.add_argument(
        "--fail-on",
        choices=["critical", "high", "medium", "low", "any", "none"],
        default="high",
        help="Minimum severity triggering exit code 1 (default: high)",
    )
    p.add_argument("--min-score", type=int, default=None, help="Fail if score drops below this threshold (0-100)")
    p.add_argument("--ignore-rule", action="append", default=[], help="Ignore specific rule ID (repeatable)")
    p.add_argument("--baseline", type=Path, default=None, help="Suppress findings matching baseline JSON fingerprints")
    p.add_argument("--write-baseline", type=Path, default=None, help="Write current findings baseline JSON and exit 0")
    p.add_argument("--output", type=Path, default=None, help="Write report output to file as well as stdout")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI color in text output")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.target)
    if not target.is_dir():
        print(f"potemkin: target directory does not exist: {target}", file=sys.stderr)
        return 2
    if args.min_score is not None and not 0 <= args.min_score <= 100:
        print(f"potemkin: --min-score must be between 0 and 100, got {args.min_score}", file=sys.stderr)
        return 2

    report = run_scan(
        target,
        diff_ref=args.diff or None,
        with_diff=args.diff is not None,
        staged=args.staged,
        ignore_rules=args.ignore_rule,
        baseline_path=args.baseline,
    )

    diff_info = report.get("diff_audit")
    if isinstance(diff_info, dict) and diff_info.get("ran") is False and diff_info.get("error"):
        print(f"potemkin: warning: git diff audit skipped ({diff_info['error']})", file=sys.stderr)

    if args.write_baseline is not None:
        reconstructed = [Finding(**f) for f in report["findings"]]
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        save_baseline(args.write_baseline, reconstructed)
        print(f"Wrote baseline with {len(reconstructed)} fingerprints to {args.write_baseline}")
        return 0

    if args.format == "json":
        rendered = json.dumps(report, indent=2)
    elif args.format == "markdown":
        rendered = format_markdown(report)
    elif args.format == "sarif":
        rendered = format_sarif(report)
    else:
        use_color = not args.no_color and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        rendered = format_text(report, use_color=use_color)

    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    return 1 if should_fail(report["findings"], report["score"], args.fail_on, args.min_score) else 0


if __name__ == "__main__":
    raise SystemExit(main())
