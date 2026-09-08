# PixelHoard v0.1 Bootstrap — Ticket Overview

> 来源:grill-with-docs 烤问(20 题, 83 决策)+ to-tickets skill
> 真源:GitHub Issues https://github.com/Mushroom0709/PixelHoard/issues
> 本目录:本地 mirror(便于离线审阅)
> 共 21 个 ticket,3 个 milestone

## Milestone 划分

| Milestone | Ticket 范围 | 范围说明 |
|---|---|---|
| **v0.1** | #1–#6 | 基建 + 认证 — 能跑起来、能注册登录 |
| **v0.5** | #1–#13 | + Share 核心 + UserGrant — 完整权限模型 |
| **v1.0** | #1–#21 | + 上传 + 视频 + 治理 + 部署 — 可上生产 |

## 阻塞关系图(按 ticket #)

```
#1 → #2, #3
#3 → #4
#4 → #5, #8, #14
#5 → #6
#6 → #7
#8 → #9, #10
#9 → #11, #12, #14
#10 → #11
#12 → #13
#14 → #15
#15 → #16
#16 → #17, #19, #20
#17 → #18
#21 阻塞全部
```

## Phase 分布

| Phase | Tickets |
|---|---|
| Phase 0 基建 | #1 #2 #3 #4 |
| Phase 1 认证 | #5 #6 #7 |
| Phase 2 Share 核心 | #8 #9 #10 #11 |
| Phase 3 UserGrant | #12 #13 |
| Phase 4 上传 | #14 #15 #16 #17 #18 |
| Phase 5 视频/治理/上线 | #19 #20 #21 |

## Ticket 列表

| # | 标题 | Phase | 类别 | 阻塞 |
|---|---|---|---|---|
| #1 | 01 Repo骨架 + docker-compose 拉空 web/api/postgres/redis | Phase 0 | infra | — |
| #2 | 02 FastAPI + Vite hello 联调 | Phase 0 | infra | #1 |
| #3 | 03 PG schema + alembic init + 首版 migration | Phase 0 | infra | #1 |
| #4 | 04 SQLAlchemy models + Pydantic schemas 骨架 | Phase 0 | infra | #3 |
| #5 | 05 注册:邮箱密码 → bcrypt 写入 users | Phase 1 | auth | #4 |
| #6 | 06 登录:JWT 签发 + middleware 校验 | Phase 1 | auth | #5 |
| #7 | 07 退出 / refresh token / is_admin flag | Phase 1 | auth | #6 |
| #8 | 08 创建 share + 自动生成 slug + 列在我的 share | Phase 2 | share | #4 |
| #9 | 09 share 详情页 + owner 视角权限 | Phase 2 | share | #8 |
| #10 | 10 Token CRUD(生成短码 + 列表 + 撤销) | Phase 2 | share | #8 |
| #11 | 11 游客访问 /s/{slug}/{token} 端到端 | Phase 2 | share | #9 / #10 |
| #12 | 12 UserGrant 创建/列表/撤销(grant UI) | Phase 3 | grant | #9 |
| #13 | 13 被授权用户访问 + viewer/editor 区分 | Phase 3 | grant | #12 |
| #14 | 14 POST /upload-init → 签 OBS Multipart 预签名 | Phase 4 | upload | #4 / #9 |
| #15 | 15 前端 Multipart 分片上传 + 进度 + 重试 | Phase 4 | upload | #14 |
| #16 | 16 POST /upload-complete + DB 写 file row(processing) | Phase 4 | upload | #15 |
| #17 | 17 Worker thumb(200) + preview(800) 生成 | Phase 4 | upload | #16 |
| #18 | 18 ARW/HEIC 兜底 display 档 + 原图策略 | Phase 4 | upload | #17 |
| #19 | 19 视频 ffprobe + moov 校验 + UI 提示 | Phase 5 | video | #16 |
| #20 | 20 删 share(DB + OBS prefix 硬删) + 审计打点 | Phase 5 | governance | #11 / #16 |
| #21 | 21 ECS 部署(避开 10333)+ iPhone 真机 P1-P12 验收 | Phase 5 | deploy | #1 / #2 / #3 / #4 / #5 / #6 / #7 / #8 / #9 / #10 / #11 / #12 / #13 / #14 / #15 / #16 / #17 / #18 / #19 / #20 |
