import type { PipelineStageView } from "@/types/api";
import { cn } from "@/lib/cn";
import StatusBadge from "./StatusBadge";

interface PipelineGraphProps {
  stages: PipelineStageView[];
  activeStageKey: string;
}

export default function PipelineGraph({ stages, activeStageKey }: PipelineGraphProps) {
  const completedCount = stages.filter(
    (s) => s.state === "succeeded" || s.state === "skipped",
  ).length;
  const progress = (completedCount / stages.length) * 100;

  return (
    <div className="bg-white rounded-md border border-zinc-200 p-4">
      {/* 进度条 */}
      <div className="mb-4">
        <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-zinc-500">
          {completedCount} / {stages.length} 阶段完成
        </div>
      </div>

      {/* 阶段节点 */}
      <div className="flex items-center justify-between">
        {stages.map((stage, idx) => (
          <div key={stage.key} className="flex items-center">
            <div
              className={cn(
                "flex flex-col items-center",
                stage.key === activeStageKey && "opacity-100",
                stage.state === "pending" && "opacity-50",
              )}
            >
              <div
                className={cn(
                  "w-24 py-2 rounded-md text-center border",
                  stage.state === "running" && "border-blue-500 bg-blue-50",
                  stage.state === "succeeded" && "border-emerald-500 bg-emerald-50",
                  stage.state === "failed" && "border-rose-500 bg-rose-50",
                  stage.state === "skipped" && "border-zinc-300 bg-zinc-50",
                  stage.state === "pending" && "border-zinc-200 bg-zinc-50",
                )}
              >
                <div className="text-sm font-medium text-zinc-900">
                  {stage.title}
                </div>
                <StatusBadge state={stage.state} className="mt-1" />
              </div>
              {stage.message && (
                <div className="mt-1 text-xs text-zinc-500 text-center max-w-24 truncate">
                  {stage.message}
                </div>
              )}
            </div>
            {idx < stages.length - 1 && (
              <div className="w-4 h-0.5 bg-zinc-200 mx-1" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}