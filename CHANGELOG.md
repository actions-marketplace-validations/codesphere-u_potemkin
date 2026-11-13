# Changelog

All notable changes to **Potemkin** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-14

### Added
- **Deterministic Verification Engine (`skills/potemkin/scripts/potemkin.py`):** Zero-dependency Python 3.10+ stdlib scanner computing a `0–100` Real-Code Score (`VERIFIED`, `CAUTION`, `POTEMKIN ALERT`) across 6 pillars and 16 rules (`POT001`–`POT016`):
  - `HOLLOW_UI` (`POT001`–`POT003`): Empty/`console.log`/`alert` handlers, dead `href="#"` links, and fake `setTimeout` + `toast` form submissions.
  - `FAKE_FALLBACK` (`POT004`–`POT006`): `catch`/`except` blocks returning mock/demo constants or fake success, broad silent `catch {}`/`except Exception: pass`, and webhooks missing HMAC signature verification.
  - `MOCK_IN_PROD` (`POT007`): Runtime fixture arrays, placeholder strings (`test@example.com`, `Coming soon`), and `raise NotImplementedError` outside ABCs/abstract methods.
  - `WIRE_GAP` (`POT008`–`POT010`): Cross-language frontend `fetch`/`axios` to backend route graph (`Next.js` App/Pages, `Express`/`Fastify`/`Hono`, `FastAPI`/`Flask`), orphan routes, and bare `localhost` literals.
  - `ENV_TRUTH` (`POT011`–`POT013`): Hardcoded secret fallbacks (`JWT_SECRET || 'dev'`), secrets leaked under `NEXT_PUBLIC_`/`VITE_`/`PUBLIC_` client prefixes, and required runtime env vars missing from `.env.example`.
  - `DIFF_CHEAT` (`POT014`–`POT016`): Git diff audit (`--diff`, `--staged`) detecting newly added `.skip`/`pytest.mark.skip`, `@ts-ignore`/`# type: ignore`/`eslint-disable`/`|| true`, and trivial or net-deleted test assertions.
- **Agent Skill Package (`skills/potemkin/`):** `SKILL.md` workflow specification, rule catalog (`references/rules.md`), framework remediation playbooks (`references/remediation.md`), and Claude Code plugin manifests (`.claude-plugin/`).
- **CLI, CI & Container Distribution:** `pyproject.toml` console entrypoint (`potemkin`), SARIF 2.1.0 / JSON / Markdown / Text formatters, fingerprint baselines (`--write-baseline` / `--baseline`), `.potemkinignore` and `.potemkin.json` configuration, GitHub Composite Action (`action.yml`), and non-root `Dockerfile`.
- **Fixture & Test Suite:** Full `clean_app` (`100/100 VERIFIED`) and `potemkin_app` (`0/100 POTEMKIN ALERT`) full-stack benchmarks plus unit/integration tests covering false-positive guards and git diff reward hacking.
