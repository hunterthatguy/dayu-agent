import type { PipelineStageView } from "@/types/api";
import { cn } from "@/lib/cn";
import StatusBadge from "./StatusBadge";

interface PipelineGraphProps {
  stages: PipelineStageView[];
  activeStageKey: string;
  onStageClick?: (stageKey: string) => void;
}

export default function PipelineGraph({ stages, activeStageKey, onStageClick }: PipelineGraphProps) {
  const completedCount = stages.filter(
    (s) => s.state === "succeeded" || s.state === "skipped",
  ).length;
  const runningCount = stages.filter((s) => s.state === "running").length;
  const totalCount = stages.length;

  // 进度百分比：已完成 + 正在进行的一半
  const progressPercent = ((completedCount + runningCount * 0.5) / totalCount) * 100;

  // 判断阶段是否可点击：succeeded状态可触发下一阶段
  const canTriggerNext = (stageKey: string, idx: number) => {
    const stage = stages[idx];
    // 当前阶段succeeded，且下一阶段pending，则可点击触发下一阶段
    if (stage.state === "succeeded" && idx < stages.length - 1) {
      const nextStage = stages[idx + 1];
      return nextStage.state === "pending";
    }
    return false;
  };

  const handleClick = (stageKey: string, idx: number) => {
    if (canTriggerNext(stageKey, idx) && onStageClick) {
      onStageClick(stages[idx + 1].key);
    }
  };

  return (
    <div className="bg-white rounded-md border border-zinc-200 p-4">
      {/* 进度条 */}
      <div className="mb-4">
        <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-zinc-500">
          {completedCount} / {totalCount} 阶段完成
          {runningCount > 0 && ` · 正在进行: ${runningCount}`}
        </div>
      </div>

      {/* 阶段节点 */}
      <div className="flex items-center justify-between gap-2">
        {stages.map((stage, idx) => (
          <div key={stage.key} className="flex items-center">
            <button
              onClick={() => handleClick(stage.key, idx)}
              disabled={!canTriggerNext(stage.key, idx)}
              className={cn(
                "flex flex-col items-center min-w-0 transition-all",
                stage.key === activeStageKey && "opacity-100",
                stage.state === "pending" && "opacity-50",
                canTriggerNext(stage.key, idx) && "cursor-pointer hover:opacity-80",
              )}
              title={canTriggerNext(stage.key, idx) ? "点击触发下一阶段" : undefined}
            >
              <div
                className={cn(
                  "w-24 py-2 px-1 rounded-md text-center border transition-all",
                  stage.state === "running" && "border-blue-500 bg-blue-50 animate-pulse",
                  stage.state === "succeeded" && "border-emerald-500 bg-emerald-50",
                  stage.state === "failed" && "border-rose-500 bg-rose-50",
                  stage.state === "skipped" && "border-zinc-300 bg-zinc-50",
                  stage.state === "pending" && "border-zinc-200 bg-zinc-50",
                  canTriggerNext(stage.key, idx) && "ring-2 ring-amber-400 ring-offset-1",
                )}
              >
                <div className="text-sm font-medium text-zinc-900 truncate">
                  {stage.title}
                </div>
                <StatusBadge state={stage.state} className="mt-1" />
              </div>
              {stage.message && (
                <div className="mt-1 text-xs text-zinc-500 text-center max-w-24 truncate">
                  {stage.message}
                </div>
              )}
              {/* 可点击提示 */}
              {canTriggerNext(stage.key, idx) && (
                <div className="mt-1 text-xs text-amber-600 font-medium">
                  点击继续 →
                </div>
              )}
            </button>
            {idx < stages.length - 1 && (
              <div className={cn(
                "w-4 h-0.5 mx-1 transition-all",
                stages[idx].state === "succeeded" ? "bg-emerald-400" : "bg-zinc-200",
              )} />
            )}
          </div>
        ))}
      </div>

      {/* 分析结果展示（当analyze阶段完成时） */}
      {stages[3]?.state === "succeeded" && stages[3]?.message && (
        <div className="mt-4 p-3 bg-zinc-50 rounded-md border border-zinc-200">
          <div className="text-sm font-medium text-zinc-900 mb-2">维度分析结果</div>
          <div className="text-sm text-zinc-600">{stages[3].message}</div>
        </div>
      )}
    </div>
  );
}