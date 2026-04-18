import { cn } from "@/lib/cn";

interface EmptyStateProps {
  message?: string;
  className?: string;
}

export default function EmptyState({
  message = "暂无数据",
  className,
}: EmptyStateProps) {
  return (
    <div className={cn("text-center py-12 text-sm text-zinc-500", className)}>
      {message}
    </div>
  );
}