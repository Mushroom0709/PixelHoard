#!/usr/bin/env bash
# test_local.sh — 本地/容器跑 pytest
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1
PYTHONPATH=. python3 -m pytest api/tests/ -v "$@"