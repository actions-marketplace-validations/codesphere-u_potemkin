<div align="center">

# Potemkin

**Deterministic Agent Skill & CI Gate that exposes where AI-written or scaffolded code faked `"production ready"`.**

[![CI](https://github.com/codesphere-u/potemkin/actions/workflows/ci.yml/badge.svg)](https://github.com/codesphere-u/potemkin/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0%20(stdlib%20only)-brightgreen.svg)](#architecture)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Works as an **Agent Skill** (`npx skills add`, Claude Code, Cursor, Antigravity, Codex), **CLI** (`uvx` / `pip`), **GitHub Action**, and **Docker container**.

</div>

---

## Why Potemkin?

Syntax linters verify formatting. Typecheckers verify signatures. Existing AI review skills rely on prose checklists that agents routinely skim past.

**Potemkin code passes `eslint` and `tsc` while lying about completeness:**

- Buttons whose `onClick` runs `() => {}` or `alert("Exporting PDF...")`
- Submit handlers simulating saves with `setTimeout(() => setSaved(true), 600)`
- API `catch` blocks silently returning `MOCK_ORDERS` or fake `{ ok: true }`
- Webhook routes returning `200 OK` without checking `stripe-signature` / HMAC headers
- Frontend `fetch('/api/orders/123', { method: 'DELETE' })` calls hitting backends that only expose `GET`
- `process.env.JWT_SECRET || "dev-secret-do-not-use"` and `NEXT_PUBLIC_ADMIN_SECRET` client leaks
- Agents "fixing" failing CI by slipping `.skip`, `@ts-ignore`, `# type: ignore`, `|| true`, or deleting assertions in the diff

**Potemkin catches all of these deterministically in milliseconds with zero external packages.**

---

## Quick Start

### Install as an Agent Skill

```bash
# Universal Agent Skills CLI (Claude Code, Cursor, Antigravity, Codex, OpenCode, Windsurf)
npx skills add codesphere-u/potemkin
```

<details>
<summary>Alternative agent installations (Claude Code plugin marketplace, Antigravity workspace skill)</summary>

**Claude Code Plugin Marketplace:**
```text
/plugin marketplace add codesphere-u/potemkin
/plugin install potemkin@potemkin-marketplace
```

**Manual / Workspace skill copy:**
Copy `skills/potemkin/` into `.agents/skills/potemkin/` (repo-local) or `~/.gemini/antigravity/skills/potemkin/`.

</details>

### Run Directly via CLI / `uvx`

```bash
# Audit current repo (plus git diff anti-reward-hacking check)
uvx --from git+https://github.com/codesphere-u/potemkin potemkin . --diff HEAD

# Or run the bundled zero-dependency script anywhere Python 3.10+ exists
python3 skills/potemkin/scripts/potemkin.py . --diff HEAD --fail-on high
```

### Add as a GitHub Action (PR & Push Gate)

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0

- uses: codesphere-u/potemkin@v1
  with:
    diff: origin/main...HEAD
    fail-on: high
    min-score: "80"
```

---

## Example Output

Running Potemkin on the included full-stack benchmark fixture [`tests/fixtures/potemkin_app`](tests/fixtures/potemkin_app):

```text
Potemkin v1.0.0 — Real-Code Verification Report
Target: tests/fixtures/potemkin_app | Files scanned: 5 | Backend routes: 3 | Client calls: 1
Score:  0/100 (POTEMKIN ALERT)  [critical=4 high=8 medium=5 low=0]

[CRITICAL] POT004 src/app/api/orders/[id]/route.ts:9 — `catch` block masks failure by returning mock data or fake `{ ok: true }` success.
    code: } catch {
    fix:  Log and propagate or return a real error response instead of faking success/mock data.
[CRITICAL] POT011 src/app/api/orders/[id]/route.ts:15 — Hardcoded fallback `"dev-secret-do-not-use"` supplied for secret `JWT_SECRET`.
    code: return process.env.JWT_SECRET || "dev-secret-do-not-use";
    fix:  Fail fast at startup if required secret env vars are unset in production.
[CRITICAL] POT006 src/app/api/stripe/webhook/route.ts:1 — Webhook route/handler appears to accept POST requests without cryptographic signature verification.
    code: export async function POST(req: Request) {
    fix:  Verify provider HMAC/webhook signature headers before trusting payloads or returning 200 OK.
[CRITICAL] POT012 src/components/BillingPanel.tsx:26 — `NEXT_PUBLIC_ADMIN_SECRET` uses a public client-bundle prefix for a sensitive secret name.
    code: <p>{process.env.NEXT_PUBLIC_ADMIN_SECRET}</p>
    fix:  Remove NEXT_PUBLIC_/VITE_/PUBLIC_ prefix and keep secrets strictly server-side.
[HIGH    ] POT005 backend/service.py:10 — Broad silent `except ...: pass` swallows runtime errors on multi-step block.
    code: except Exception:
    fix:  Handle, log, or rethrow exceptions explicitly so runtime failures are never hidden.
[HIGH    ] POT007 backend/service.py:15 — `raise NotImplementedError` inside runtime function `unimplemented_exporter`.
    code: raise NotImplementedError("implement later")
    fix:  Replace stub/fixture data in runtime modules with real data loading or raise only in ABCs.
[HIGH    ] POT008 src/components/BillingPanel.tsx:18 — `DELETE /api/orders/${id}` method mismatch; backend exposes GET.
    code: return fetch(`/api/orders/${id}`, { method: "DELETE" });
    fix:  Align the frontend endpoint/method with a real backend route handler.
[HIGH    ] POT003 src/components/BillingPanel.tsx:10 — `handleSubmit` fakes completion with `setTimeout` and UI feedback without calling an API or store mutation.
...
```

Running on [`tests/fixtures/clean_app`](tests/fixtures/clean_app) produces:

```text
Potemkin v1.0.0 — Real-Code Verification Report
Target: tests/fixtures/clean_app | Files scanned: 4 | Backend routes: 4 | Client calls: 3
Score:  100/100 (VERIFIED)  [critical=0 high=0 medium=0 low=0]

No Potemkin stubs, fake fallbacks, dead wires, or reward-hacking detected.
```

---

## The 6 Pillars (`POT001`–`POT016`)

| Pillar | Rules | What Potemkin Verifies |
| :--- | :--- | :--- |
| **`HOLLOW_UI`** | `POT001`–`POT003` | Empty/`alert()`/`console.log` JSX handlers, dead `href="#"` placeholders (allowing valid SPA `onClick` anchors), and `setTimeout` + `toast` theater forms |
| **`FAKE_FALLBACK`** | `POT004`–`POT006` | `catch`/`except` blocks returning mock arrays or fake `{ ok: true }`, broad silent catches, and unverified webhook endpoints |
| **`MOCK_IN_PROD`** | `POT007` | Runtime `MOCK_*`/`mockUsers` fixtures, `"Coming soon"`/`"test@example.com"` strings, and `NotImplementedError` outside `ABC`s |
| **`WIRE_GAP`** | `POT008`–`POT010` | Frontend `fetch`/`axios` calls vs backend routes (Next.js App/Pages, Express/Fastify/Hono, FastAPI/Flask), orphan endpoints, and bare `localhost` URLs |
| **`ENV_TRUTH`** | `POT011`–`POT013` | Hardcoded secret fallbacks, secrets exposed under `NEXT_PUBLIC_`/`VITE_`/`PUBLIC_` prefixes, and required runtime env vars missing from `.env.example` |
| **`DIFF_CHEAT`** | `POT014`–`POT016` | Git diff (`--diff`, `--staged`) catching newly added `.skip`/`pytest.mark.skip`, `@ts-ignore`/`# type: ignore`/`eslint-disable`/`\|\| true`, and deleted/trivial test assertions |

See [skills/potemkin/references/rules.md](skills/potemkin/references/rules.md) for the complete rule matrix and false-positive guards, and [skills/potemkin/references/remediation.md](skills/potemkin/references/remediation.md) for production fixes.

---

## Real-Code Score & Exit Thresholds

- Deductions: `CRITICAL` (`-18`), `HIGH` (`-9`), `MEDIUM` (`-4`), `LOW` (`-1`)
- Grades:
  - `90–100` (with `0 CRITICAL`): **`VERIFIED`**
  - `70–89`: **`CAUTION`**
  - `<70`: **`POTEMKIN ALERT`**
- Default CI gate: `--fail-on high` (exits `1` if any `CRITICAL` or `HIGH` finding exists; exits `2` on invalid CLI args/missing target).

---

## Configuration, Baselines & Suppressions

### Incremental Rollout on Legacy Codebases

```bash
# Snapshot existing technical debt once
potemkin . --write-baseline .potemkin-baseline.json

# Fail CI only on newly introduced Potemkin findings + diff cheating
potemkin . --diff origin/main...HEAD --baseline .potemkin-baseline.json --fail-on high
```

### Config Files

- **`.potemkinignore`**: Gitignore-style paths and globs to exclude (e.g., `legacy-prototype/`, `packages/sandbox/*.tsx`).
- **`.potemkin.json`**:
  ```json
  {
    "ignoreRules": ["POT010"],
    "exclude": ["examples/"]
  }
  ```
- **Inline Suppression**: Append `potemkin-ignore: POT010 - reason` on the same line or preceding line for documented exceptions (rule-scoped so unrelated bugs on that line still fire).

---

## CLI Reference

```text
potemkin [target] [options]

Options:
  --format {text,markdown,json,sarif}   Report format (default: text)
  --diff [REF]                         Inspect git diff (defaults to HEAD) for POT014-POT016
  --staged                             Inspect staged git index for POT014-POT016
  --fail-on {critical,high,medium,low,any,none}
                                       Minimum severity that exits non-zero (default: high)
  --min-score N                        Fail if Real-Code Score is below N (0-100)
  --ignore-rule POTxxx                 Suppress specific rule ID (repeatable)
  --baseline PATH                      Suppress fingerprinted baseline findings
  --write-baseline PATH                Write current findings to baseline JSON
  --output PATH                        Write formatted report to a file
  --no-color                           Disable ANSI color escapes
  --version                            Show version and exit
```

### Docker

```bash
docker build -t potemkin .
docker run --rm -v "$PWD:/workspace:ro" potemkin . --fail-on high --no-color
```

---

## Architecture

- **Single-source, zero-dependency engine** ([skills/potemkin/scripts/potemkin.py](skills/potemkin/scripts/potemkin.py)): Uses only the Python 3.10+ standard library (`ast`, `re`, `json`, `hashlib`, `subprocess`, `argparse`, `pathlib`, `fnmatch`, `dataclasses`) so agents can execute it straight out of `~/.agents/skills/potemkin` or `.claude/skills/potemkin` without `pip install` or network calls.
- **Language-aware scanning:** Combines Python's compiler `ast` (detecting `ast.Load` vs `ast.Store` on `os.environ`, `ABC` / `@abstractmethod` exemptions, broad `except:` vs narrow parser exceptions) with a comment-masking JavaScript/TypeScript/JSX/Vue/Svelte lexer and brace matcher.
- **Full-stack route graph:** Normalizes Next.js App Router (`src/app/api/.../route.ts`), Next.js Pages API, Express/Fastify/Hono handlers, and FastAPI/Flask `APIRouter`/`Blueprint` prefixes into a unified endpoint table matched against `fetch`/`axios` calls.

---

## Contributing & Verification

```bash
pip install -e ".[dev]"
ruff check .
mypy
pytest -v
potemkin . --fail-on any --min-score 100
```

See [CHANGELOG.md](CHANGELOG.md) for release notes and [LICENSE](LICENSE) (MIT).
