# ADR-0002:性能预算

- **Status**: Accepted
- **Date**: 2026-09-09
- **Deciders**: User + Hermes Agent
- **Related**: D33-D44(视频+图片策略), P1-P16(性能硬约束)

---

## Context

用户明确要求"重点关注浏览图片和播放视频的性能"。v1 必须有量化指标,避免主观判断。

本 ADR 锁定所有 P* 性能指标为 v1 验收硬约束。

## Decision

### P1-P12 — 浏览器端体验

| # | 指标 | 目标 | 验收方式 |
|---|---|---|---|
| **P1** | 图片缩略图首屏可见 | < 800ms (P95) | Lighthouse + 真机 WiFi |
| **P2** | 单张大图(20MB)首次可见 | < 1.5s (P95) | 单图慢启动测 |
| **P3** | 视频首帧(seek 到任意位置)延迟 | < 1.5s (P95) | Range 请求测 |
| **P4** | 视频起播到流畅 | < 2.5s | 播放器 buffer 测 |
| **P5** | 100 张缩略图瀑布流滚动 | 0 CLS + 60fps | Performance API |
| **P6** | 视频 Range / 206 | 必须支持 | `curl -I` 看 header |
| **P7** | 缩略图懒加载 | 仅视口内 + 1 屏预读 | DevTools Network |
| **P8** | 浏览器直连 OBS | 必须 | Network 验证 |
| **P10** | iOS Safari + Android Chrome 真机 | 必须 | 真机手测 |

### P11-P16 — 服务端/上传

| # | 指标 | 目标 |
|---|---|---|
| **P11** | 缩略图生成 | < 3s/张 |
| **P12** | 衍生档生成(单张原图) | < 8s/张 |
| **P13** | 预签名 URL 签发 | < 50ms |
| **P14** | 单 part 上传(5MB)失败重试 | < 2s |
| **P15** | 上传完成到衍生档 ready | < 8s(图)/ < 15s(视频 ffprobe)|
| **P16** | 并发 part 数 | 默认 3,移动端 2 |

### 视频 moov 校验前置(P3 的可达性)

- 上传后 `ffprobe file | grep moov` 看 `moov_position`
- 不在文件头 → **强提示用户**"视频需快进才能播放,建议转码" — 不偷偷转码(符合 D36)
- UI 显示 ✅ "可快进播放" 或 ⚠️ "仅支持顺序播放"

## Consequences

### Positive

- 所有指标可量化、可在 CI / 端到端测试中验证
- 性能问题出现时有明确的回归基线

### Negative

- 性能预算**只对 v1 在主流硬件/网络下生效**,弱网/老旧设备不在预算内
- 强加 P5(0 CLS)对瀑布流虚拟滚动实现要求高,前端需用 IntersectionObserver

### 风险

- 视频 moov 校验如果 ffprobe 失败率 > 5%,需考虑回退策略(不在 v1 处理)

## 实现关键点

1. **P1 / P2**:Thumb + Preview + Display 全部预生成 → 浏览器拿预签名直连 OBS
2. **P3 / P6**: 视频文件 moov 校验前置 + 不达标就提示
3. **P5**: 前端用 `IntersectionObserver` + virtual list + 图片 `width/height` 属性预留空间
4. **P8**: 浏览器 `fetch(presignedUrl).then(blob => URL.createObjectURL(blob))`,绝不走后端中转
5. **P11 / P12**: Pillow 流水线 + 后台 worker;ARW 解码可慢(`rawpy.process()` 约 1-3s/张)