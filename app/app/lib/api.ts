export interface HelloPayload {
  message: string;
  service: string;
  version: string;
  timestamp: string;
}

export type HelloResult =
  | {
      connected: true;
      data: HelloPayload;
      latencyMs: number;
    }
  | {
      connected: false;
      error: string;
      latencyMs: number;
    };

export async function fetchBackendHello(options?: {
  baseUrl?: string;
  name?: string;
}): Promise<HelloResult> {
  const baseUrl = (options?.baseUrl ?? "").replace(/\/+$/, "");
  const query = options?.name?.trim()
    ? `?name=${encodeURIComponent(options.name.trim())}`
    : "";
  const endpoint = `${baseUrl}/api/hello${query}`;
  const startedAt = performance.now();

  try {
    const response = await fetch(endpoint, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(4000),
    });
    const latencyMs = Math.round(performance.now() - startedAt);

    if (!response.ok) {
      return {
        connected: false,
        error: `HTTP ${response.status} ${response.statusText}`,
        latencyMs,
      };
    }

    const data = (await response.json()) as HelloPayload;
    return {
      connected: true,
      data,
      latencyMs,
    };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - startedAt);
    return {
      connected: false,
      error: err instanceof Error ? err.message : "Không thể kết nối tới Backend",
      latencyMs,
    };
  }
}

