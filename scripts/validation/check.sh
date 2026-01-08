#!/bin/bash
# Runs all validation checks: lint, typecheck, test, build
# Used by: pre-commit hook, CI workflow
set -e

echo "-> Linting..."
bun run lint

echo "-> Type checking..."
bun run typecheck

echo "-> Testing..."
bun run test

echo "-> Building..."
bun run build

echo "All checks passed"
