import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { subscribePipelineProgress } from "@/lib/sse";
import PipelineGraph from "@/components/shared/PipelineGraph";
import type { PipelineProgressView, PipelineStageView } from "@/types/api";

// 进度持久化 localStorage key
const PROGRESS_STORAGE_KEY = "dayu_upload_progress";

// 预定义的阶段模板（用于立即显示进度框架）
const INITIAL_STAGES: PipelineStageView[] = [
  { key: "resolve", title: "解析 ticker", state: "pending", message: "", started_at: "", finished_at: "" },
  { key: "download", title: "下载财报", state: "pending", message: "", started_at: "", finished_at: "" },
  { key: "process", title: "解析与抽取", state: "pending", message: "", started_at: "", finished_at: "" },
  { key: "analyze", title: "维度分析", state: "pending", message: "", started_at: "", finished_at: "" },
];

// 创建初始进度视图（点击按钮后立即显示）
function createInitialProgress(ticker: string, sessionId: string): PipelineProgressView {
  return {
    ticker,
    run_id: sessionId,
    session_id: sessionId,
    stages: INITIAL_STAGES,
    active_stage_key: "resolve",
    terminal_state: "running",
    updated_at: new Date().toISOString(),
  };
}

// 从 localStorage 加载进度
function loadProgress(): PipelineProgressView | null {
  try {
    const stored = localStorage.getItem(PROGRESS_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as PipelineProgressView;
      // 只有 running 状态才恢复
      if (parsed.terminal_state === "running") {
        return parsed;
      }
    }
  } catch {
    // ignore
  }
  return null;
}

// 保存进度到 localStorage
function saveProgress(progress: PipelineProgressView): void {
  try {
    localStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify(progress));
    // 非 running 状态时清除
    if (progress.terminal_state !== "running") {
      localStorage.removeItem(PROGRESS_STORAGE_KEY);
    }
  } catch {
    // ignore
  }
}

