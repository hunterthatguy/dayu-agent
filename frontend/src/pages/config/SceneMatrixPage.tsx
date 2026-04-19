import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import DataTable from "@/components/shared/DataTable";
import EmptyState from "@/components/shared/EmptyState";
import type { SceneMatrixRowView } from "@/types/api";
import { cn } from "@/lib/cn";
import { X } from "lucide-react";

export default function SceneMatrixPage() {
  const queryClient = useQueryClient();
  const [selectedScene, setSelectedScene] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: matrix, isLoading: matrixLoading, error: matrixError } = useQuery({
    queryKey: ["scene-matrix"],
    queryFn: api.config.getSceneMatrix,
  });

  const { data: modelRequirements } = useQuery({
    queryKey: ["model-requirements"],
    queryFn: api.settings.listModelRequirements,
  });

  const updateMutation = useMutation({
    mutationFn: ({ sceneName, modelName }: { sceneName: string; modelName: string }) =>
      api.settings.updateSceneDefaultModel(sceneName, modelName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scene-matrix"] });
      setSelectedScene(null);
      setError(null);
    },
    onError: (err: ApiError) => {
      setError(err.message);
    },
  });

  if (matrixLoading) return <div className="text-sm text-zinc-500">加载中...</div>;
  if (matrixError) return <div className="text-sm text-rose-600">加载失败</div>;

  if (!matrix) return <EmptyState message="无数据" />;

  const modelAvailability = new Map<string, boolean>();
  if (modelRequirements) {
    for (const req of modelRequirements) {
      modelAvailability.set(req.model_name, req.is_available);
    }
  }

  const columns = [
    { key: "scene_name", header: "Scene" },
    { key: "default_model", header: "默认模型" },
    ...matrix.all_models.map((model) => ({
      key: model,
      header: model,
      render: (row: SceneMatrixRowView) => {
        const option = row.allowed_models.find((m) => m.model_name === model);
        if (!option) return <span className="text-zinc-300">-</span>;
        const isAvailable = modelAvailability.get(model) ?? false;
        const isDefault = option.is_default;

        if (!isAvailable) {
          return (
            <span className="text-zinc-300 cursor-not-allowed" title="需要配置 API Key">
              ○
            </span>
          );
        }

        if (isDefault) {
          return (
            <button
              className="text-emerald-600 cursor-default"
              title="当前默认模型"
            >
              ●
            </button>
          );
        }

        return (
          <button
            onClick={() => handleModelSelect(row.scene_name, model)}
            className={cn(
              "text-zinc-400 hover:text-zinc-900 hover:bg-zinc-50 px-1 rounded",
              selectedScene === row.scene_name && "bg-zinc-100",
            )}
            title="点击切换为默认模型"
          >
            ○
          </button>
        );
      },
    })),
  ];

  const handleModelSelect = (sceneName: string, modelName: string) => {
    if (!modelAvailability.get(modelName)) {
      setError(`模型 ${modelName} 需要先配置对应的 API Key`);
      return;
    }
    setSelectedScene(sceneName);
    updateMutation.mutate({ sceneName, modelName });
  };

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">Scene × 模型矩阵</h2>
        <div className="text-sm text-zinc-500">
          ● = 默认模型 · ○ = 可选模型 · - = 未声明
        </div>
        <div className="text-sm text-zinc-400 mt-1">
          点击可选模型切换默认模型（需先配置 API Key）
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-md text-sm text-rose-600">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-rose-400 hover:text-rose-600">
            <X className="w-4 h-4 inline" />
          </button>
        </div>
      )}

      {updateMutation.isPending && (
        <div className="mb-4 p-3 bg-zinc-50 border border-zinc-200 rounded-md text-sm text-zinc-600">
          正在更新默认模型...
        </div>
      )}

      <div className="bg-white rounded-md border border-zinc-200 overflow-hidden">
        <DataTable
          columns={columns}
          data={matrix.rows}
          rowKey={(row) => row.scene_name}
        />
      </div>
    </div>
  );
}