export default function TopBar() {
  return (
    <header className="h-12 border-b border-zinc-200 bg-white flex items-center px-4">
      <div className="flex-1" />
      <div className="text-sm text-zinc-500">
        {/* 可扩展：用户信息、全局操作 */}
      </div>
    </header>
  );
}