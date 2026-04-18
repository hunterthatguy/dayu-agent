import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface DataTableProps<T> {
  columns: { key: string; header: string; render?: (row: T) => ReactNode }[];
  data: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export default function DataTable<T>({
  columns,
  data,
  rowKey,
  onRowClick,
  emptyMessage = "暂无数据",
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-zinc-500">{emptyMessage}</div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-zinc-200">
          {columns.map((col) => (
            <th
              key={col.key}
              className="px-3 py-2 text-left font-medium text-zinc-600"
            >
              {col.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row) => (
          <tr
            key={rowKey(row)}
            className={cn(
              "border-b border-zinc-100 hover:bg-zinc-50 transition-colors",
              onRowClick && "cursor-pointer",
            )}
            onClick={() => onRowClick?.(row)}
          >
            {columns.map((col) => (
              <td key={col.key} className="px-3 py-2 text-zinc-900">
                {col.render
                  ? col.render(row)
                  : String((row as Record<string, unknown>)[col.key] ?? "-")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}