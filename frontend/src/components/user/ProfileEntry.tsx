"use client";

import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2 } from "lucide-react";

type ProfileEntryProps = {
  user?: { nickname?: string; phone?: string; avatarText?: string } | null;
  statusText?: string;
  detailText?: string;
  loading?: boolean;
};

export default function ProfileEntry({
  user,
  statusText = "状态良好",
  detailText = "点击进入个人中心",
  loading = false,
}: ProfileEntryProps) {
  const router = useRouter();
  const avatarText = user?.avatarText || user?.nickname?.slice(0, 1) || user?.phone?.slice(-2) || "我";

  return (
    <button
      type="button"
      onClick={() => router.push("/profile")}
      className="flex items-center gap-4 rounded-2xl px-2 py-1 text-left transition hover:bg-slate-50 cursor-pointer"
    >
      <div className="text-right">
        <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          {statusText}
        </div>
        <div className="text-[14px] font-semibold text-slate-500">{detailText}</div>
      </div>
      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[24px] font-black text-white shadow-xl shadow-green-600/20">
        {avatarText}
      </div>
    </button>
  );
}
