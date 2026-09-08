#!/usr/bin/env bash
# verify.sh — 部署后端到端验证
set -euo pipefail

PUBLIC_HOST="${PUBLIC_HOST:-27.18.114.8}"
PUBLIC_PORT="${PUBLIC_PORT:-10388}"
BASE="http://${PUBLIC_HOST}:${PUBLIC_PORT}"

echo "═══ PixelHoard verify ═══"
echo "Target: $BASE"
echo ""

pass=0
fail=0

check() {
  local name="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✓ $name ($actual)"
    pass=$((pass+1))
  else
    echo "  ✗ $name expected=$expected got=$actual"
    fail=$((fail+1))
  fi
}

# 1. web 200
echo "[1/4] web (/)"
WEB_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
check "web HTTP" "200" "$WEB_CODE"

# 2. api /api/health
echo ""
echo "[2/4] api (/api/health)"
HEALTH=$(curl -s "$BASE/api/health")
echo "  response: $HEALTH"
if echo "$HEALTH" | grep -q '"ok":true'; then
  echo "  ✓ api ok"
  pass=$((pass+1))
else
  echo "  ✗ api not ok"
  fail=$((fail+1))
fi

# 3. dist hash 一致
echo ""
echo "[3/4] dist hash"
REMOTE_HASH=$(curl -s "$BASE/" | grep -oE 'index-[A-Za-z0-9_-]+\.js' | head -1)
LOCAL_HASH=$(ls web/dist/assets/index-*.js 2>/dev/null | head -1 | xargs basename)
echo "  remote: $REMOTE_HASH"
echo "  local : $LOCAL_HASH"
if [ -n "$REMOTE_HASH" ] && [ "$REMOTE_HASH" = "$LOCAL_HASH" ]; then
  echo "  ✓ 一致"
  pass=$((pass+1))
else
  echo "  ⚠ 不一致(可能是缓存,强制刷新)"
  fail=$((fail+1))
fi

# 4. api /api/obs-ping(OBS 连通)
echo ""
echo "[4/4] obs 连通 (/api/obs-ping)"
OBS=$(curl -s "$BASE/api/obs-ping")
echo "  response: $OBS"
if echo "$OBS" | grep -q '"ok":true'; then
  echo "  ✓ OBS 通"
  pass=$((pass+1))
else
  echo "  ⚠ OBS 不可达(可能是凭据问题)"
  fail=$((fail+1))
fi

echo ""
echo "═══ summary ═══"
echo "  pass: $pass"
echo "  fail: $fail"
[ "$fail" -eq 0 ] && exit 0 || exit 1