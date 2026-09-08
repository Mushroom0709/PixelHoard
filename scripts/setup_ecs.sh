#!/usr/bin/env bash
# setup_ecs.sh — ECS 环境准备(由部署 agent 跑,不是本地 Mac)
# 在 ECS 上跑:bash setup_ecs.sh
set -euo pipefail

DEPLOY_DIR="${ECS_DEPLOY_DIR:-/home/workspace/PixelHoard}"
PUBLIC_PORT="${PUBLIC_PORT:-10388}"

echo "═══ PixelHoard ECS setup ═══"
echo "DEPLOY_DIR=$DEPLOY_DIR"
echo "PUBLIC_PORT=$PUBLIC_PORT"

# 0. 必备工具
echo "[0/6] 检查工具链…"
for cmd in docker python3.11 ffmpeg curl ss; do
  command -v "$cmd" >/dev/null || {
    echo "  ⚠ $cmd 未安装,尝试 apt 安装"
    apt-get install -y "$cmd" || true
  }
done

# 1. 部署目录
echo "[1/6] 创建部署目录…"
mkdir -p "$DEPLOY_DIR"/{api,web,nginx,scripts,logs}

# 2. 端口占用检查
echo "[2/6] 端口 $PUBLIC_PORT 检查…"
if ss -tln | grep -q ":$PUBLIC_PORT "; then
  echo "  ⚠ 端口 $PUBLIC_PORT 已被占用,详情:"
  ss -tlnp | grep ":$PUBLIC_PORT "
  echo "  请确认该进程是否可停,或修改 PUBLIC_PORT"
else
  echo "  ✓ $PUBLIC_PORT 空闲"
fi

# 3. Docker 守护
echo "[3/6] Docker daemon…"
systemctl is-active docker >/dev/null 2>&1 || systemctl start docker
docker version >/dev/null && echo "  ✓ docker ok"

# 4. 旧容器清理(若存在)
echo "[4/6] 旧容器清理…"
cd "$DEPLOY_DIR"
docker compose down 2>/dev/null || true
docker rm -f pixelhoard-api pixelhoard-web pixelhoard-postgres pixelhoard-redis pixelhoard-worker pixelhoard-nginx 2>/dev/null || true
echo "  ✓"

# 5. .env 准备
echo "[5/6] .env 配置…"
if [ ! -f .env ]; then
  echo "  ⚠ 未找到 .env,从 .env.example 拷贝 + 生成密钥"
  cp .env.example .env
  NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  sed -i.bak "s|^JWT_SECRET=.*|JWT_SECRET=$NEW_SECRET|" .env
  rm -f .env.bak
  echo "  ✓ 已生成新 JWT_SECRET"
else
  echo "  ✓ .env 存在"
fi

# 6. 完成
echo "[6/6] 完成 ✓"
echo ""
echo "下一步:本地 Mac 跑 scripts/deploy.sh 推送代码 + 构建 + 起容器"
echo "或:本地手动 scp 到 $DEPLOY_DIR,然后 docker compose up -d"