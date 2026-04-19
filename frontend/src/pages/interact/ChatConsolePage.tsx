import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentEvent, SceneMatrixView } from "@/types/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: { name: string; args: Record<string, unknown> }[];
  isStreaming?: boolean;
}

interface ChatSession {
  sessionId: string;
  messages: Message[];
}

export default function ChatConsolePage() {
  const [sceneName, setSceneName] = useState<string>("");
  const [ticker, setTicker] = useState<string>("");
  const [inputText, setInputText] = useState<string>("");
  const [session, setSession] = useState<ChatSession | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // 获取 scene 矩阵
  const { data: sceneMatrix } = useQuery({
    queryKey: ["scene-matrix"],
    queryFn: api.config.getSceneMatrix,
  });

  // 提交对话
  const submitMutation = useMutation({
    mutationFn: () =>
      api.chat.submitTurn({
        user_text: inputText,
        ticker: ticker || undefined,
        scene_name: sceneName || undefined,
        session_id: session?.sessionId || undefined,
      }),
    onSuccess: (response) => {
      // 添加用户消息
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: inputText,
      };

      // 添加助手消息占位
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setSession((prev) => ({
        sessionId: response.session_id,
        messages: [...(prev?.messages || []), userMessage, assistantMessage],
      }));

      setInputText("");
      subscribeToEvents(response.session_id, assistantMessage.id);
    },
  });

  // SSE 事件订阅
  const subscribeToEvents = useCallback((sessionId: string, messageId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(api.chat.getSessionEventsUrl(sessionId));
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const agentEvent: AgentEvent = JSON.parse(event.data);
        handleAgentEvent(agentEvent, messageId);
      } catch {
        // 忽略解析错误
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === messageId ? { ...m, isStreaming: false } : m,
          ),
        };
      });
    };
  }, []);

  const handleAgentEvent = (event: AgentEvent, messageId: string) => {
    // 后端事件类型：content_delta, reasoning_delta, final_answer, tool_event, error, done
    if (event.type === "content_delta") {
      // payload 是字符串
      const text = event.payload as string | undefined;
      if (text) {
        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === messageId
                ? { ...m, content: m.content + text }
                : m,
            ),
          };
        });
      }
    } else if (event.type === "reasoning_delta") {
      // reasoning/thinking 内容，合并到 content
      const text = event.payload as string | undefined;
      if (text) {
        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === messageId
                ? { ...m, content: m.content + text }
                : m,
            ),
          };
        });
      }
    } else if (event.type === "final_answer" || event.type === "done") {
      // 最终答案或完成事件
      setSession((prev) => {
        if (!prev) return prev;
        // 如果有 final_answer payload，使用它替换内容
        if (event.type === "final_answer" && event.payload && typeof event.payload === "object") {
          const payload = event.payload as { content?: string };
          const finalContent = payload.content || "";
          return {
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === messageId ? { ...m, content: finalContent, isStreaming: false } : m,
            ),
          };
        }
        return {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === messageId ? { ...m, isStreaming: false } : m,
          ),
        };
      });
      eventSourceRef.current?.close();
    } else if (event.type === "tool_event") {
      // tool_event payload: { engine_event_type: str, data: dict }
      const payload = event.payload as { engine_event_type?: string; data?: Record<string, unknown> } | undefined;
      const engineEventType = payload?.engine_event_type;
      const data = payload?.data;
      if (engineEventType === "tool_call_start" && data) {
        const toolName = (data.name as string) || "unknown";
        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.map((m) => {
              if (m.id !== messageId) return m;
              const toolCalls = m.toolCalls || [];
              return { ...m, toolCalls: [...toolCalls, { name: toolName, args: {} }] };
            }),
          };
        });
      }
    } else if (event.type === "error") {
      const payload = event.payload as { message?: string } | undefined;
      const errorMsg = payload?.message || "发生错误";
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === messageId
              ? { ...m, content: m.content + `\n[错误: ${errorMsg}]`, isStreaming: false }
              : m,
          ),
        };
      });
    }
  };

  // 新会话
  const handleNewSession = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setSession(null);
  };

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages]);

  // 快捷键提交
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
      {/* 顶部控制栏 */}
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
          <span className="text-xs text-zinc-400">
            Session: {session.sessionId.slice(0, 8)}...
          </span>
        )}
      </div>

      {/* 消息流 */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {!session || session.messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-zinc-500">
            输入问题开始对话（支持 Cmd+Enter 快捷提交）
          </div>
        ) : (
          session.messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] px-3 py-2 rounded-lg text-sm ${
                  message.role === "user"
                    ? "bg-zinc-900 text-white"
                    : "bg-zinc-100 text-zinc-800"
                }`}
              >
                <div className="whitespace-pre-wrap">{message.content}</div>
                {message.toolCalls && message.toolCalls.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-zinc-300/50 text-xs text-zinc-600">
                    {message.toolCalls.map((tool, i) => (
                      <div key={i}>🔧 {tool.name}</div>
                    ))}
                  </div>
                )}
                {message.isStreaming && (
                  <span className="inline-block w-2 h-4 ml-1 bg-zinc-400 animate-pulse" />
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 错误提示 */}
      {submitMutation.isError && (
        <div className="px-4 py-2 bg-rose-50 text-rose-600 text-sm border-t border-rose-200">
          发送失败：{(submitMutation.error as Error).message}
        </div>
      )}

      {/* 底部输入区 */}
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