import type { AgentEvent } from "@/types/api";

/**
 * 一次 chat turn 的助手消息状态。
 *
 * - content: 已渲染的最终文本；优先权 final_answer > 累计 content_delta > reasoning_delta。
 * - reasoning: 累计 reasoning_delta，单独展示思考链，不与最终回答混合。
 * - toolCalls: 已分发的工具调用快照（按工具调用 id 去重 / 升级状态）。
 * - status: 流的整体状态。
 * - usage: 最近一次 metadata 中的 token 用量摘要。
 * - lastError: 最近一次 error / warning 信息。
 */
export type ChatTurnStatus = "streaming" | "completed" | "cancelled" | "error";

export interface ToolCallView {
  id: string;
  name: string;
  state: "dispatched" | "succeeded" | "failed";
  argumentsPreview: string;
  resultPreview?: string;
  errorMessage?: string;
}

export interface UsageSummary {
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
}

export interface ChatTurnState {
  content: string;
  reasoning: string;
  toolCalls: ToolCallView[];
  status: ChatTurnStatus;
  usage?: UsageSummary;
  lastError?: string;
}

export const INITIAL_TURN_STATE: ChatTurnState = {
  content: "",
  reasoning: "",
  toolCalls: [],
  status: "streaming",
};

const TERMINAL_EVENT_TYPES = new Set(["final_answer", "error", "cancelled"]);

/** 终结事件：收到这些事件意味着本轮 SSE 可以关闭。 */
export function isTerminalEvent(event: AgentEvent): boolean {
  return TERMINAL_EVENT_TYPES.has(event.type);
}

interface ToolEventPayload {
  engine_event_type?: string;
  data?: Record<string, unknown>;
}

interface FinalAnswerPayload {
  content?: string;
}

interface ErrorPayload {
  message?: string;
  detail?: string;
}

interface MetadataPayload {
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

interface CancelledPayload {
  reason?: string;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function previewArguments(args: unknown): string {
  if (typeof args === "string") {
    return args.length > 200 ? `${args.slice(0, 200)}…` : args;
  }
  if (args === undefined || args === null) {
    return "";
  }
  try {
    const text = JSON.stringify(args);
    return text.length > 200 ? `${text.slice(0, 200)}…` : text;
  } catch {
    return String(args);
  }
}

function upsertToolCall(
  list: ToolCallView[],
  id: string,
  patch: (existing: ToolCallView | undefined) => ToolCallView,
): ToolCallView[] {
  const idx = list.findIndex((tc) => tc.id === id);
  if (idx === -1) {
    return [...list, patch(undefined)];
  }
  const next = [...list];
  next[idx] = patch(next[idx]);
  return next;
}

function reduceToolEvent(state: ChatTurnState, payload: ToolEventPayload): ChatTurnState {
  const engineType = payload.engine_event_type;
  const data = payload.data ?? {};
  if (!engineType) {
    return state;
  }
  if (engineType === "tool_call_dispatched") {
    const id = asString(data.tool_call_id) ?? asString(data.id) ?? `${Date.now()}`;
    const name = asString(data.name) ?? "unknown_tool";
    return {
      ...state,
      toolCalls: upsertToolCall(state.toolCalls, id, (existing) => ({
        id,
        name: existing?.name ?? name,
        state: "dispatched",
        argumentsPreview: previewArguments(data.arguments),
      })),
    };
  }
  if (engineType === "tool_call_result") {
    const id = asString(data.tool_call_id) ?? asString(data.id);
    if (!id) {
      return state;
    }
    const ok = data.error === undefined || data.error === null;
    const resultPreview = previewArguments(data.result);
    const errorMessage = ok ? undefined : asString(data.error) ?? "工具执行失败";
    return {
      ...state,
      toolCalls: upsertToolCall(state.toolCalls, id, (existing) => ({
        id,
        name: existing?.name ?? asString(data.name) ?? "unknown_tool",
        state: ok ? "succeeded" : "failed",
        argumentsPreview: existing?.argumentsPreview ?? "",
        resultPreview,
        errorMessage,
      })),
    };
  }
  return state;
}

/**
 * 把单条 AgentEvent 应用到 turn 状态上。
 *
 * 该函数为纯函数：相同输入恒得到相同输出，便于做单元测试与回放。
 */
export function reduceTurnState(state: ChatTurnState, event: AgentEvent): ChatTurnState {
  switch (event.type) {
    case "content_delta": {
      const text = typeof event.payload === "string" ? event.payload : "";
      if (!text) {
        return state;
      }
      return { ...state, content: state.content + text };
    }
    case "reasoning_delta": {
      const text = typeof event.payload === "string" ? event.payload : "";
      if (!text) {
        return state;
      }
      return { ...state, reasoning: state.reasoning + text };
    }
    case "final_answer": {
      const payload = (event.payload ?? {}) as FinalAnswerPayload;
      const finalContent = payload.content ?? state.content;
      return { ...state, content: finalContent, status: "completed" };
    }
    case "tool_event": {
      const payload = (event.payload ?? {}) as ToolEventPayload;
      return reduceToolEvent(state, payload);
    }
    case "metadata": {
      const payload = (event.payload ?? {}) as MetadataPayload;
      const usage = payload.usage;
      if (!usage) {
        return state;
      }
      return {
        ...state,
        usage: {
          promptTokens: asNumber(usage.prompt_tokens),
          completionTokens: asNumber(usage.completion_tokens),
          totalTokens: asNumber(usage.total_tokens),
        },
      };
    }
    case "warning": {
      const payload = (event.payload ?? {}) as ErrorPayload;
      const message = payload.message ?? payload.detail;
      if (!message) {
        return state;
      }
      return { ...state, lastError: message };
    }
    case "error": {
      const payload = (event.payload ?? {}) as ErrorPayload;
      const message = payload.message ?? payload.detail ?? "执行失败";
      return {
        ...state,
        status: "error",
        lastError: message,
      };
    }
    case "cancelled": {
      const payload = (event.payload ?? {}) as CancelledPayload;
      return {
        ...state,
        status: "cancelled",
        lastError: payload.reason,
      };
    }
    case "done":
      // 单次 LLM 迭代结束信号；多步推理中会出现多次，不视为流终结。
      return state;
    default:
      return state;
  }
}
