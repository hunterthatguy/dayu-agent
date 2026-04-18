import type { PipelineProgressView } from "@/types/api";

export function subscribeSse<T>(
  url: string,
  onEvent: (data: T) => void,
  onError?: (err: Event) => void,
): () => void {
  const es = new EventSource(url);
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent(data as T);
    } catch {
      // ignore non-JSON keepalive
    }
  };
  if (onError) {
    es.onerror = onError;
  }
  return () => {
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