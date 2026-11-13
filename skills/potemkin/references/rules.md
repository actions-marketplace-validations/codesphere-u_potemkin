# Potemkin Rule Reference (`POT001`–`POT016`)

Potemkin computes a deterministic **Real-Code Score (`0–100`)** by deducting:
- `CRITICAL`: `-18` points (any critical finding caps grade below `VERIFIED`)
- `HIGH`: `-9` points
- `MEDIUM`: `-4` points
- `LOW`: `-1` point

Grades: `90–100` with `0 CRITICAL` = **VERIFIED** | `70–89` = **CAUTION** | `<70` = **POTEMKIN ALERT**.

---

## Pillar 1: `HOLLOW_UI` — Cosmetic Controls & Theater Forms

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `POT001` | High | `onClick`, `onSubmit`, `onChange`, `onPress` handlers with empty `{}`, `null`, `console.log(...)`, or `alert(...)` bodies | Ignores test/story files, `stopPropagation`/`preventDefault`, and JS comments |
| `POT002` | Medium | `<a href="#">`, `href=""`, or `to="#"` dead links in `.jsx/.tsx/.vue/.svelte` | Allows `#section-id` anchor slugs and SPA anchors that carry a real `onClick` handler |
| `POT003` | High | `handleSubmit` / `onSubmit` simulating completion via `setTimeout` + `toast`/`alert` | Skipped whenever handler invokes `fetch`, `axios`, `mutate`, `trpc`, `action`, `prisma`, or store actions |

## Pillar 2: `FAKE_FALLBACK` — Masked Failures & Unverified Webhooks

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `POT004` | Critical | `catch` / `except` returning mock/demo constants or fake `{ ok: true }` / `{ received: true }` | Ignores test/mock/seed paths |
| `POT005` | High | Empty JS `catch {}` or broad Python `except:` / `except Exception: pass` on multi-step blocks | Ignores cleanup blocks (`close`, `unlink`, `destroy`), commented `/* ignore */`, and narrow Python parse catches (`except ValueError: pass`) |
| `POT006` | Critical | Webhook routes accepting POSTs without verifying HMAC/signature headers | Recognizes `constructEvent`, `createHmac`, `timingSafeEqual`, `svix`, `stripe-signature`, `x-hub-signature`, `hmac.new`, `compare_digest` |

## Pillar 3: `MOCK_IN_PROD` — Fixtures & Stubs in Runtime Paths

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `POT007` | High | Runtime `MOCK_*`/`mockUsers` array/object literals, placeholder literals (`"Coming soon"`, `"test@example.com"`), and runtime `NotImplementedError` | Skips `tests/`, `__mocks__/`, `fixtures/`, `stories/`, `seeds/`, `docs/`, `migrations/`; Python AST ignores `NotImplementedError` inside `ABC` / `Protocol` / `@abstractmethod` |

## Pillar 4: `WIRE_GAP` — Disconnected Frontend ↔ Backend Contracts

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `POT008` | High | Frontend `fetch`/`axios` calls to `/api/...` routes absent from backend routes or with mismatched HTTP method | Only checks `/api/...` calls when backend routes exist; normalizes `:id`, `[id]`, `{id}`, `${expr}`, and dynamic route groups `(auth)` |
| `POT009` | Medium | Backend routes (Next.js App Router/Pages, Express/Fastify/Hono, FastAPI/Flask) with zero client or test references | Skips `/health*`, `/ready*`, `/metrics`, `/docs`, `/openapi.json`, `/api/auth*`, and webhooks; runs only when client callers exist |
| `POT010` | Medium | Bare `http://localhost:...` or `http://127.0.0.1:...` literals without env overrides | Ignores env fallback patterns (`process.env.X \|\|`, `os.getenv`), `config.dev`/`isDev`/`NODE_ENV` dev blocks, and config files (`vite.config`, `next.config`, `settings.py`, `config.py`) |

## Pillar 5: `ENV_TRUTH` — Secret Fallbacks & Configuration Drift

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `POT011` | Critical | Security-sensitive env vars (`JWT_SECRET`, `WEBHOOK_SECRET`, `PRIVATE_KEY`, etc.) defaulting to hardcoded strings | Matches fallback operators (`\|\|`, `??`, `os.getenv(..., "...")`) outside tests |
| `POT012` | Critical | Sensitive variable names (`SECRET`, `PRIVATE`, `PASSWORD`, `DATABASE_URL`, etc.) exposed under client prefixes (`NEXT_PUBLIC_`, `VITE_`, etc.) | Allows explicitly public tokens (`PUBLISHABLE`, `ANON_KEY`, `API_URL`, `LIVEKIT_URL`) |
| `POT013` | Medium | Required env vars read via `os.environ["X"]` or unguarded `process.env.X` missing from `.env.example` / `.env.sample` / `.env.template` | Runs only when an env template exists; ignores `os.environ["X"] = ...` writes, optional `.get()` / guarded `\|\|` checks, and standard OS/CI vars (`PORT`, `NODE_ENV`, `GITHUB_*`, `VERCEL_*`) |

## Pillar 6: `DIFF_CHEAT` — Git Diff Anti-Reward-Hacking (`--diff` / `--staged`)

| Rule | Severity | What It Catches | False-Positive Guards |
| :--- | :--- | :--- | :--- |
| `POT014` | Critical | Newly added `.skip`, `.only`, `xit`, `xdescribe`, `@pytest.mark.skip`, `@unittest.skip`, `@pytest.mark.xfail`, `t.Skip` | Inspects only added `+` diff lines |
| `POT015` | High | Newly added `@ts-ignore`, `@ts-nocheck`, `as any`, `# type: ignore`, `# noqa`, `eslint-disable`, `--no-verify`, `\|\| true` | Skips Markdown/docs files |
| `POT016` | High | Trivial assertions (`assert True`, `expect(true).toBe(true)`) or test files removing `>=2` assertions without equivalent replacements | Counts net assertion lines across modified test files |

---

## Configuration & Suppressions

### Inline Suppression

```python
LOCAL_TEST_ENDPOINT = "http://127.0.0.1:9000"  # potemkin-ignore: POT010 - local daemon IPC only
```

```ts
// potemkin-ignore: POT005 - socket close on teardown is intentionally non-fatal
try { socket.destroy(); } catch {}
```

### `.potemkinignore`

Works like `.gitignore` (supports prefixes and globs):

```text
legacy-prototype/
packages/demo-sandbox/*.tsx
```

### `.potemkin.json`

```json
{
  "exclude": ["legacy-v1"],
  "ignoreRules": ["POT009"],
  "envDrift": true,
  "orphanRoutes": true
}
```
