#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLED_DEPS="${BUNDLED_DEPS:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies}"

export PATH="$BUNDLED_DEPS/node/bin:$BUNDLED_DEPS/bin:$PATH"

cd "$ROOT/frontend"
pnpm --config.dangerouslyAllowAllBuilds=true install --no-frozen-lockfile
pnpm build
pnpm lint

