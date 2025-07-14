"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, Settings, User, X } from "lucide-react";

type AccountMenuUser = { nickname: string; phone: string; avatarText: string };

export default function AccountMenu({ user }: { user?: AccountMenuUser | null }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  const u = user || { nickname: "", phone: "", avatarText: "" };

  return (
    <div ref={ref} className="relative w-full">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-[0_14px_35px_rgba(15,23,42,0.05)] transition hover:bg-slate-50 cursor-pointer"
      >
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[21px] font-black text-white shadow-lg shadow-green-600/20">
          {u.avatarText || u.nickname?.[0] || "?"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[16px] font-black text-slate-900">{u.nickname || "用户"}</div>
          <div className="truncate text-[12px] font-semibold text-slate-500">{u.phone || ""}</div>
        </div>
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-full rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl z-50">
          <button onClick={() => { router.push("/profile"); setOpen(false); }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
          ><User className="h-4 w-4 text-slate-400" />个人中心</button>
          <button onClick={() => { router.push("/settings"); setOpen(false); }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
          ><Settings className="h-4 w-4 text-slate-400" />账号设置</button>
          <button onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold text-red-500 transition hover:bg-red-50"
          ><LogOut className="h-4 w-4" />退出登录</button>
        </div>
      )}
    </div>
  );
}
