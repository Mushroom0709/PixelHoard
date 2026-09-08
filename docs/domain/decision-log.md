# PixelHoard Decision Log

> 所有 83 条决策的原文记录(D1-D83)。每条决策在烤问时被固化,在 ADR 中被引用。
> 任何修改都需要重新烤问 + 更新 ADR 版本号。

---

## D1-D12 — 角色与权限模型

| # | 决策 |
|---|---|
| **D1** | 权限粒度 = **一个 share**(容器级,无资源级覆写)|
| **D2** | 权限种类(对游客而言) = `read` / `readwrite` 两级 |
| **D3** | 角色模型 = `admin` / `user` / `guest` 三层 |
| **D4** | 创建 share 默认权限 = `readwrite` 给本人(owner 永远可写)|
| **D5** | 用户拖入文件到 share |
| **D6** | 分享码(access token)的权限 = **码本身的属性**,不是查询时分配 |
| **D7** | 游客只能只读,且必须有 token |
| **D8** | 一个 share = 一个权限域 |
| **D9** | 一个 share 可发多个 token,每个绑定固定权限 |
| **D10** | Token 形态 = 短码 8 位 base62,可选 expiry / revoke / label |
| **D11** | URL 形式 = `https://{host}/s/{slug}?t={token}` 或 `/s/{slug}/{token}`(v1 选其一,在 ADR-0006 中定)|
| **D12** | 游客 = 纯无状态,token 是唯一凭证 |

## D13-D22 — 游客与 token

| # | 决策 |
|---|---|
| **D13** | 服务端**不持久化游客信息** |
| **D14** | 游客不能收藏 / 转存 |
| **D15** | 游客可:在线浏览、预览、单文件下载、批量下载、看 EXIF |
| **D16** | D15 能力不跟 token 权限走,只要 token 有效 |
| **D17** | Token 权限(read/readwrite)只区分"能否上传/删除文件",不影响下载 |
| **D18** | D17 简化:游客永远是"只读 + 可下载";"读写权限 token"本质是"用户视角的管理权限"|
| **D19** | Token 可独立撤销 |
| **D20** | Token 可设 `expires_at`(可选)|
| **D21** | token 字段 = `id, share_id, token_code, permission, expires_at, revoked_at, created_at, last_used_at, label, public_note` |
| **D22** | 过期 = 后台查询直接拒(不删数据);撤销 = 立即失效 |

## D23-D28 — 删除语义

| # | 决策 |
|---|---|
| **D23** | 删 share = **硬删**:DB + 所有 token + 所有 file + OBS prefix 全清 |
| **D24** | 删除前**弹一次确认**(防误操作;你需求里没明说但工程常识)|
| **D25** | OBS prefix = `obs://obs-mushroom/PixelHoard/shares/{share_id}/...` |
| **D26** | 删除 = 不可逆 |
| **D27** | 后端 FastAPI(Python 3.11+) |
| **D28** | 前端 React + Vite + TS + Tailwind v4 |

## D29-D32 — 技术栈

| # | 决策 |
|---|---|
| **D29** | DB = PostgreSQL(主)+ Redis(token 限流 + 临时缓存) |
| **D30** | 对象存储 = OBS |
| **D31** | 视频处理 = FFprobe(仅探测)+ FastAPI BackgroundTasks |
| **D32** | 图片处理 = Pillow + rawpy + dcraw |

## D33-D44 — 视频与图片策略

| # | 决策 |
|---|---|
| **D33** | **原画直传**:服务端不重编码,OBS 存什么就播放什么 |
| **D34** | 服务端仅 ffprobe 探测(分辨率/时长/编码/旋转角)|
| **D35** | 前端用原生 `<video>` + HTTP Range / 206,直连 OBS 预签名 URL |
| **D36** | 不兼容格式 = 提示"请下载观看"(绝不偷偷转码) |
| **D37** | 不做 HLS / ABR / 切片,v2+ 再说 |
| **D38** | 前端按 codec 选播放器(主要靠浏览器原生 + 不可播时降级)|
| **D39** | 浏览器原生支持格式(JPG/PNG/WebP/GIF/AVIF/HEIC/HEIF)→ 直传原图作 display 档 |
| **D40** | 浏览器不支持格式(ARW/CR2/NEF/DNG 等)→ 必须生成 display 档(JPEG/WebP 95% 保 EXIF)|
| **D41** | 全部上传 → 必须生成 thumb(200px) + preview(800px) |
| **D42** | Display 档自适应判定 = `image_probe.py`,上传后立即 sniff |
| **D43** | 原图 + 衍生档全部进 OBS |
| **D44** | 衍生档异步生成,不影响上传主流程 |

