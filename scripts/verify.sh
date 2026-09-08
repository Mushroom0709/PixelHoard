#!/usr/bin/env bash
# verify.sh — 部署后端到端验证
set -euo pipefail

PUBLIC_HOST="${PUBLIC_HOST:-27.18.114.8}"
PUBLIC_PORT="${PUBLIC_PORT:-10388}"
BASE="http://${PUBLIC_HOST}:${PUBLIC_PORT}"
SSH="${SSH:-sshpass -p kU2hVZdxaT4GBW8b ssh -p 10332 -o StrictHostKeyChecking=no root@${PUBLIC_HOST}}"

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
echo "[1/6] web (/)"
WEB_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
check "web HTTP" "200" "$WEB_CODE"

# 2. api /api/health
echo ""
echo "[2/6] api (/api/health)"
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
echo "[3/6] dist hash"
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

# 4. api /api/version
echo ""
echo "[4/6] api (/api/version)"
VERSION=$(curl -s "$BASE/api/version")
echo "  response: $VERSION"
if echo "$VERSION" | grep -q '"ok":true'; then
  echo "  ✓ api version ok"
  pass=$((pass+1))
else
  echo "  ✗ api version not ok"
  fail=$((fail+1))
fi

# 5. api /api/obs-ping
echo ""
echo "[5/6] obs 连通 (/api/obs-ping)"
OBS=$(curl -s "$BASE/api/obs-ping")
echo "  response: $OBS"
if echo "$OBS" | grep -q '"ok":true'; then
  echo "  ✓ OBS 通"
  pass=$((pass+1))
else
  echo "  ⚠ OBS 不可达(可能是凭据问题)"
  fail=$((fail+1))
fi

# 6. DB schema — 7 张表都应存在
echo ""
echo "[6/6] DB schema (7 张表)"
DB_TABLES=$(eval "$SSH" 'docker exec pixelhoard-postgres psql -U pixelhoard -d pixelhoard -tA -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='\''public'\'' AND table_name IN ('\''users'\'','\''shares'\'','\''share_tokens'\'','\''user_grants'\'','\''files'\'','\''audit_logs'\'','\''quota_configs'\'');"' 2>/dev/null || echo "0")
if [ "$DB_TABLES" = "7" ]; then
  echo "  ✓ 7 表齐"
  pass=$((pass+1))
else
  echo "  ✗ DB 表数: $DB_TABLES (期望 7)"
  fail=$((fail+1))
fi

echo ""
echo "═══ summary ═══"
echo "  pass: $pass"
echo "  fail: $fail"
[ "$fail" -eq 0 ] && exit 0 || exit 1