import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { subscribePipelineProgress } from "@/lib/sse";
import PipelineGraph from "@/components/shared/PipelineGraph";
import type { PipelineProgressView } from "@/types/api";

export default function UploadPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"ticker" | "file">("ticker");
  const [ticker, setTicker] = useState("");
  const [market, setMarket] = useState("US");
  const [overwrite, setOverwrite] = useState(false);
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<PipelineProgressView | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

    setLoading(true);
    setError(null);
    setProgress(null);

    try {
      const result = await api.upload.manualUpload({
        ticker: normalizedTicker,
        market,
        overwrite,
      });

      // 开始订阅进度
      const cleanup = subscribePipelineProgress(
        result.run_id,
        result.ticker,
        result.session_id,
        (view) => {
          setProgress(view);
          setLoading(false);
          if (view.terminal_state === "succeeded") {
            setTimeout(() => navigate(`/portfolio/${view.ticker}`), 1000);
          }
        },
        () => {
          setError("进度订阅失败");
          setLoading(false);
        },
      );

      cleanupRef.current = cleanup;
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
      setLoading(false);
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

    setLoading(true);
    setError(null);
    setProgress(null);

    try {
      const result = await api.upload.uploadFiles(normalizedTicker, files);

      // 开始订阅进度
      const cleanup = subscribePipelineProgress(
        result.run_id,
        result.ticker,
        result.session_id,
        (view) => {
          setProgress(view);
          setLoading(false);
          if (view.terminal_state === "succeeded") {
            setTimeout(() => navigate(`/portfolio/${view.ticker}`), 1000);
          }
        },
        () => {
          setError("进度订阅失败");
          setLoading(false);
        },
      );

      cleanupRef.current = cleanup;
    } catch (err) {
      setError(err instanceof Error ? err.message : "文件上传失败");
      setLoading(false);
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
            className="w-full px-3 py-2 text-sm border border-zinc-200 rounded-md focus:outline-none focus:border-zinc-400"
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
                className="w-full px-3 py-2 text-sm border border-zinc-200 rounded-md"
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
              />
              覆盖已有数据
            </label>

            {error && <div className="text-sm text-rose-600">{error}</div>}

            <button
              type="submit"
              disabled={loading || !ticker.trim()}
              className="w-full px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded-md hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "提交中..." : "开始下载"}
            </button>
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
                className="w-full text-sm text-zinc-600 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200"
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
                  className="text-xs text-zinc-400 hover:text-zinc-600 mt-1"
                >
                  清除选择
                </button>
              </div>
            )}

            {error && <div className="text-sm text-rose-600">{error}</div>}

            <button
              type="submit"
              disabled={loading || !ticker.trim() || !files || files.length === 0}
              className="w-full px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded-md hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "上传中..." : "上传并处理"}
            </button>
          </form>
        )}
      </div>

      {/* 右侧进度 */}
      <div>
        {progress ? (
          <PipelineGraph
            stages={progress.stages}
            activeStageKey={progress.active_stage_key}
          />
        ) : (
          <div className="bg-white rounded-md border border-zinc-200 p-6 text-center text-sm text-zinc-500">
            {mode === "ticker"
              ? "输入 ticker 后点击「开始下载」从 SEC 下载财报"
              : "选择本地财报文件后点击「上传并处理」"}
          </div>
        )}
      </div>
    </div>
  );
}