## D45-D49 — 上传策略

| # | 决策 |
|---|---|
| **D45** | 上传 = 浏览器直传 OBS(后端零代理)|
| **D46** | 大文件(>5MB)走 OBS Multipart 分片 |
| **D47** | 后端只签 URL + 写 file row + 触发衍生档生成 |
| **D48** | 断点续传 = Multipart Init 后每 part 独立重试 + IndexedDB 缓存 part 进度 |
| **D49** | 进度反馈 = XHR `upload.onprogress` 直读 OBS 响应 |

## D50-D54 — 分享可见性

| # | 决策 |
|---|---|
| **D50** | 每个 share 必须挂 owner_id |
| **D51** | 用户列表 = `WHERE owner_id = me OR id IN (shares_granted_to_me)` |
| **D52** | 管理员可见全部 share + 全部 user |
| **D53** | 授权粒度 = share 级 |
| **D54** | 授权方式 = 显式(owner 手动加用户 + 角色)|

## D55-D57 — Token label 策略

| # | 决策 |
|---|---|
| **D55** | token 字段新增 `label`(owner 私有)+ `public_note`(游客可见)|
| **D56** | 游客页访问时,public_note 非空才展示 |
| **D57** | 游客永远看不到 label / token 创建时间 / 撤销按钮 / token 列表 |

## D58-D60 — Slug 策略

| # | 决策 |
|---|---|
| **D58** | 默认系统生成 8 位 base62 slug |
| **D59** | 用户改名时校验 `^[a-z0-9-]{3,32}$`,大小写不敏感,全局唯一 |
| **D60** | 冲突返回 409,前端提示"该名称已被占用" |

## D61-D63 — Quota

| # | 决策 |
|---|---|
| **D61** | v1 不设硬上限 |
| **D62** | 保留 quota 表结构,admin 后台可配 |
| **D63** | 唯一硬约束 = OBS 总用量监控 + 阈值告警 |

## D64-D67 — 登录

| # | 决策 |
|---|---|
| **D64** | 登录 = 邮箱 + 密码 |
| **D65** | 注册不强制邮箱验证,banner 提示 |
| **D66** | 密码 bcrypt,Session = JWT |
| **D67** | OAuth = v2 |

## D68-D72 — 移动端

| # | 决策 |
|---|---|
| **D68** | 手机端用户上传 = v1 必须 |
| **D69** | 游客手机仅浏览/预览/下载单文件 |
| **D70** | 批量下载 v1 后置 |
| **D71** | 移动端上传 = `<input type="file" capture="environment">` |
| **D72** | 移动端验证 = iOS Safari + Android Chrome 真机 |

## D73-D76 — 审计

| # | 决策 |
|---|---|
| **D73** | 审计保留 = 30 天 |
| **D74** | 记录事件 = 登录/登出/创建-删除 share/生-撤 token/上-删文件/授权变更/admin 操作 |
| **D75** | 字段 = `id, user_id, share_id, action, target_type, target_id, ip, ua, occurred_at` |
| **D76** | 30 天后 cron 删 DB 行 |

## D77-D79 — 备份

| # | 决策 |
|---|---|
| **D77** | OBS 桶开 versioning |
| **D78** | 用户主动删时**绕过 versioning** |
| **D79** | versioning 只防系统层误操作 |

## D80-D83 — 部署

| # | 决策 |
|---|---|
| **D80** | 部署目标 = ECS xj-ai-service(27.18.114.8, SSH 10332)|
| **D81** | 业务端口 = 10333–10400 |
| **D82** | 本地 Mac 只开发调试 |
| **D83** | 容器化 = Docker + Compose(api / web / worker)|