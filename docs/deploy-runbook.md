# PixelHoard 部署运行手册

> 一份逐步指南,告诉部署 agent / 你怎么把 PixelHoard 推到 ECS xj-ai-service。

## 0. 前置条件

| 项目 | 值 |
|---|---|
| ECS | `27.18.114.8` (xj-ai-service) |
| SSH 端口 | `10332` (非默认 22)|
| 用户 | `root` |
| 密码 | 见 `.env` 的 `ECS_PASSWORD` |
| 部署目录 | `/home/workspace/PixelHoard` |
| 对外端口 | `10388` (唯一) |

## 1. 本地准备(Mac)

```bash
cd /Users/mushroom/Documents/ai/hermes/projects/PixelHoard

# 第一次:从模板生成 .env
cp .env.example .env
# 编辑 .env,确认 OBS_AK/SK/ENDPOINT 正确

# 加载 .env
set -a; source .env; set +a

# 验证 .env 必要字段
echo "OBS_AK=$OBS_AK"
echo "ECS_HOST=$ECS_HOST"
```

## 2. ECS 环境准备(由部署 agent 跑,SSH 上去)

```bash
sshpass -p "$ECS_PASSWORD" ssh -p 10332 -o StrictHostKeyChecking=no root@27.18.114.8
# 在 ECS 内:
bash <(curl -fsSL https://raw.githubusercontent.com/Mushroom0709/PixelHoard/main/scripts/setup_ecs.sh)
# 或者先把 setup_ecs.sh scp 上去再跑
```

预期输出:
```
✓ 10388 空闲
✓ docker ok
✓ .env 已生成 JWT_SECRET
```

## 3. 代码推送 + 部署(Mac 本地跑 deploy.sh)

```bash
cd /Users/mushroom/Documents/ai/hermes/projects/PixelHoard
bash scripts/deploy.sh
```

预期:
```
═══ PixelHoard deploy ═══
Target: root@27.18.114.8:10332 -> /home/workspace/PixelHoard
Public: http://27.18.114.8:10388

[1/6] 本地 docker compose config 检查… ✓
[2/6] scp src 到 ECS … ✓
[3/6] ECS 上 cp + 起容器… ✓ (containers Up)
[4/6] 验证 web… HTTP 200
[5/6] 验证 api… {"ok":true,...}
[6/6] dist hash 一致性… ✓
═══ deploy 完成 ═══
```

## 4. 端到端验证

```bash
bash scripts/verify.sh
```

期望:
- ✓ web HTTP 200
- ✓ api /api/health ok
- ✓ dist hash 一致
- ✓ OBS /api/obs-ping ok

## 5. 真机视觉验证(iPhone Safari)

1. iPhone 打开 Safari
2. 访问 `http://27.18.114.8:10388/`
3. 看到 "PixelHoard" 大字 + "API 健康 ✓ ok"

⚠️ HTTP 非 HTTPS,首次访问 Safari 会问"是否访问不安全网站",点"访问"即可。

## 6. 排错

### 容器起不来

```bash
ssh -p 10332 root@27.18.114.8
cd /home/workspace/PixelHoard
docker compose ps
docker compose logs api --tail=50
```

### OBS 不可达

```bash
docker exec pixelhoard-api curl http://localhost:8000/obs-ping
```

### web hash 不一致

说明 web 容器没拉到新 dist。强制 rebuild:
```bash
docker compose build web --no-cache
docker compose up -d web
```

## 7. 端口策略备忘

| 服务 | 端口 |
|---|---|
| nginx(对外) | **10388** ← 唯一对外 |
| api | 内网 8000 |
| web | 内网 80 |
| postgres | 内网 5432 |
| redis | 内网 6379 |
| worker | 无 |

**不要**在 `docker-compose.yml` 里把内部服务暴露到公网。