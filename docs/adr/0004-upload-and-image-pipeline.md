# ADR-0004:上传与图片处理策略

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D39-D49, P11-P16

---

## Context

### 上传方式(D45-D49)

5 个候选:浏览器 → 后端 → OBS / 直传 OBS / 直传+分片 / 桌面客户端。
选 **C:直传 + Multipart 分片**,理由:
1. 浏览器直连 OBS,后端零代理流量
2. >5MB 自动分片,断点续传原生支持
3. 移动端友好(上传大视频经常断线)

### 图片处理(D39-D44)

3 个候选:必生成 display / 仅 thumb+preview / 自适应+兜底。
选 **C+A**:浏览器原生支持 → 直传原图作 display;不支持 → 必生成 display。
理由:
1. JPG/PNG/WebP 等不需要处理,保持原画质
2. ARW/CR2/NEF 等浏览器根本播不了,**必须**有一份浏览器友好的副本
3. 全部必须生成 thumb(200) + preview(800)

## Decision

### 上传协议

```
[浏览器]                          [FastAPI]                      [OBS]
   |                                  |
   | POST /shares/{slug}/upload-init |                            |
   |   {filename, size, mime, sha256} |                            |
   |--------------------------------->|                            |
   |                                  | 校验: token权限+quota     |
   |                                  | 签发 Multipart Init       |
   |                                  |--------------------------->|
   |<---------------------------------|                            |
   |   {upload_id, part_urls[5MB×N], complete_url}                 |
   |                                                                   |
   | PUT part1 (5MB) ──────────────────────────────────────────────>  |
   | PUT part2 (5MB) ──────────────────────────────────────────────>  |
   | ... (并发3~5个part,失败重试该part)                              |
   |                                                                   |
   | POST /shares/{slug}/upload-complete                             |
   |   {upload_id, parts[etag]}                                       |
   |--------------------------------->|                              |
   |                                  | 校验所有 part ETag |
   |                                  | Complete Multipart          |
   |                                  |--------------------------->  |
   |                                  | 写 file row                 |
   |                                  | BackgroundTask:衍生档生成 |
   |<---------------------------------|                              |
   |   {file_id, status:"processing"}  |                              |
```

### OBS prefix 设计

```
obs://obs-mushroom/PixelHoard/
  shares/{share_id}/
    raw/{yyyy}/{mm}/{dd}/{upload_id}_{i}.{ext}
    thumb/{file_id}.jpg       # 200px
    preview/{file_id}.jpg     # 800px
    display/{file_id}.jpg     # 兜底档(仅当原图不能直接显示)
```

### 图片衍生档生成流程

```python
# api/worker/generate_image_variants.py
NATIVE_FORMATS = {"jpg", "jpeg", "png", "webp", "gif", "avif", "heic", "heif"}

async def generate_variants(file_id: str, suffix: str, mime: str):
    raw = await obs.get_object(f"shares/{share_id}/raw/{file_id}.{suffix}")
    
    # 必有档
    thumb = await resize(raw, max_width=200)
    preview = await resize(raw, max_width=800)
    
    # 兜底档(仅当浏览器不支持)
    needs_display = suffix.lower() not in NATIVE_FORMATS
    tasks = [
        obs.put_object(f"shares/{share_id}/thumb/{file_id}.jpg", thumb),
        obs.put_object(f"shares/{share_id}/preview/{file_id}.jpg", preview),
    ]
    if needs_display:
        display = await convert_to_jpeg(raw, quality=95, preserve_exif=True)
        tasks.append(obs.put_object(f"shares/{share_id}/display/{file_id}.jpg", display))
    
    await asyncio.gather(*tasks)
    
    await db.execute(
        "UPDATE files SET status='ready', "
        "thumb_url=?, preview_url=?, display_url=? WHERE id=?",
        ...
    )
```

## Consequences

### Positive

- 大文件上传友好(分片 + 断点续传)
- 移动端相册直传可用(D71)
- 衍生档生成不影响上传主流程(D44)
- 浏览器原生支持格式零损耗

### Negative

- HEIC/HEIF 在 Chrome Android 仍需兜底(虽 iOS Safari 原生支持)
- ARW 解码耗时较长(1-3s/张,Pillow + rawpy + dcraw 三件套)
- 后台 worker 必须独立部署,不能与 API 同进程阻塞

### 风险

- OBS Multipart Init 失败 → 重试
- 衍生档生成失败 → file.status='failed',UI 显示"⚠️ 处理失败,可重试"

### 性能预算

- **P11**: 缩略图生成 < 3s/张
- **P12**: 衍生档生成 < 8s/张
- **P13**: 预签名 URL < 50ms
- **P15**: 上传完成到 ready < 8s(图)/ < 15s(视频 ffprobe)
- **P16**: 并发 part = 3(默认), 2(移动端)

## ARW 缩略图生成特别说明

索尼 ARW 是 RAW 格式,直接 Pillow 打不开,需要:
1. `rawpy.process()` 读 RAW → numpy
2. `Pillow.fromarray()` 转 Image
3. `dcraw -e` 兼容方案(从 `.thumb.jpg` / `.preview.jpg` / `.jpg` 取已嵌入缩略图)

详情见 `docs/domain/raw-decoding.md`(后续编写)。