// 清除进度
function clearProgress(): void {
  try {
    localStorage.removeItem(PROGRESS_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export default function UploadPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"ticker" | "file">("ticker");
  const [ticker, setTicker] = useState("");
  const [market, setMarket] = useState("US");
  const [overwrite, setOverwrite] = useState(false);
  const [files, setFiles] = useState<FileList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<PipelineProgressView | null>(null);
  const [analysisResult, setAnalysisResult] = useState<{
    summary: string;
    insights: string[];
  } | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const sessionIdRef = useRef<string>("");

  // 判断是否正在执行
  const isRunning = progress?.terminal_state === "running";

  // 判断是否已失败/取消
  const hasFailed = progress?.terminal_state === "failed" || progress?.terminal_state === "cancelled";

  // 重置任务状态
  const handleReset = () => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    clearProgress();
    setProgress(null);
    setError(null);
    setAnalysisResult(null);
    sessionIdRef.current = "";
  };

  // 处理阶段点击（手动触发下一阶段）
  const handleStageClick = async (stageKey: string) => {
    if (!progress || !sessionIdRef.current) return;

    const currentTicker = progress.ticker;

    if (stageKey === "process") {
      // 触发解析与抽取阶段
      try {
        setError(null);
        const result = await api.upload.triggerProcess({
          ticker: currentTicker,
          session_id: sessionIdRef.current,
        });

        // 更新sessionId（新阶段有新的session）
        sessionIdRef.current = result.session_id;

        // 重新订阅SSE
        cleanupRef.current?.();
        const cleanup = subscribePipelineProgress(
          result.run_id,
          result.ticker,
          result.session_id,
          handleProgressUpdate,
          () => {
            setError("进度订阅失败");
          },
        );
        cleanupRef.current = cleanup;
      } catch (err) {
        setError(err instanceof Error ? err.message : "触发解析与抽取失败");
      }
    } else if (stageKey === "analyze") {
      // 触发维度分析阶段
      try {
        setError(null);
        const result = await api.upload.triggerAnalyze({
          ticker: currentTicker,
          session_id: sessionIdRef.current,
        });

        // 更新进度视图的analyze阶段为succeeded
        setProgress((prev) => {
          if (!prev) return null;
          const newStages = prev.stages.map((s) =>
            s.key === "analyze"
              ? {
                  ...s,
                  state: "succeeded" as const,
                  message: result.summary,
                  finished_at: new Date().toISOString(),
                }
              : s,
          );
          return {
            ...prev,
            stages: newStages,
            active_stage_key: "",
            terminal_state: "succeeded" as const,
          };
        });

        // 存储分析结果
        setAnalysisResult({
          summary: result.summary,
          insights: result.insights,
        });

        // 清理
        clearProgress();
        cleanupRef.current?.();
      } catch (err) {
        setError(err instanceof Error ? err.message : "触发维度分析失败");
      }
    }
  };

  // 处理进度更新回调
  const handleProgressUpdate = (view: PipelineProgressView) => {
    setProgress(view);
    saveProgress(view);

    // 成功完成
    if (view.terminal_state === "succeeded") {
      // 判断是download还是process完成
      const downloadStage = view.stages.find((s) => s.key === "download");
      const processStage = view.stages.find((s) => s.key === "process");

      // download完成后不自动跳转，等待用户点击触发process
      if (downloadStage?.state === "succeeded" && processStage?.state === "pending") {
        // 保持进度状态，等待用户点击
      } else if (processStage?.state === "succeeded") {
        // process完成，等待用户点击触发analyze
      }
    }

    // 失败或取消：设置错误信息但不清除进度（让用户看到失败状态）
    if (view.terminal_state === "failed") {
      setError("任务执行失败");
    }
    if (view.terminal_state === "cancelled") {
      setError("任务已取消");
    }
  };

  // 页面加载时恢复进度
  useEffect(() => {
    const storedProgress = loadProgress();
    if (storedProgress) {
      setProgress(storedProgress);
      // 重新订阅 SSE
      const cleanup = subscribePipelineProgress(
        storedProgress.session_id,
        storedProgress.ticker,
        storedProgress.session_id,
        handleProgressUpdate,
        () => {
          setError("进度订阅失败");
          handleReset();
        },
      );
      cleanupRef.current = cleanup;
    }
  }, [navigate]);

  // 清理 SSE 连接
  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  const handleTickerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const normalizedTicker = ticker.trim().toUpperCase();
    if (!normalizedTicker) {
      setError("ticker 不能为空");
      return;
    }

    setError(null);

    try {
      const result = await api.upload.manualUpload({
        ticker: normalizedTicker,
        market,
        overwrite,
      });

      // 保存sessionId供后续阶段触发
      sessionIdRef.current = result.session_id;

      // 点击后立即显示进度框架（缓解用户焦虑）
      const initialProgress = createInitialProgress(normalizedTicker, result.session_id);
      setProgress(initialProgress);
      saveProgress(initialProgress);

      // 开始订阅进度
      const cleanup = subscribePipelineProgress(
        result.run_id,
        result.ticker,
        result.session_id,
        handleProgressUpdate,
        () => {
          setError("进度订阅失败");
          handleReset();
        },
      );

      cleanupRef.current = cleanup;
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
      handleReset();
    }
  };

  const handleFileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const normalizedTicker = ticker.trim().toUpperCase();
    if (!normalizedTicker) {
      setError("ticker 不能为空");
      return;
    }
    if (!files || files.length === 0) {
      setError("请选择文件");
      return;
    }

    setError(null);

    try {
      const result = await api.upload.uploadFiles(normalizedTicker, files);

      // 保存sessionId供后续阶段触发
      sessionIdRef.current = result.session_id;

      // 点击后立即显示进度框架（缓解用户焦虑）
      const initialProgress = createInitialProgress(normalizedTicker, result.session_id);
      setProgress(initialProgress);
      saveProgress(initialProgress);

      // 开始订阅进度
      const cleanup = subscribePipelineProgress(
        result.run_id,
        result.ticker,
        result.session_id,
        handleProgressUpdate,
        () => {
          setError("进度订阅失败");
          handleReset();
        },
      );

      cleanupRef.current = cleanup;
    } catch (err) {
      setError(err instanceof Error ? err.message : "文件上传失败");
      handleReset();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(e.target.files);
  };

  const handleRemoveFiles = () => {
    setFiles(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      {/* 左侧表单 */}
      <div className="bg-white rounded-md border border-zinc-200 p-6">
        <h2 className="text-lg font-semibold text-zinc-900 mb-4">上传</h2>

        {/* 模式切换 */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode("ticker")}
            className={`px-3 py-1 text-sm rounded ${
              mode === "ticker"
                ? "bg-zinc-900 text-white"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            从 SEC 下载
          </button>
          <button
            onClick={() => setMode("file")}
            className={`px-3 py-1 text-sm rounded ${
              mode === "file"
                ? "bg-zinc-900 text-white"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            上传本地文件
          </button>
        </div>

        {/* 公共 ticker 输入 */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-zinc-700 mb-1">
            Ticker
          </label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="如 AAPL"
            disabled={isRunning}
            className="w-full px-3 py-2 text-sm border border-zinc-200 rounded-md focus:outline-none focus:border-zinc-400 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {/* ticker 模式表单 */}
        {mode === "ticker" && (
          <form onSubmit={handleTickerSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                市场
              </label>
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                disabled={isRunning}
                className="w-full px-3 py-2 text-sm border border-zinc-200 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="US">US</option>
                <option value="HK">HK</option>
                <option value="CN">CN</option>
              </select>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
                disabled={isRunning}
                className="disabled:opacity-50"
              />
              覆盖已有数据
            </label>

            {error && (
              <div className="text-sm text-rose-600 p-2 bg-rose-50 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={isRunning || !ticker.trim()}
                className="flex-1 px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded-md hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRunning ? "执行中..." : "开始下载"}
              </button>
              {(isRunning || hasFailed) && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2 text-sm font-medium bg-zinc-100 text-zinc-700 rounded-md hover:bg-zinc-200"
                >
                  重置任务
                </button>
              )}
            </div>
          </form>
        )}

        {/* 文件上传模式表单 */}
        {mode === "file" && (
          <form onSubmit={handleFileSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">
                选择财报文件
              </label>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.htm,.html,.txt,.md"
                onChange={handleFileChange}
                disabled={isRunning}
                className="w-full text-sm text-zinc-600 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <p className="text-xs text-zinc-400 mt-1">
                支持 PDF, Word, PPT, Excel, HTML, TXT, Markdown
              </p>
            </div>

            {files && files.length > 0 && (
              <div className="bg-zinc-50 p-2 rounded">
                <div className="text-xs text-zinc-500 mb-1">
                  已选择 {files.length} 个文件：
                </div>
                <ul className="text-xs text-zinc-600 space-y-1">
                  {Array.from(files).map((file, i) => (
                    <li key={i}>{file.name}</li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={handleRemoveFiles}
                  disabled={isRunning}
                  className="text-xs text-zinc-400 hover:text-zinc-600 mt-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  清除选择
                </button>
              </div>
            )}

            {error && (
              <div className="text-sm text-rose-600 p-2 bg-rose-50 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={isRunning || !ticker.trim() || !files || files.length === 0}
                className="flex-1 px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded-md hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRunning ? "执行中..." : "上传并处理"}
              </button>
              {(isRunning || hasFailed) && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2 text-sm font-medium bg-zinc-100 text-zinc-700 rounded-md hover:bg-zinc-200"
                >
                  重置任务
                </button>
              )}
            </div>
          </form>
        )}
      </div>

      {/* 右侧进度 */}
      <div className="space-y-4">
        {progress ? (
          <PipelineGraph
            stages={progress.stages}
            activeStageKey={progress.active_stage_key}
            onStageClick={handleStageClick}
          />
        ) : (
          <div className="bg-white rounded-md border border-zinc-200 p-6 text-center text-sm text-zinc-500">
            {mode === "ticker"
              ? "输入 ticker 后点击「开始下载」从 SEC 下载财报"
              : "选择本地财报文件后点击「上传并处理」"}
          </div>
        )}

        {/* 分析结果展示 */}
        {analysisResult && (
          <div className="bg-white rounded-md border border-zinc-200 p-4">
            <h3 className="text-sm font-semibold text-zinc-900 mb-2">维度分析结果</h3>
            <div className="text-sm text-zinc-600 mb-3">{analysisResult.summary}</div>
            {analysisResult.insights.length > 0 && (
              <div>
                <div className="text-xs text-zinc-500 mb-1">关键洞察:</div>
                <ul className="text-xs text-zinc-600 space-y-1">
                  {analysisResult.insights.map((insight, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-emerald-500">•</span>
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <button
              onClick={() => navigate(`/portfolio/${progress?.ticker || ticker}`)}
              className="mt-3 text-xs text-zinc-600 hover:text-zinc-900 underline"
            >
              查看 Portfolio 详情
            </button>
          </div>
        )}
      </div>
    </div>
  );
}