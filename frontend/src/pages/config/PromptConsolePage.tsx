import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import EmptyState from "@/components/shared/EmptyState";
import type { PromptDocumentView, PromptDocumentDetailView } from "@/types/api";

type CategoryKey = "manifests" | "scenes" | "base" | "tasks";

export default function PromptConsolePage() {
  const { path } = useParams<{ path?: string }>();
  const queryClient = useQueryClient();

  // 获取所有 prompt 文档列表
  const { data: documents, isLoading } = useQuery({
    queryKey: ["prompt-documents"],
    queryFn: api.config.listPromptDocuments,
  });

  // 选中的文档路径
  const [selectedPath, setSelectedPath] = useState<string | null>(
    path ?? null,
  );

  // 编辑内容
  const [editContent, setEditContent] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);

  // 获取选中文档详情
  const { data: documentDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["prompt-document", selectedPath],
    queryFn: () =>
      selectedPath ? api.config.getPromptDocument(selectedPath) : null,
    enabled: selectedPath !== null,
  });

  // 更新文档
  const updateMutation = useMutation({
    mutationFn: (content: string) =>
      selectedPath ? api.config.updatePromptDocument(selectedPath, content) : null,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompt-document", selectedPath] });
      setIsEditing(false);
    },
  });

  // 同步编辑内容
  useEffect(() => {
    if (documentDetail && !isEditing) {
      setEditContent(documentDetail.content);
    }
  }, [documentDetail, isEditing]);

  // 按类别分组文档
  const groupedDocuments: Record<CategoryKey, PromptDocumentView[]> = {
    manifests: [],
    scenes: [],
    base: [],
    tasks: [],
  };

  if (documents) {
    for (const doc of documents) {
      const category = doc.category as CategoryKey;
      if (groupedDocuments[category]) {
        groupedDocuments[category].push(doc);
      }
    }
  }

  const handleSave = () => {
    if (editContent.trim()) {
      updateMutation.mutate(editContent);
    }
  };

  const handleCancel = () => {
    setEditContent(documentDetail?.content ?? "");
    setIsEditing(false);
  };

  if (isLoading) {
    return <div className="text-sm text-zinc-500">加载中...</div>;
  }

  return (
    <div className="flex h-[calc(100vh-120px)]">
      {/* 左侧文件树 */}
      <aside className="w-48 border-r border-zinc-200 overflow-auto">
        <div className="p-3">
          <div className="text-sm font-semibold text-zinc-900 mb-2">
            Prompt 资产
          </div>
          {(["manifests", "scenes", "base", "tasks"] as CategoryKey[]).map(
            (category) => (
              <div key={category} className="mb-3">
                <div className="text-xs text-zinc-500 uppercase mb-1">
                  {category}
                </div>
                <ul className="space-y-1">
                  {groupedDocuments[category].map((doc) => (
                    <li key={doc.relative_path}>
                      <button
                        onClick={() => setSelectedPath(doc.relative_path)}
                        className={`w-full text-left px-2 py-1 text-sm rounded ${
                          selectedPath === doc.relative_path
                            ? "bg-zinc-100 text-zinc-900"
                            : "text-zinc-600 hover:bg-zinc-50"
                        }`}
                      >
                        {doc.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ),
          )}
        </div>
      </aside>

      {/* 中间编辑区 */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {selectedPath === null ? (
          <div className="flex items-center justify-center h-full">
            <EmptyState message="请从左侧选择一个文档" />
          </div>
        ) : detailLoading ? (
          <div className="flex items-center justify-center h-full text-sm text-zinc-500">
            加载中...
          </div>
        ) : documentDetail ? (
          <>
            {/* 编辑器头部 */}
            <div className="px-4 py-2 border-b border-zinc-200 flex items-center justify-between">
              <div className="text-sm text-zinc-600">
                {documentDetail.document.relative_path}
              </div>
              <div className="flex gap-2">
                {!isEditing ? (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-2 py-1 text-sm bg-zinc-100 text-zinc-700 rounded hover:bg-zinc-200"
                  >
                    编辑
                  </button>
                ) : (
                  <>
                    <button
                      onClick={handleCancel}
                      className="px-2 py-1 text-sm text-zinc-600 hover:text-zinc-900"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={updateMutation.isPending || !editContent.trim()}
                      className="px-2 py-1 text-sm bg-zinc-900 text-white rounded hover:bg-zinc-800 disabled:opacity-50"
                    >
                      {updateMutation.isPending ? "保存中..." : "保存"}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* 编辑器 */}
            <div className="flex-1 overflow-auto p-4">
              {isEditing ? (
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full h-full p-3 border border-zinc-200 rounded text-sm font-mono resize-none focus:outline-none focus:ring-1 focus:ring-zinc-300"
                  spellCheck={false}
                />
              ) : (
                <pre className="text-sm font-mono whitespace-pre-wrap text-zinc-800">
                  {documentDetail.content}
                </pre>
              )}
            </div>

            {/* 错误提示 */}
            {updateMutation.isError && (
              <div className="px-4 py-2 bg-rose-50 text-rose-600 text-sm border-t border-rose-200">
                保存失败：{(updateMutation.error as Error).message}
              </div>
            )}
          </>
        ) : (
          <div className="flex items-center justify-center h-full">
            <EmptyState message="文档不存在或无权限访问" />
          </div>
        )}
      </main>

      {/* 右侧信息面板 */}
      {documentDetail && (
        <aside className="w-56 border-l border-zinc-200 p-3 overflow-auto">
          <div className="text-sm font-semibold text-zinc-900 mb-3">
            文档信息
          </div>
          <div className="space-y-2 text-sm">
            <div>
              <span className="text-zinc-500">类别：</span>
              <span className="text-zinc-900">
                {documentDetail.document.category}
              </span>
            </div>
            <div>
              <span className="text-zinc-500">名称：</span>
              <span className="text-zinc-900">
                {documentDetail.document.name}
              </span>
            </div>
            <div>
              <span className="text-zinc-500">大小：</span>
              <span className="text-zinc-900 tabular-nums">
                {documentDetail.document.size.toLocaleString()} 字节
              </span>
            </div>
            <div>
              <span className="text-zinc-500">更新：</span>
              <span className="text-zinc-900">
                {new Date(documentDetail.document.updated_at).toLocaleString()}
              </span>
            </div>
          </div>

          {documentDetail.document.category === "manifests" && (
            <div className="mt-4 pt-3 border-t border-zinc-200">
              <div className="text-xs text-zinc-500 mb-2">
                查看拼接后的系统提示
              </div>
              <button
                onClick={() => {
                  // 可扩展：打开 composition modal
                }}
                className="px-2 py-1 text-xs bg-zinc-100 text-zinc-700 rounded hover:bg-zinc-200"
              >
                查看 Composition
              </button>
            </div>
          )}
        </aside>
      )}
    </div>
  );
}