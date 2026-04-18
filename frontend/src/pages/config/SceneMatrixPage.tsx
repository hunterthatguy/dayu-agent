import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import DataTable from "@/components/shared/DataTable";
import EmptyState from "@/components/shared/EmptyState";
import type { SceneMatrixRowView } from "@/types/api";
import { cn } from "@/lib/cn";

export default function SceneMatrixPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["scene-matrix"],
    queryFn: api.config.getSceneMatrix,
  });

  if (isLoading) return <div className="text-sm text-zinc-500">加载中...</div>;
  if (error) return <div className="text-sm text-rose-600">加载失败</div>;

  const matrix = data;
  if (!matrix) return <EmptyState message="无数据" />;

  const columns = [
    { key: "scene_name", header: "Scene" },
    { key: "default_model", header: "默认模型" },
    ...matrix.all_models.map((model) => ({
      key: model,
      header: model,
      render: (row: SceneMatrixRowView) => {
        const option = row.allowed_models.find((m) => m.model_name === model);
        if (!option) return <span className="text-zinc-300">-</span>;
        if (option.is_default) {
          return <span className="text-emerald-600">●</span>;
        }
        return <span className="text-zinc-400">○</span>;
      },
    })),
  ];

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-900">Scene × 模型矩阵</h2>
        <div className="text-sm text-zinc-500">
          ● = 默认模型 · ○ = 可选模型 · - = 未声明
        </div>
      </div>

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