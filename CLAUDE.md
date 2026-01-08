# MCP Server Development Guidelines

## Code Quality Rules

**MANDATORY**: Before presenting ANY code:

1. Run `./scripts/validation/check.sh`
2. If validation fails, fix and re-run (max 3 attempts)
3. NEVER present code that hasn't passed validation

## Commands

```bash
# Full validation (same as CI)
./scripts/validation/check.sh

# Individual commands
bun run lint        # ESLint + Prettier
bun run typecheck   # TypeScript
bun run test        # Bun native tests
bun run build       # Production build
```

## Git Workflow

- Work on feature branches
- Run `./scripts/setup-hooks.sh` after cloning (installs pre-commit hook)
- Use conventional commits for automatic releases:
  - `feat:` minor version bump
  - `fix:` patch version bump
  - `feat!:` or `BREAKING CHANGE:` major version bump
