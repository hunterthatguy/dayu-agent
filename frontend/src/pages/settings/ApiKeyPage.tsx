import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { ApiKeyStatusResponse } from "@/types/api";
import { Eye, EyeOff, Check, ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";

const API_KEY_URLS: Record<string, string> = {
  MIMO_PLAN_API_KEY: "https://platform.mimo.ai",
  MIMO_API_KEY: "https://platform.mimo.ai",
  DEEPSEEK_API_KEY: "https://platform.deepseek.com",
  FMP_API_KEY: "https://financialmodelingprep.com",
  TAVILY_API_KEY: "https://tavily.com",
  SERPER_API_KEY: "https://serper.dev",
};

export default function ApiKeyPage() {
  const queryClient = useQueryClient();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: api.settings.listApiKeys,
  });

  const setMutation = useMutation({
    mutationFn: ({ keyName, value }: { keyName: string; value: string }) =>
      api.settings.setApiKey(keyName, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setEditingKey(null);
      setInputValue("");
      setError(null);
    },
    onError: (err: ApiError) => {
      setError(err.message);
    },
  });

  const clearMutation = useMutation({
    mutationFn: (keyName: string) => api.settings.clearApiKey(keyName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (err: ApiError) => {
      setError(err.message);
    },
  });

  if (isLoading) return <div className="text-sm text-zinc-500">加载中...</div>;

  const keys = data ?? [];

  const handleEdit = (keyName: string) => {
    setEditingKey(keyName);
    setInputValue("");
    setShowValue(false);
    setError(null);
  };

  const handleSave = () => {
    if (!editingKey || !inputValue.trim()) return;
    setMutation.mutate({ keyName: editingKey, value: inputValue.trim() });
  };

  const handleCancel = () => {
    setEditingKey(null);
    setInputValue("");
    setError(null);
  };

  const handleClear = (keyName: string) => {
    if (confirm("确定要清空该 API Key 吗？")) {
      clearMutation.mutate(keyName);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">API Keys 配置</h2>
        <div className="text-sm text-zinc-500">
          配置各服务 API Key，用于模型调用和数据获取
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-md text-sm text-rose-600">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {keys.map((key) => (
          <ApiKeyCard
            key={key.key_name}
            data={key}
            isEditing={editingKey === key.key_name}
            inputValue={inputValue}
            showValue={showValue}
            onEdit={() => handleEdit(key.key_name)}
            onSave={handleSave}
            onCancel={handleCancel}
            onClear={() => handleClear(key.key_name)}
            onInputChange={setInputValue}
            onToggleShow={() => setShowValue(!showValue)}
            isSaving={setMutation.isPending && editingKey === key.key_name}
            url={API_KEY_URLS[key.key_name]}
          />
        ))}
      </div>
    </div>
  );
}

interface ApiKeyCardProps {
  data: ApiKeyStatusResponse;
  isEditing: boolean;
  inputValue: string;
  showValue: boolean;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onClear: () => void;
  onInputChange: (value: string) => void;
  onToggleShow: () => void;
  isSaving: boolean;
  url: string;
}

function ApiKeyCard({
  data,
  isEditing,
  inputValue,
  showValue,
  onEdit,
  onSave,
  onCancel,
  onClear,
  onInputChange,
  onToggleShow,
  isSaving,
  url,
}: ApiKeyCardProps) {
  return (
    <div className="bg-white rounded-md border border-zinc-200 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium text-zinc-900">{data.display_name}</span>
            {data.is_configured ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs">
                <Check className="w-3 h-3" />
                已配置
              </span>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-500 text-xs">
                未配置
              </span>
            )}
          </div>
          <div className="text-sm text-zinc-500 mt-1">
            来源: {data.source === "env" ? "环境变量" : data.source === "file" ? "本地文件" : "未设置"}
          </div>
        </div>

        {!isEditing && (
          <div className="flex items-center gap-2">
            <button
              onClick={onEdit}
              className="px-3 py-1.5 text-sm text-zinc-600 hover:text-zinc-900 border border-zinc-200 rounded-md hover:bg-zinc-50"
            >
              编辑
            </button>
            {data.is_configured && (
              <button
                onClick={onClear}
                className="px-3 py-1.5 text-sm text-rose-600 hover:text-rose-700 border border-rose-200 rounded-md hover:bg-rose-50"
              >
                清空
              </button>
            )}
          </div>
        )}
      </div>

      {isEditing && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2">
            <input
              type={showValue ? "text" : "password"}
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder="输入 API Key"
              className="flex-1 px-3 py-2 text-sm border border-zinc-200 rounded-md focus:outline-none focus:ring-2 focus:ring-zinc-300"
            />
            <button
              onClick={onToggleShow}
              className="p-2 text-zinc-400 hover:text-zinc-600"
            >
              {showValue ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex items-center justify-between">
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700"
            >
              <ExternalLink className="w-3 h-3" />
              获取 API Key
            </a>

            <div className="flex items-center gap-2">
              <button
                onClick={onCancel}
                className="px-3 py-1.5 text-sm text-zinc-600 hover:text-zinc-900"
              >
                取消
              </button>
              <button
                onClick={onSave}
                disabled={!inputValue.trim() || isSaving}
                className={cn(
                  "px-3 py-1.5 text-sm rounded-md",
                  inputValue.trim() && !isSaving
                    ? "bg-zinc-900 text-white hover:bg-zinc-800"
                    : "bg-zinc-100 text-zinc-400 cursor-not-allowed",
                )}
              >
                {isSaving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}