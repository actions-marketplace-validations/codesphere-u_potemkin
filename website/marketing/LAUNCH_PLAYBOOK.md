# Potemkin v1.1.0 Launch Playbook

- **Primary URL**: https://codesphere-u.github.io/potemkin/
- **Positioning**: Deterministic Agent Skill & pure-stdlib CI gate that catches 16 real-code defects (`POT001`–`POT016`) before scaffolded PRs ship.
- **Core Proof Point**: `tests/fixtures/clean_app` (`100/100 VERIFIED`) vs `tests/fixtures/potemkin_app` (`0/100 POTEMKIN ALERT`, 17 caught defects) plus 100/100 self-audit on `potemkin`.
- **Distribution Channels**:
  - `npx skills add codesphere-u/potemkin` (Claude Code, Cursor, Antigravity, Codex)
  - GitHub Marketplace Action (`codesphere-u/potemkin@v1`) with SARIF 2.1.0 upload
  - Browser Studio (`https://codesphere-u.github.io/potemkin/studio.html`) for instant rule evaluation without local setup.
