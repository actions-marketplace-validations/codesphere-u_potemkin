# Getting Started with Potemkin

Potemkin verifies whether an application works end-to-end or only looks finished on the surface. It ships with zero runtime dependencies on Python 3.10+.

## Install Options

- **Agent Skill**: `npx skills add codesphere-u/potemkin`
- **Ephemeral CLI (`uvx`)**: `uvx --from git+https://github.com/codesphere-u/potemkin potemkin . --diff HEAD`
- **Local Python Package**: `pip install git+https://github.com/codesphere-u/potemkin.git`

## First Run

```bash
potemkin . --diff HEAD --fail-on high --min-score 90
```

Try the interactive browser scanner at [https://codesphere-u.github.io/potemkin/studio.html](https://codesphere-u.github.io/potemkin/studio.html).
