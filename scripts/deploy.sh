#!/usr/bin/env bash
# deploy.sh — Mac 本地 → ECS 部署
# 由你或部署 agent 在 Mac 上跑
set -euo pipefail

# 1. 加载 .env
if [ -f .env ]; then
  set -a; source .env; set +a
else
  echo "✗ .env 不存在,请 cp .env.example .env 并填好 OBS 凭证" >&2
  exit 1
fi

: "${ECS_HOST:?ECS_HOST not set}"
: "${ECS_SSH_PORT:=10332}"
: "${ECS_USER:=root}"
: "${ECS_PASSWORD:?ECS_PASSWORD not set}"
: "${ECS_DEPLOY_DIR:=/home/workspace/PixelHoard}"
: "${PUBLIC_PORT:=10388}"

REMOTE="${ECS_USER}@${ECS_HOST}"
SCRATCH="/tmp/PixelHoard-deploy-$$"

echo "═══ PixelHoard deploy ═══"
echo "Target: $REMOTE:$ECS_SSH_PORT -> $ECS_DEPLOY_DIR"
echo "Public: http://${ECS_HOST}:${PUBLIC_PORT}"

# 2. 检查本地 docker compose
echo ""
echo "[1/6] 本地 docker compose config 检查…"
docker compose config -q && echo "  ✓ compose config ok"

# 3. scp 代码到 ECS /tmp
echo ""
echo "[2/6] scp src 到 ECS $SCRATCH …"
sshpass -p "$ECS_PASSWORD" ssh -p "$ECS_SSH_PORT" -o StrictHostKeyChecking=no "$REMOTE" "rm -rf $SCRATCH && mkdir -p $SCRATCH"
sshpass -p "$ECS_PASSWORD" scp -P "$ECS_SSH_PORT" -o StrictHostKeyChecking=no \
  docker-compose.yml \
  nginx \
  api \
  web \
  scripts \
  "$REMOTE:$SCRATCH/"

# 4. ECS 上 cp + 起容器
echo ""
echo "[3/6] ECS 上 cp + 起容器…"
sshpass -p "$ECS_PASSWORD" ssh -p "$ECS_SSH_PORT" -o StrictHostKeyChecking=no "$REMOTE" << EOF
  set -e
  cd $ECS_DEPLOY_DIR
  # 强制覆盖式 cp(skill 经验:rm -f + cp -rf)
  rm -rf api web nginx scripts docker-compose.yml
  cp -rf $SCRATCH/* .
  ls -la
  echo "--- docker compose build ---"
  docker compose build api web
  echo "--- docker compose up ---"
  docker compose up -d
  sleep 5
  echo "--- docker compose ps ---"
  docker compose ps
EOF

# 5. 验证 web
echo ""
echo "[4/6] 验证 web (http://${ECS_HOST}:${PUBLIC_PORT}/)…"
sleep 3
HTTP_CODE=$(curl -s -o /tmp/deploy_web.html -w "%{http_code}" "http://${ECS_HOST}:${PUBLIC_PORT}/" || echo "000")
echo "  HTTP $HTTP_CODE"
if [ "$HTTP_CODE" != "200" ]; then
  echo "  ✗ web 不可达,看 /tmp/deploy_web.html:"
  cat /tmp/deploy_web.html
  exit 1
fi

# 6. 验证 api
echo ""
echo "[5/6] 验证 api (http://${ECS_HOST}:${PUBLIC_PORT}/api/health)…"
curl -s "http://${ECS_HOST}:${PUBLIC_PORT}/api/health" | tee /tmp/deploy_api_health.json
echo ""

# 7. dist hash 一致性
echo ""
echo "[6/6] dist hash 一致性检查…"
REMOTE_HASH=$(curl -s "http://${ECS_HOST}:${PUBLIC_PORT}/" | grep -oE 'index-[A-Za-z0-9_-]+\.js' | head -1)
LOCAL_HASH=$(ls web/dist/assets/index-*.js 2>/dev/null | head -1 | xargs basename)
echo "  remote: $REMOTE_HASH"
echo "  local : $LOCAL_HASH"
if [ -n "$REMOTE_HASH" ] && [ "$REMOTE_HASH" = "$LOCAL_HASH" ]; then
  echo "  ✓ hash 一致"
else
  echo "  ⚠ hash 不一致,需重新 docker compose build web"
fi

echo ""
echo "═══ deploy 完成 ═══"
echo "访问: http://${ECS_HOST}:${PUBLIC_PORT}/"