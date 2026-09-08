# ADR-0003:视频处理策略(原画直传)

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D33-D38, P3, P6

---

## Context

视频处理有 4 个候选方案:
- A. 不转码,原画直传(选 A)
- B. 转 H.264 + ABR HLS
- C. 仅探测,不转码
- D. 转 H.264 MP4 单档

用户选择 **A:原画直传**。理由:
1. 分享必然要是原画的
2. 不转码 = 零 CPU / 零额外存储 / 上传立即可看
3. 服务端简化,只做 ffprobe 探测

## Decision

### 核心规则(D33-D38)

1. **不重编码**: OBS 存什么,前端播放什么
2. **仅 ffprobe 探测**: 分辨率、时长、编码、旋转角
3. **前端原生播放**: `<video>` + HTTP Range / 206,直连 OBS
4. **不兼容即提示**: 浏览器不支持的格式 → 提示"请下载观看",**绝不偷偷转码**

### 视频 moov 校验前置

- 上传完成后立即 `ffprobe`
- 检查 `moov` 原子是否在文件头
- **不在文件头 → UI 弹 ⚠️ "顺序播放,无法快进,建议转码后上传"**
- 不偷偷帮用户转码(尊重原画原则)

### 前端播放器选型

```ts
// 简化逻辑(实际要更细)
const VIDEO_FORMATS = {
  mp4: { h264: 'video/mp4', hevc: 'video/mp4' },
  mov: 'video/quicktime',
  webm: 'video/webm',
  mkv: 'video/x-matroska', // 大多数浏览器不原生支持
  avi: 'video/x-msvideo',   // 浏览器不原生支持
}

function pickPlayer(mime, codec) {
  if (canPlay('video/mp4; codecs="avc1.42E01E"')) return 'native'
  // 不支持就提示下载
  return 'download-prompt'
}
```

## Consequences

### Positive

- 上传立即可看(无转码等待)
- 零服务器 CPU 开销
- 用户完全掌控自己的原文件

### Negative

- iOS Safari 仅支持 H.264 + MP4/MOV,其他格式(iPhone HEVC 录的视频在 Chrome 上无法播) → 用户需下载
- 大视频(>2GB)无 ABR 自适应,弱网下体验差
- HEVC 在 Safari OK,Chrome / Firefox 不行 — 必须前端 sniff

### 风险

- v1 上线后,可能 30% 用户上传的视频无法在线播(用 MKV / AVI / 不规范 MP4)
- 缓解:UI 上传后立即显示"✅ 可在线播放 / ⚠️ 仅下载"badge,降低用户预期

### v2 优化项

- HLS 自适应码率切片(预留能力,D37)
- 智能转码(用户可选"开启自动转码")

## 性能硬约束

- **P3**: 视频首帧 < 1.5s(依赖 moov 在前头)
- **P4**: 起播到流畅 < 2.5s
- **P6**: HTTP Range / 206 必须支持
- **P8**: 浏览器直连 OBS(走预签名 URL)

## 上传时 ffprobe 流程

```python
# api/worker/probe_video.py(伪代码)
async def probe_video(obs_path: str) -> VideoProbeResult:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,codec_name,codec_type:format=duration,size",
        "-of", "json",
        obs_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ProbeFailed(stderr.decode())
    result = json.loads(stdout)
    return VideoProbeResult(
        width=...,
        height=...,
        duration=...,
        codec=...,
        # 关键:moov 位置
        moov_at_head=await check_moov_at_head(obs_path),
    )
```