# PixelHoard CONTEXT — 词汇锁与项目基线

> 本文件是项目的"宪法"。所有 ADR、Domain Model、代码、文档出现歧义时,以此为准。
> 任何修改本文件的决策必须先经过烤问并升版(在 `## Version` 加一条)。

## Version

- **v1.0** (2026-09-09):初次建立。grill-with-docs 烤问 20 题,固化 83 条决策(D1-D83)。

---

## 1. 项目一句话

> **PixelHoard** = 基于华为云 OBS 的照片/视频/任意文件分享系统。
> 三种角色(管理员 / 用户 / 游客),所有分享行为以"分享(share)"为单位组织。

---

## 2. 词汇锁(Glossary 摘要)

完整 glossary 见 `docs/glossary/glossary.md`。核心 12 词:

| 术语 | 定义 |
|---|---|
| **Share** | 分享容器,顶层权限域。一个 share 拥有 N 个 file,挂 M 个 token,被 K 个 user_grant 授权 |
| **File** | 分享内的具体文件(图片/视频/任意)。物理存在 OBS,DB 仅存元数据 |
| **Token** | 短码(8 位 base62),绑定单一 share + 单一权限,游客凭此访问 |
| **UserGrant** | 登录用户被授权访问某 share 的关系,绑定 viewer / editor 角色 |
| **Slug** | share 的 URL 路径名,默认系统生成可改名 |
| **Public Note** | token 上对游客可见的留言字段 |
| **Label** | token 上对 owner 私有的管理备注 |
| **Display 档** | 浏览器可播的副本(原图直传 or 转码兜底)|
| **Preview 档** | 800px 宽中档预览图 |
| **Thumb 档** | 200px 宽缩略图 |
| **RAW 档** | 用户上传的原始文件,OBS 原样保存 |
| **Quota** | v1 暂无限额;预留表结构 |

---

## 3. 角色矩阵(详见 ADR-0001 §权限模型)

| 能力 | 游客+token(read) | 游客+token(readwrite) | 用户 viewer | 用户 editor | owner | admin |
|---|---|---|---|---|---|---|
| 浏览元数据 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 看文件列表 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 在线预览 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 单文件下载 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 整分享打包下载 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 看 EXIF | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 上传文件 | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| 删除文件 | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| 授权给其他用户 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 修改分享设置 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 删除整个分享 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 撤销 token | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 看全部 share | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 4. 技术栈(摘要,详见 ADR-0001)

| 层 | 选型 |
|---|---|
| 后端 | FastAPI(Python 3.11+) |
| 前端 | React + Vite + TypeScript + Tailwind v4 |
| DB | PostgreSQL + Redis |
| 对象存储 | 华为云 OBS(endpoint=obs.cn-central-221.ovaijisuan.com,bucket=obs-mushroom)|
| 视频处理 | ffprobe(仅探测,不重编码)|
| 图片处理 | Pillow + rawpy + dcraw |
| 上传 | 浏览器直传 OBS + Multipart 分片(>5MB)|
| 认证 | 邮箱 + 密码 + JWT |
| 部署 | Docker + Docker Compose,目标 ECS xj-ai-service(27.18.114.8,SSH 10332)|

---

## 5. 性能硬约束(详见 ADR-0002)

| # | 指标 | 目标 |
|---|---|---|
| P1 | 缩略图首屏 | < 800ms |
| P2 | 原图加载(20MB) | < 1.5s |
| P3 | 视频首帧 | < 1.5s |
| P4 | 视频起播流畅 | < 2.5s |
| P5 | 100 张缩略图瀑布流 | 0 CLS + 60fps |
| P6 | 视频 Range / 206 | 必须 |
| P7 | 缩略图懒加载 | 视口内 + 1 屏预读 |
| P8 | 浏览器直连 OBS | 必须 |
| P10 | 移动端 iOS+Android | 必须真机过 |
| P11 | 缩略图生成 | < 3s/张 |
| P12 | 衍生档生成(单张) | < 8s/张 |
| P13 | 预签名 URL 签发 | < 50ms |

---

## 6. 决策索引

> 决策索引(D1-D83)落在 `docs/domain/decision-log.md`,**不在 CONTEXT.md**。
> CONTEXT 只承载词汇锁。