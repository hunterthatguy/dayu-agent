import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { subscribeSse } from "@/lib/sse";
import type { AgentEvent } from "@/types/api";
import {
  INITIAL_TURN_STATE,
  isTerminalEvent,
  reduceTurnState,
  type ChatTurnState,
  type ChatTurnStatus,
} from "./chatEventReducer";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  reasoning?: string;
  status?: ChatTurnStatus;
  toolCalls?: ChatTurnState["toolCalls"];
  usage?: ChatTurnState["usage"];
  errorMessage?: string;
}

interface ChatSession {
  sessionId: string;
  messages: Message[];
}

const STATUS_LABEL: Record<ChatTurnStatus, string> = {
  streaming: "处理中…",
  completed: "完成",
  cancelled: "已取消",
  error: "出错",
};

function projectMessage(message: Message, state: ChatTurnState): Message {
  return {
    ...message,
    text: state.content,
    reasoning: state.reasoning || undefined,
    status: state.status,
    toolCalls: state.toolCalls,
    usage: state.usage,
    errorMessage: state.lastError,
  };
}

export default function ChatConsolePage() {
  const [sceneName, setSceneName] = useState<string>("");
  const [ticker, setTicker] = useState<string>("");
  const [inputText, setInputText] = useState<string>("");
  const [session, setSession] = useState<ChatSession | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const disposeSseRef = useRef<(() => void) | null>(null);
  const turnStateRef = useRef<ChatTurnState>(INITIAL_TURN_STATE);

  const { data: sceneMatrix } = useQuery({
    queryKey: ["scene-matrix"],
    queryFn: api.config.getSceneMatrix,
  });

  const closeActiveStream = useCallback(() => {
    disposeSseRef.current?.();
    disposeSseRef.current = null;
  }, []);

  const subscribeToSession = useCallback(
    (sessionId: string, messageId: string) => {
      closeActiveStream();
      turnStateRef.current = INITIAL_TURN_STATE;

      const applyState = (next: ChatTurnState) => {
        turnStateRef.current = next;
        setSession((prev) => {
          if (!prev) {
            return prev;
          }
          return {
            ...prev,
            messages: prev.messages.map((m) => (m.id === messageId ? projectMessage(m, next) : m)),
          };
        });
      };

      const dispose = subscribeSse<AgentEvent>(api.chat.getSessionEventsPath(sessionId), {
        onEvent: (event) => {
          const next = reduceTurnState(turnStateRef.current, event);
          if (next !== turnStateRef.current) {
            applyState(next);
          }
          return isTerminalEvent(event);
        },
        onError: () => {
          // EventSource 会自动重连；只有彻底关闭后才走 onClose
        },
        onClose: () => {
          if (disposeSseRef.current === dispose) {
            disposeSseRef.current = null;
          }
          const final = turnStateRef.current;
          if (final.status === "streaming") {
            applyState({ ...final, status: "error", lastError: final.lastError ?? "事件流中断" });
          }
        },
      });

      disposeSseRef.current = dispose;
    },
    [closeActiveStream],
  );

  const submitMutation = useMutation({
    mutationFn: () =>
      api.chat.submitTurn({
        user_text: inputText,
        ticker: ticker || undefined,
        scene_name: sceneName || undefined,
        session_id: session?.sessionId || undefined,
      }),
    onSuccess: (response) => {
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        text: inputText,
      };

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: "",
        status: "streaming",
        toolCalls: [],
      };

      setSession((prev) => ({
        sessionId: response.session_id,
        messages: [...(prev?.messages || []), userMessage, assistantMessage],
      }));

      setInputText("");
      // 使用 session 级订阅（API 返回的 run_id 实际是 session_id）
      subscribeToSession(response.session_id, assistantMessage.id);
    },
  });

  const handleNewSession = () => {
    closeActiveStream();
    setSession(null);
  };

  useEffect(() => {
    return () => {
      closeActiveStream();
    };
  }, [closeActiveStream]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (inputText.trim() && !submitMutation.isPending) {
        submitMutation.mutate();
      }
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-zinc-200">
        <select
          value={sceneName}
          onChange={(e) => setSceneName(e.target.value)}
          className="px-2 py-1 text-sm border border-zinc-300 rounded focus:outline-none focus:ring-1 focus:ring-zinc-400"
        >
          <option value="">默认场景</option>
          {sceneMatrix?.rows.map((row) => (
            <option key={row.scene_name} value={row.scene_name}>
              {row.scene_name}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker（可选）"
          className="px-2 py-1 text-sm border border-zinc-300 rounded w-24 focus:outline-none focus:ring-1 focus:ring-zinc-400"
        />
        <button
          onClick={handleNewSession}
          className="px-3 py-1 text-sm bg-zinc-100 text-zinc-700 rounded hover:bg-zinc-200"
        >
          新会话
        </button>
        {session && (
          <span className="text-xs text-zinc-400">Session: {session.sessionId.slice(0, 8)}…</span>
        )}
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {!session || session.messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-zinc-500">
            输入问题开始对话（支持 Cmd+Enter 快捷提交）
          </div>
        ) : (
          session.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {submitMutation.isError && (
        <div className="px-4 py-2 bg-rose-50 text-rose-600 text-sm border-t border-rose-200">
          发送失败：{(submitMutation.error as Error).message}
        </div>
      )}

      <div className="px-4 py-3 border-t border-zinc-200">
        <div className="flex gap-2">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题... (Cmd+Enter 提交)"
            rows={3}
            className="flex-1 px-3 py-2 text-sm border border-zinc-300 rounded resize-none focus:outline-none focus:ring-1 focus:ring-zinc-400"
            disabled={submitMutation.isPending}
          />
          <button
            onClick={() => submitMutation.mutate()}
            disabled={!inputText.trim() || submitMutation.isPending}
            className="px-4 py-2 text-sm bg-zinc-900 text-white rounded hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed self-end"
          >
            {submitMutation.isPending ? "发送中..." : "发送"}
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const status = message.status;
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] px-3 py-2 rounded-lg text-sm ${
          isUser ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-800"
        }`}
      >
        {message.reasoning && !isUser && (
          <details className="mb-2 text-xs text-zinc-500">
            <summary className="cursor-pointer select-none">思考过程</summary>
            <div className="mt-1 whitespace-pre-wrap">{message.reasoning}</div>
          </details>
        )}
        <div className="whitespace-pre-wrap">{message.text}</div>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 pt-2 border-t border-zinc-300/50 text-xs text-zinc-600 space-y-1">
            {message.toolCalls.map((tool) => (
              <div key={tool.id}>
                <span className="font-mono">[{toolStateGlyph(tool.state)}]</span> {tool.name}
                {tool.argumentsPreview && (
                  <span className="text-zinc-400"> · {tool.argumentsPreview}</span>
                )}
                {tool.errorMessage && (
                  <span className="text-rose-500"> · {tool.errorMessage}</span>
                )}
              </div>
            ))}
          </div>
        )}
        {!isUser && status === "streaming" && (
          <span className="inline-block w-2 h-4 ml-1 bg-zinc-400 animate-pulse" />
        )}
        {!isUser && status && status !== "streaming" && (
          <div
            className={`mt-2 text-xs ${
              status === "completed"
                ? "text-emerald-600"
                : status === "cancelled"
                  ? "text-amber-600"
                  : "text-rose-600"
            }`}
          >
            {STATUS_LABEL[status]}
            {message.errorMessage ? `：${message.errorMessage}` : ""}
            {message.usage?.totalTokens !== undefined && (
              <span className="ml-2 text-zinc-400">tokens: {message.usage.totalTokens}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function toolStateGlyph(state: "dispatched" | "succeeded" | "failed"): string {
  if (state === "succeeded") return "✓";
  if (state === "failed") return "✗";
  return "…";
}
