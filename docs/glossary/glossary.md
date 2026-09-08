# PixelHoard Glossary

> 项目所有术语的权威定义。出现歧义时,以此为准。

## 角色类

| 术语 | 定义 |
|---|---|
| **Admin(管理员)** | 系统管理员,可看全部 share / user,可做任何 owner 能做的事 |
| **User(用户)** | 注册登录用户,可创建 share、可被授权访问别人的 share |
| **Guest(游客)** | 无账户,仅凭 token 访问某个 share。**不持久化任何信息** |
| **Owner** | 创建某 share 的用户,对该 share 有完全权限 |
| **Viewer** | 被 owner 授权只能"看"的用户角色 |
| **Editor** | 被 owner 授权可"看 + 上传 + 删除"的用户角色 |

## 容器类

| 术语 | 定义 |
|---|---|
| **Share** | 分享容器。顶层权限域。每个 share 必须有 1 个 owner |
| **File** | 分享内的具体文件。物理存于 OBS,DB 仅存元数据(文件名/size/mime/sha256/上传者/上传时间/probe结果) |
| **Slug** | share 的 URL 路径,默认 8 位 base62 系统生成,可改 |
| **OBS Prefix** | `obs://obs-mushroom/PixelHoard/shares/{share_id}/...`,删 share 时整段删 |

## 凭证类

| 术语 | 定义 |
|---|---|
| **Token** | 短码(8 位 base62),绑定 share + 权限(read / readwrite),游客用 |
| **Token Permission** | `read`(游客只读)或 `readwrite`(游客可上传/删除)|
| **Public Note** | token 上对游客可见的留言。空则不展示 |
| **Label** | token 上对 owner 私有的管理备注 |
| **Expires At** | token 过期时间。空 = 永不过期 |
| **Revoked At** | token 撤销时间。非空即失效 |

## 派生类

| 术语 | 定义 |
|---|---|
| **UserGrant** | 登录用户被授权访问某 share 的关系。role = viewer / editor |
| **Display 档** | 浏览器可播的副本。原图能播则用原图,否则转 JPEG/WebP 95% 兜底 |
| **Preview 档** | 800px 宽中档预览图,**必有** |
| **Thumb 档** | 200px 宽缩略图,**必有** |
| **RAW 档** | 用户上传原文件,**必有**,OBS 原样保存 |
| **Probe** | 上传后 ffprobe(视频)/ Pillow sniff(图片)得到的结果,存 DB |

## 状态机

| 术语 | 定义 |
|---|---|
| **Share 状态** | `active`(默认)/ `deleted`(硬删后保留 30 天审计)|
| **File 状态** | `processing`(上传完,衍生档生成中)/ `ready`(全部 ready)/ `failed`(处理失败,记录原因)|

## 工程术语

| 术语 | 定义 |
|---|---|
| **Pre-signed URL** | OBS 临时签名 URL,浏览器拿此 URL 直传/直下,过期间失效 |
| **Multipart Upload** | OBS 大文件分片上传协议,5MB 起,可并发/可断点续传 |
| **Range / 206** | HTTP Range 请求 + 206 Partial Content 响应,视频 seek 的基础 |

## 反义/易混

| ❌ 不要说 | ✅ 要说 | 理由 |
|---|---|---|
| "相册" | **Share** | 不要用"相册",易混 |
| "分享码" | **Token** | 文档统一 |
| "权限" | **Permission**(token) / **Role**(user_grant) | 两个不同维度 |
| "上传到分享" | "上传到 share {slug}" | share 是命名空间 |