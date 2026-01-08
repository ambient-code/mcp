#!/bin/bash
# Security scanning for secrets and sensitive data
# Used by: CI workflow (runs in parallel with validation)
set -e

echo "-> Scanning for hardcoded secrets..."
if grep -rE '(api_key|secret|password|token)\s*[:=]\s*["\x27][A-Za-z0-9+/]{20,}' src/ 2>/dev/null; then
    echo "ERROR: Potential secrets found in code"
    exit 1
fi
echo "No secrets detected"

echo "-> Checking for credential URLs..."
if grep -rE 'https?://[^:]+:[^@]+@' src/ 2>/dev/null; then
    echo "ERROR: URLs with embedded credentials found"
    exit 1
fi
echo "No credential URLs detected"

echo "-> Verifying no .env files tracked in git..."
if git ls-files | grep -E '^\.env' | grep -v '.env.example' | grep -q .; then
    echo "ERROR: .env files should not be committed"
    exit 1
fi
echo "No .env files tracked"

echo "Security scan passed"
