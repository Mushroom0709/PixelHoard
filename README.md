# PixelHoard

> 基于华为云 OBS 的照片/视频/任意文件分享系统。
> 三种角色(管理员 / 用户 / 游客),所有分享行为以"分享(share)"为单位组织。

## 当前状态

- **v0.5 完成**(全部 ticket #1-#20 closed)
- 91/91 pytest 通过
- Web dist 190 KB JS / 62 KB gzip
- **v1.0 待部署验证**(ticket #21)

## 文档导航

| 文档 | 内容 |
|---|---|
| [docs/CONTEXT.md](docs/CONTEXT.md) | 词汇锁 + 项目基线 |
| [docs/glossary/glossary.md](docs/glossary/glossary.md) | 完整术语表 |
| [docs/domain/decision-log.md](docs/domain/decision-log.md) | D1-D83 决策原文 |
| [docs/adr/0001-stack-and-roles.md](docs/adr/0001-stack-and-roles.md) | 技术栈与权限模型 |
| [docs/adr/0002-performance-budgets.md](docs/adr/0002-performance-budgets.md) | 性能预算 P1-P16 |
| [docs/adr/0003-video-strategy.md](docs/adr/0003-video-strategy.md) | 视频原画直传 |
| [docs/adr/0004-upload-and-image-pipeline.md](docs/adr/0004-upload-and-image-pipeline.md) | 上传与图片衍生档 |
| [docs/adr/0005-domain-model.md](docs/adr/0005-domain-model.md) | PG schema |
| [docs/adr/0006-url-and-routing.md](docs/adr/0006-url-and-routing.md) | URL 与前端路由 |
| [docs/adr/0007-deployment.md](docs/adr/0007-deployment.md) | 部署拓扑 |
| [docs/deploy-runbook.md](docs/deploy-runbook.md) | 部署运行手册(逐步) |
| [docs/tickets-overview.md](docs/tickets-overview.md) | 21 ticket 总览 |
| [GitHub Issues](https://github.com/Mushroom0709/PixelHoard/issues) | 真源 issue tracker |

## 当前状态

- v0.0(规划完成)
- 0 代码,0 ticket
- 7 个 ADR 落盘
- 83 条决策固化

## 技术栈速览

| 层 | 选型 |
|---|---|
| 后端 | FastAPI(Python 3.11+) |
| 前端 | React + Vite + TS + Tailwind v4 |
| DB | PostgreSQL + Redis |
| 对象存储 | 华为云 OBS(obs-mushroom / PixelHoard/) |
| 部署 | Docker Compose → ECS xj-ai-service(27.18.114.8)|

## 下一步

1. 创建 `api/` + `web/` 目录骨架
2. ADR-0005 schema → SQLAlchemy models + alembic
3. ADR-0004 上传协议 → FastAPI 路由
4. ADR-0003 视频 ffprobe worker
5. ADR-0006 前端路由 + ShareView 组件
6. ADR-0007 部署到 ECS 验证 P1-P12

## License

GPL-3.0