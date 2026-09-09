# CONTEXT · PixelHoard

> 一句话定位:本文件是 PixelHoard 项目的**词汇表**,任何 ADR / ticket / 代码出现歧义时,以此处的术语定义为准。

---

## 1. 项目一句话

> 基于华为云 OBS 的照片/视频/任意文件分享系统。
> 三种角色(管理员 / 用户 / 游客),所有分享行为以"分享(share)"为单位组织。

---

## 2. 角色类

### Admin(管理员)

- **类别**:项目层(顶层角色)
- **定义**:系统管理员账号,可看全部 share / user,可做任何 owner 能做的事
- **使用场景**:`docs/adr/0001-stack-and-roles.md §权限模型` 的 admin 行;后台 `/admin/*` 路由
- **不是**:User(普通用户,看不见全部 share);Owner(单 share 的创建者,无跨 share 权限)
- **边界**:admin 仍受单 share ACL 校验,但其 `is_admin=true` 跳过 owner 校验

### User(用户)

- **类别**:项目层
- **定义**:注册登录用户,可创建 share、可被授权访问别人的 share
- **使用场景**:注册/登录流程;`/shares` 我的分享列表;ticket #5-#7
- **不是**:Admin(无权看全部);Guest(无账户)

### Guest(游客)

- **类别**:项目层
- **定义**:无账户,仅凭 token 访问某个 share。**服务端不持久化任何游客信息**
- **使用场景**:`/s/{slug}/{token}` URL;ticket #11
- **不是**:User(无 cookie / 无 JWT)
- **边界**:游客能做的所有事 = 看 share 元数据 + 文件列表 + 预览 + 单文件下载 + 打包下载 + 看 EXIF,**不能**上传/删除/授权

### Owner / Viewer / Editor

- **类别**:授权角色(非顶层账号)
- **定义**:Owner=创建者;Viewer/Editor=被 owner 显式授权的登录用户
- **使用场景**:`user_grants` 表 role 字段;ticket #12 / #13
- **不是**:admin 是顶层角色,与授权角色正交

---

## 3. 容器类

### Share

- **类别**:核心实体
- **定义**:分享容器,顶层权限域。每个 share 必须有 1 个 owner,可挂 N 个 file、M 个 token、K 个 user_grant
- **使用场景**:所有 ticket 的中心实体;`shares` 表
- **不是**:File(单个文件);Folder(不是文件夹,扁平结构)
- **边界**:share 可空(无 file);share 删除 = 硬删(D23)

### File

- **类别**:核心实体
- **定义**:分享内的具体文件(图片/视频/任意)。物理存于 OBS,DB 仅存元数据
- **使用场景**:`files` 表;ticket #14-#18 上传流程
- **不是**:Folder(无嵌套);Version(OBS 物理只有 latest,versioning 仅兜底)
- **边界**:file.status ∈ {processing, ready, failed};file 可被任意 share 内 editor 删除

### Slug

- **类别**:URL 标识
- **定义**:share 的 URL 路径段,默认系统生成 8 位 base62,用户可改名
- **使用场景**:`/s/{slug}/{token}` 路径形式;`shares.slug` 字段
- **不是**:share_id(数据库内部 id,不对外暴露);token(短码,挂在 slug 下)
- **边界**:改名规则 `^[a-z0-9-]{3,32}$`,大小写不敏感,全局唯一

### OBS Prefix

- **类别**:存储路径
- **定义**:`obs://obs-mushroom/PixelHoard/shares/{share_id}/raw/{yyyy}/{mm}/{dd}/{upload_id}_{i}.{ext}` — 删 share 时整段 prefix 删
- **使用场景**:ADR-0004 §OBS prefix 设计
- **不是**:bucket 路径(根在 `PixelHoard/`,不是 bucket 根)

---

## 4. 凭证类

### Token(访问令牌)

- **类别**:凭证
- **定义**:短码(8 位 base62),绑定 share + 权限(read / readwrite),游客凭此访问
- **使用场景**:`share_tokens` 表;`/s/{slug}/{token}` 路径中的 token 段
- **不是**:UserGrant(给登录用户);JWT(给登录用户);Slug(share 标识)
- **边界**:token 可设 expires_at / revoked_at / label / public_note 四个可选字段

### Token Permission

- **类别**:枚举值
- **定义**:`read` 或 `readwrite` 两值之一,绑定 token
- **使用场景**:`share_tokens.permission` 字段
- **不是**:UserGrant 的 role(viewer / editor,另一维度)
- **边界**:read token 不能上传/删除,但**仍可下载/预览** — 游客下载能力与 token 权限正交

### Public Note

- **类别**:token 字段
- **定义**:token 上对**游客**可见的留言字段
- **使用场景**:游客页访问时若非空则顶部展示一行
- **不是**:Label(owner 私有);token 创建时间(游客看不到)

### Label

