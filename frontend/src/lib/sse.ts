import type { PipelineProgressView } from "@/types/api";

/**
 * 通用 SSE 客户端工具。
 *
 * - 默认使用相对 URL，由 Vite 代理（dev）或同源（prod）转发到后端。
 * - 通过 onClose 通知调用方"连接彻底关闭"，调用方可据此收尾 UI 状态。
 * - 返回的 dispose 函数用于主动关闭，重复调用安全。
 */

export interface SubscribeSseOptions<T> {
  /** 收到一条已 JSON 解析的事件时回调。返回 true 表示业务侧请求关闭连接。 */
  onEvent: (data: T) => boolean | void;
  /** EventSource 触发 error 时回调。注意 EventSource 默认会自动重连。 */
  onError?: (err: Event) => void;
  /** 连接彻底关闭（被业务关闭或浏览器置为 CLOSED 状态）时回调，仅触发一次。 */
  onClose?: () => void;
  /** 显式注入 EventSource 实现，便于测试。 */
  eventSourceFactory?: (url: string) => EventSource;
}

export function subscribeSse<T>(url: string, options: SubscribeSseOptions<T>): () => void {
  const factory = options.eventSourceFactory ?? ((u: string) => new EventSource(u));
  const es = factory(url);
  let closed = false;

  const finalize = () => {
    if (closed) {
      return;
    }
    closed = true;
    try {
      es.close();
    } catch {
      // ignore
    }
    options.onClose?.();
  };

  es.onmessage = (e) => {
    if (closed) {
      return;
    }
    let parsed: T;
    try {
      parsed = JSON.parse(e.data) as T;
    } catch {
      // 心跳 / 非 JSON 数据，忽略
      return;
    }
    const requestClose = options.onEvent(parsed);
    if (requestClose === true) {
      finalize();
    }
  };

  es.onerror = (e) => {
    options.onError?.(e);
    // EventSource 会在 CLOSED 状态下停止重连，此时视为彻底失败
    if (es.readyState === EventSource.CLOSED) {
      finalize();
    }
  };

  return finalize;
}

export function subscribePipelineProgress(
  runId: string,
  ticker: string,
  sessionId: string,
  onProgress: (view: PipelineProgressView) => void,
  onError?: (err: Event) => void,
): () => void {
  const url = `/api/upload/progress/${runId}?ticker=${encodeURIComponent(ticker)}&session_id=${encodeURIComponent(sessionId)}`;
  return subscribeSse<PipelineProgressView>(url, {
    onEvent: (view) => {
      onProgress(view);
    },
    onError,
  });
}
