---
name: potemkin
description: >-
  Deterministic verification skill that exposes Potemkin code—hollow UI buttons,
  fake setTimeout saves, catch blocks returning mock data, unverified webhooks,
  dead frontend-to-backend API fetches, orphan endpoints, secret fallbacks, env
  drift, and AI test-cheating (.skip, @ts-ignore, hollowed assertions). Use
  before claiming a feature, refactor, PR, or AI-built codebase is done or
  production ready.
license: MIT
compatibility: Requires Python 3.10+ (stdlib only, zero external packages) and optional git for --diff mode.
metadata:
  author: codesphere-u
  version: "1.0.1"
  repository: https://github.com/codesphere-u/potemkin
---

# Potemkin — Expose Where Code Faked "Production Ready"

Never report a task, pull request, or application as complete until **Potemkin** verifies with deterministic AST and static checks that UI controls, error handlers, API routes, secrets, and tests are genuinely wired rather than cosmetic stubs.

## When to Run

- Before claiming any feature, bugfix, or codebase is "done" or "production ready"
- After rapid UI/API scaffolding or large AI-assisted edits
- Before merging a PR or tagging a release
- Whenever reviewing an unfamiliar or AI-generated codebase

## Mandatory Verification Workflow

### 1. Run the Deterministic Audit

Execute the bundled zero-dependency scanner from this skill's directory (for example, `.agents/skills/potemkin/scripts/potemkin.py` or `~/.claude/skills/potemkin/scripts/potemkin.py`), or via `uvx`:

```bash
# Full repository audit (JSON for structured triage, or text for readable output)
python3 <skill-dir>/scripts/potemkin.py . --format json

# Audit repository AND inspect git diff for AI reward hacking (.skip, suppressions, deleted assertions)
python3 <skill-dir>/scripts/potemkin.py . --diff HEAD --format text
```

For large legacy repositories adopting Potemkin incrementally, establish a baseline first and gate on regressions:

```bash
python3 <skill-dir>/scripts/potemkin.py . --write-baseline .potemkin-baseline.json
python3 <skill-dir>/scripts/potemkin.py . --diff HEAD --baseline .potemkin-baseline.json --fail-on high
```

> Load [references/rules.md](references/rules.md) when you need detailed rule definitions (`POT001`–`POT016`) or suppression rules.

### 2. Triage by Pillar (Never Guess)

Inspect every finding in priority order (`CRITICAL` -> `HIGH` -> `MEDIUM`):

1. **`ENV_TRUTH` (`POT011`–`POT013`)**: Hardcoded secret fallbacks (`JWT_SECRET || 'dev'`), secrets prefixed for client bundles (`NEXT_PUBLIC_`), and undocumented required env vars.
2. **`FAKE_FALLBACK` (`POT004`–`POT006`)**: `catch`/`except` blocks returning `MOCK_*`/demo data or fake `{ ok: true }`, broad silent `catch {}` / `except: pass`, and webhooks without HMAC verification.
3. **`MOCK_IN_PROD` (`POT007`)**: Fixture arrays, placeholder strings, or runtime `NotImplementedError` stubs in non-test directories.
4. **`HOLLOW_UI` (`POT001`–`POT003`)**: Empty/log-only/`alert()` JSX handlers, dead `href="#"` links, and fake `setTimeout` + `toast` form submissions.
5. **`WIRE_GAP` (`POT008`–`POT010`)**: Frontend `fetch`/`axios` calls to missing backend routes or wrong HTTP methods, orphan endpoints, and bare `localhost` URLs.
6. **`DIFF_CHEAT` (`POT014`–`POT016`)**: Newly added `.skip`, `pytest.mark.skip`, `@ts-ignore`, `# type: ignore`, `eslint-disable`, `--no-verify`, `|| true`, `assert True`, or net deleted test assertions.

### 3. Remediate Properly (Strict Anti-Cheat Rule)

> **CRITICAL:** Never resolve a Potemkin finding by silencing warnings with `potemkin-ignore`, adding `@ts-ignore` / `# type: ignore`, skipping tests, or swapping one fake fallback for another. Fix the underlying wiring, error handling, validation, or remove dead scaffolded controls/routes.

Consult [references/remediation.md](references/remediation.md) for concrete before/after patterns covering Next.js App Router, FastAPI, Express/Fastify, Stripe/webhook signature verification, startup env validation, and test restoration.

If an intentional exception genuinely applies (for example, a documented intentionally local CLI URL), add an inline justification only with explicit context:

```ts
// potemkin-ignore: POT010 - local dev CLI intentionally binds loopback
```

### 4. Re-Verify & Present Receipts

Re-run Potemkin alongside the repository's real test suite after fixing all `CRITICAL` and `HIGH` findings:

```bash
python3 <skill-dir>/scripts/potemkin.py . --diff HEAD --fail-on high
```

In your final response to the user, report:
- The observed **Potemkin Score (`0–100`) and Grade** (`VERIFIED` / `CAUTION` / `POTEMKIN ALERT`)
- Every resolved Potemkin finding (`rule_id` and `file:line`)
- Any remaining `MEDIUM` / suppressed findings with justification