- **类别**:token 字段
- **定义**:token 上对**owner 私有**的管理备注
- **使用场景**:owner 后台 token 列表展示用
- **不是**:Public Note(游客看不到)

### Expires At / Revoked At

- **类别**:token 字段
- **定义**:Expires At=过期时间(空=永不过期);Revoked At=撤销时间(非空=失效)
- **使用场景**:D19 / D20 单 token 粒度撤销 + 过期
- **不是**:share 级删除(整组失效);删除 token 行(数据仍留作审计)

---

## 5. 派生类

### UserGrant

- **类别**:授权关系
- **定义**:登录用户被授权访问某 share 的关系,绑定 role=viewer | editor
- **使用场景**:`user_grants` 表;ticket #12 / #13
- **不是**:token(给游客);share ownership(永久)
- **边界**:viewer 不能上传/删除,editor 可上传/删除但不能授权他人

### Display 档 / Preview 档 / Thumb 档 / RAW 档

- **类别**:文件衍生档
- **定义**:RAW=用户原文件;Display=浏览器可播的副本(原图直传或转码兜底);Preview=800px 宽中档;Thumb=200px 宽缩略图
- **使用场景**:`files` 表 thumb_key / preview_key / display_key;ADR-0004 §图片衍生档
- **不是**:HLS 切片(不做);ABR 码率档(不做)
- **边界**:Thumb / Preview **必有**;Display **仅当原图浏览器不支持时生成**

### Probe(探测结果)

- **类别**:文件元数据
- **定义**:上传后 ffprobe(视频)/ Pillow sniff(图片)得到的结果,存 `files` 表
- **使用场景**:视频 moov 校验(ADR-0003);图片 width/height/EXIF 读

---

## 6. 状态机

### Share 状态

- **类别**:状态枚举
- **定义**:`active`(默认)/ `deleted`(硬删后保留 30 天审计)
- **使用场景**:`shares.is_deleted` / `deleted_at` 字段
- **不是**:File 状态(独立)

### File 状态

- **类别**:状态枚举
- **定义**:`processing`(上传完,衍生档生成中)/ `ready`(全部 ready)/ `failed`(处理失败,记录 reason)
- **使用场景**:`files.status` 字段;ticket #17 / #18
- **边界**:processing 状态下文件 URL 仍可下 raw,但 thumb/preview 不可用

---

## 7. 工程术语

### Pre-signed URL

- **类别**:OBS 概念
- **定义**:OBS 临时签名 URL,浏览器拿此 URL 直传/直下,过期间失效
- **使用场景**:上传(D45-D49);下载(游客直下);ticket #14
- **不是**:长期公开 URL(OBS 默认所有 object 私有)

### Multipart Upload

- **类别**:OBS 协议
- **定义**:OBS 大文件分片上传协议,5MB 起,可并发/可断点续传
- **使用场景**:D46 ticket #14-#16
- **不是**:单 PUT(超过 5GB 必失败)

### Range / 206

- **类别**:HTTP 协议
- **定义**:HTTP Range 请求 + 206 Partial Content 响应,视频 seek 的基础
- **使用场景**:P6 视频性能硬约束;ADR-0003
- **不是**:整段下载(无 seek 能力)

---

## 8. 词汇冲突索引(写作时请避开)

| 易混词 | 区别 |
|---|---|
| Share vs File | share = 容器, file = 内容;权限挂在 share 上 |
| Token vs UserGrant | token = 游客凭证, UserGrant = 登录用户授权 |
| Slug vs share_id vs token_code | slug=share 路径名;share_id=DB 主键;token_code=短码 |
| Permission(token) vs Role(UserGrant) | 两个独立维度,可并存 |
| Display vs Preview vs Thumb | 三档,size 不同,Display 仅兜底时存在 |
| Raw vs Original | 都指原文件;项目内统一用 **RAW** |
| Owner vs Admin | owner=单 share 创建者;admin=全局角色 |
| Reader vs Viewer | token read = 游客只读;user_grant viewer = 登录用户只读;**两者不互通** |

---

> **不要在这里写**:
> - 实现细节(库名 / API / 代码) → 去 ADR
> - 决策编号列表(D1-D83) → 去 `docs/domain/decision-log.md`
> - TODO / 待办 / 进度 → 不属于词汇锁
> - 性能数据 / 技术栈表 → 去 ADR
## 2026-09-09 补全轮词汇锁增补
- **文件访问档位(kind)**:raw(原文件)/ thumb(200px)/ preview(800px)/ display(RAW·HEIC 兜底档);均经签名 URL 端点按需签发,不暴露 OBS key
- **游客 API(/api/guest/***)**:share 视图(share+permission+public_note)、文件列表、文件 URL、文件删除(readwrite token);游客链接页面 = SPA
- **共享给我的(/shares/granted)**:非 owner 被授权(viewer/editor)的 share 列表入口
- **管理员(admin)**:用户管理 /admin/users;对全部 share/文件有读+管理权
