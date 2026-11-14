# CI Gate, SARIF & Remediation Guide

## GitHub Actions (`codesphere-u/potemkin@v1`)

```yaml
- name: Potemkin Real-Code Gate
  uses: codesphere-u/potemkin@v1
  with:
    path: "."
    diff: "origin/main"
    fail-on: "high"
    min-score: "90"
    sarif-file: "potemkin.sarif"
```

## Brownfield Baselines

Freeze legacy findings in `.potemkin-baseline.json` so only new regressions fail PRs:

```bash
potemkin . --write-baseline .potemkin-baseline.json
potemkin . --baseline .potemkin-baseline.json --fail-on high
```

See [skills/potemkin/references/rules.md](../skills/potemkin/references/rules.md) and [skills/potemkin/references/remediation.md](../skills/potemkin/references/remediation.md) for rule-by-rule remediation patterns.
