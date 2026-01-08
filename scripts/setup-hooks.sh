#!/bin/bash
# Installs git hooks for local development
# Run once after cloning: ./scripts/setup-hooks.sh
set -e

echo "Setting up git hooks..."

mkdir -p .git/hooks

cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
./scripts/validation/check.sh
EOF

chmod +x .git/hooks/pre-commit

echo "Pre-commit hook installed"
