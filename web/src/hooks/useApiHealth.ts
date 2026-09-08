import { useEffect, useState } from "react";

interface HealthResp {
  ok: boolean;
  service: string;
  version: string;
  phase?: string;
  milestone?: string;
}

interface ApiState {
  health: HealthResp | null;
  version: HealthResp | null;
  loading: boolean;
  error: string | null;
  latencyMs: number | null;
}

/**
 * 调 /api/health + /api/version,联调验证 FastAPI ↔ Vite 反代是否打通。
 * ticket #2 的核心 hook。
 */
export function useApiHealth(): ApiState {
  const [state, setState] = useState<ApiState>({
    health: null,
    version: null,
    loading: true,
    error: null,
    latencyMs: null,
  });

  useEffect(() => {
    const t0 = performance.now();
    Promise.all([
      fetch("/api/health").then((r) => r.json()),
      fetch("/api/version").then((r) => r.json()),
    ])
      .then(([health, version]) => {
        const dt = performance.now() - t0;
        setState({
          health,
          version,
          loading: false,
          error: null,
          latencyMs: Math.round(dt),
        });
      })
      .catch((e) =>
        setState({
          health: null,
          version: null,
          loading: false,
          error: String(e),
          latencyMs: null,
        })
      );
  }, []);

  return state;
}