import { NavLink, Outlet } from "react-router-dom";

const groups = [
  {
    label: "总览",
    items: [
      { to: "/", label: "工作台", icon: HomeIcon },
      { to: "/spaces", label: "空间", icon: SpaceIcon },
    ],
  },
  {
    label: "资产",
    items: [
      { to: "/entities", label: "实体库", icon: BoxIcon },
      { to: "/search", label: "检索溯源", icon: SearchIcon },
      { to: "/ask", label: "复盘问答", icon: ChatIcon },
      { to: "/reports", label: "复盘报告", icon: FileIcon },
    ],
  },
  {
    label: "接入",
    items: [{ to: "/import", label: "导入会议", icon: ImportIcon }],
  },
];

export function AppShell() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-[220px] shrink-0 bg-white/90 backdrop-blur border-r border-line sticky top-0 h-screen flex flex-col">
        <div className="px-5 pt-7 pb-6">
          <div className="font-serif text-[22px] font-bold tracking-tight text-brand">会议资产</div>
          <div className="text-[12px] text-text-sub mt-1">决策底账 · 可溯源</div>
        </div>
        <nav className="px-3 flex-1 space-y-5 overflow-auto">
          {groups.map((g) => (
            <div key={g.label}>
              <div className="px-3 mb-1.5 text-[11px] tracking-wider text-text-sub">{g.label}</div>
              <div className="space-y-0.5">
                {g.items.map((it) => (
                  <NavLink
                    key={it.to}
                    to={it.to}
                    end={it.to === "/"}
                    className={({ isActive }) =>
                      `nav-link ${isActive ? "text-brand bg-[#F0F5FF]" : "text-text-main hover:text-brand hover:bg-[#F8FAFF]"}`
                    }
                  >
                    <it.icon />
                    {it.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="px-5 py-5 text-[12px] text-text-sub border-t border-line">POC 单用户 · 无登录</div>
      </aside>
      <main className="flex-1 min-w-0">
        <div className="max-w-[1200px] mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function HomeIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z" />
    </svg>
  );
}
function SpaceIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="7" height="7" rx="1.5" />
      <rect x="14" y="4" width="7" height="7" rx="1.5" />
      <rect x="3" y="13" width="7" height="7" rx="1.5" />
      <rect x="14" y="13" width="7" height="7" rx="1.5" />
    </svg>
  );
}
function BoxIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 21 7.5 12 12 3 7.5 12 3Z" />
      <path d="M21 7.5V16.5L12 21M3 7.5V16.5L12 21" />
    </svg>
  );
}
function SearchIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}
function ChatIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 18.5 4 21l3.2-1.2A9 9 0 1 0 5 18.5Z" />
    </svg>
  );
}
function FileIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v6h6M9 13h6M9 17h6" />
    </svg>
  );
}
function ImportIcon() {
  return (
    <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 4v10" />
      <path d="m8 10 4 4 4-4" />
      <path d="M5 18h14" />
    </svg>
  );
}
