import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";

interface KeyMetricProps {
  label: string;
  value: number | string;
  unit?: string;
  className?: string;
}

export default function KeyMetric({
  label,
  value,
  unit,
  className,
}: KeyMetricProps) {
  const displayValue =
    typeof value === "number" ? formatNumber(value) : value;

  return (
    <div className={cn("bg-white rounded-md p-4 border border-zinc-200", className)}>
      <div className="text-xs text-zinc-500 mb-1">{label}</div>
      <div className="text-lg font-semibold text-zinc-900 tabular-nums">
        {displayValue}
        {unit && <span className="text-sm text-zinc-500 ml-1">{unit}</span>}
      </div>
    </div>
  );
}