import type { PipelineProgressView } from "@/types/api";

// SSE 直接连接后端端口（绕过 Vite 代理）
const SSE_BASE_URL = "http://localhost:9000";

export function subscribeSse<T>(
  url: string,
  onEvent: (data: T) => void,
  onError?: (err: Event) => void,
): () => void {
  // SSE 端点直接连接后端
  const fullUrl = url.startsWith("/api") ? `${SSE_BASE_URL}${url}` : url;
  const es = new EventSource(fullUrl);

  console.log("[SSE] 连接建立:", fullUrl);

  es.onopen = () => {
    console.log("[SSE] 连接已打开");
  };

  es.onmessage = (e) => {
    console.log("[SSE] 收到消息:", e.data);
    try {
      const data = JSON.parse(e.data);
      console.log("[SSE] 解析后:", data);
      onEvent(data as T);
    } catch (err) {
      console.log("[SSE] 解析失败:", err);
      // ignore non-JSON keepalive
    }
  };

  es.onerror = (e) => {
    console.log("[SSE] 错误:", e, "readyState:", es.readyState);
    if (onError) {
      onError(e);
    }
    // EventSource会自动重连，但如果是连接失败则关闭
    if (es.readyState === EventSource.CLOSED) {
      console.log("[SSE] 连接已关闭");
    }
  };

  return () => {
    console.log("[SSE] 手动关闭连接");
    es.close();
  };
}

export function subscribePipelineProgress(
  runId: string,
  ticker: string,
  sessionId: string,
  onProgress: (view: PipelineProgressView) => void,
  onError?: (err: Event) => void,
): () => void {
  const url = `/api/upload/progress/${runId}?ticker=${encodeURIComponent(ticker)}&session_id=${encodeURIComponent(sessionId)}`;
  return subscribeSse<PipelineProgressView>(url, onProgress, onError);
}