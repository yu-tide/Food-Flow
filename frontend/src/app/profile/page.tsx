"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Circle,
  Home,
  Leaf,
  Loader2,
  LogOut,
  Save,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  UploadCloud,
  UserRound,
} from "lucide-react";
import AccountMenu from "@/components/user/AccountMenu";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

type UserData = {
  nickname?: string | null;
  phone?: string | null;
  avatarText?: string | null;
  target_calories?: number | null;
  target_protein?: number | null;
  target_carbs?: number | null;
  target_fat?: number | null;
  goal_type?: string | null;
  created_at?: string | null;
};

type UserProfile = {
  nickname: string;
  phone: string;
  avatarText: string;
  created_at?: string | null;
};

type DashboardToday = {
  consumedCalories: number | null;
  targetCalories: number | null;
};

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getLocalUser(): UserData {
  if (typeof window === "undefined") return {};

  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function normalizeUser(data: UserData, fallback: UserData = {}): UserProfile {
  const nickname = data.nickname || fallback.nickname || "";
  const phone = data.phone || fallback.phone || "";
  const avatarText =
    data.avatarText ||
    fallback.avatarText ||
    nickname?.slice(0, 1) ||
    phone?.slice(-2) ||
    "我";

  return {
    nickname,
    phone,
    avatarText,
    created_at: data.created_at || fallback.created_at || null,
  };
}

function adaptDashboardToday(raw: any, settings?: UserData | null): DashboardToday {
  const today = raw?.today ?? raw ?? {};

  return {
    consumedCalories: numberOrNull(
      today.consumedCalories ??
        today.consumed_calories ??
        today.calories ??
        today.total_calories,
    ),
    targetCalories: numberOrNull(
      today.targetCalories ??
        today.target_calories ??
        settings?.target_calories,
    ),
  };
}

function formatDateTime(value?: string | null) {
  if (!value) return "暂未提供";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂未提供";

  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function goalLabel(value?: string | null) {
  if (value === "lose") return "减脂";
  if (value === "gain") return "增肌";
  return "维持体重";
}

function formatTarget(value?: number | null, unit = "") {
  if (typeof value !== "number" || value <= 0) return "未设置";
  return `${value.toLocaleString()}${unit}`;
}

export default function ProfilePage() {
  const router = useRouter();

  const [user, setUser] = useState<UserProfile>(() =>
    normalizeUser(getLocalUser()),
  );
  const [settings, setSettings] = useState<UserData | null>(null);
  const [dash, setDash] = useState<DashboardToday>({
    consumedCalories: null,
    targetCalories: null,
  });

  const [nicknameDraft, setNicknameDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savedProfile, setSavedProfile] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const token = localStorage.getItem("token");

      if (!token) {
        router.push("/login");
        return;
      }

      try {
        const [settingsRes, dashboardRes] = await Promise.all([
          fetch(`${API_BASE}/api/users/me/settings`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE}/api/dashboard/summary`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        if (settingsRes.status === 401 || dashboardRes.status === 401) {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          router.push("/login");
          return;
        }

        if (!settingsRes.ok) {
          throw new Error("加载个人资料失败");
        }

        const settingsData = (await settingsRes.json()) as UserData;
        const dashboardData = dashboardRes.ok ? await dashboardRes.json() : null;

        if (cancelled) return;

        const nextUser = normalizeUser(settingsData, getLocalUser());

        setSettings(settingsData);
        setUser(nextUser);
        setNicknameDraft(nextUser.nickname);
        setDash(adaptDashboardToday(dashboardData, settingsData));

        localStorage.setItem("user", JSON.stringify(nextUser));
      } catch (err) {
        console.error("[Profile] load failed:", err);
        if (!cancelled) {
          if (err instanceof TypeError && err.message.includes("fetch")) {
            setError("后端服务不可用，请确认已启动 uvicorn");
          } else {
            setError("加载个人中心失败");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleSaveProfile = async () => {
    const nickname = nicknameDraft.trim();

    if (!nickname) {
      setError("昵称不能为空");
      return;
    }

    if (nickname.length > 20) {
      setError("昵称不能超过 20 个字符");
      return;
    }

    if (!settings) return;

    setSavingProfile(true);
    setSavedProfile(false);
    setError("");

    try {
      const token = localStorage.getItem("token");

      if (!token) {
        router.push("/login");
        return;
      }

      const payload = {
        ...settings,
        nickname,
      };

      const res = await fetch(`${API_BASE}/api/users/me/settings`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        router.push("/login");
        return;
      }

      if (!res.ok) {
        throw new Error("保存失败");
      }

      const contentType = res.headers.get("content-type") || "";
      const nextSettings = contentType.includes("application/json")
        ? ((await res.json()) as UserData)
        : payload;

      const nextUser = normalizeUser(nextSettings, {
        ...user,
        nickname,
      });

      setSettings(nextSettings);
      setUser(nextUser);
      setNicknameDraft(nextUser.nickname);
      localStorage.setItem("user", JSON.stringify(nextUser));

      setSavedProfile(true);
      setTimeout(() => setSavedProfile(false), 2500);
    } catch (err) {
      console.error("[Profile] save failed:", err);
      setError("保存失败，请确认后端是否支持修改昵称");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  return (
    <ProfilePageShell user={user}>
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-green-600" />
            <p className="mt-3 text-[15px] font-bold text-slate-500">
              正在加载个人中心...
            </p>
          </div>
        </div>
      ) : error && !settings ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Circle className="mx-auto h-10 w-10 text-slate-300" />
            <p className="mt-3 text-[15px] font-bold text-slate-500">
              {error}
            </p>
          </div>
        </div>
      ) : settings ? (
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto pb-6 pr-1">
          {error ? (
            <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
              {error}
            </p>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
            <div className="space-y-4">
              <ProfileOverviewCard
                user={user}
                settings={settings}
                dash={dash}
              />

              <BasicProfileCard
                user={user}
                nicknameDraft={nicknameDraft}
                saving={savingProfile}
                saved={savedProfile}
                onNicknameChange={(value) => {
                  setNicknameDraft(value);
                  setSavedProfile(false);
                  setError("");
                }}
                onSave={handleSaveProfile}
              />

              <GoalSummaryCard settings={settings} />
            </div>

            <div className="space-y-4">
              <AiInfoCard />
              <SecurityCard user={user} onLogout={handleLogout} />
            </div>
          </div>
        </div>
      ) : null}
    </ProfilePageShell>
  );
}

function ProfilePageShell({
  user,
  children,
}: {
  user: UserProfile;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#f8faf8] text-slate-950 lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={user} />

        <section className="min-w-0 bg-white lg:h-screen lg:overflow-hidden">
          <div className="mx-auto flex min-h-screen w-full max-w-[1480px] flex-col px-5 py-4 sm:px-6 lg:h-screen lg:min-h-0 lg:px-7">
            <ProfilePageHeader user={user} />
            {children}
          </div>
        </section>
      </div>
    </main>
  );
}

function ProfilePageHeader({ user }: { user: UserProfile }) {
  return (
    <header className="flex shrink-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="text-[28px] font-black leading-tight tracking-[-0.06em] text-slate-950 sm:text-[34px]">
          个人中心
        </h1>

        <p className="mt-1.5 text-[15px] font-semibold text-slate-500">
          管理你的账号资料、营养目标与 AI 分析偏好。
        </p>
      </div>

      <div className="flex items-center gap-4 rounded-2xl px-2 py-1">
        <div className="text-right">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            账号正常
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            {user.phone || "个人资料"}
          </div>
        </div>

        <div className="grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[24px] font-black text-white shadow-xl shadow-green-600/20">
          {user.avatarText || user.nickname?.[0] || "我"}
        </div>
      </div>
    </header>
  );
}

function AppLogo() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5">
      <div className="relative h-9 w-9 text-green-600">
        <Leaf className="absolute left-1 top-2 h-6 w-6 -rotate-[28deg] fill-green-500/15 stroke-[2.8]" />
        <Leaf className="absolute left-3.5 top-0 h-7 w-7 rotate-[22deg] fill-green-500/15 stroke-[2.8]" />
        <Leaf className="absolute left-[17px] top-[19px] h-5 w-5 rotate-[70deg] fill-green-500/15 stroke-[2.8]" />
      </div>

      <span className="text-[24px] font-black tracking-[-0.04em] text-green-700">
        FoodFlow
      </span>
    </Link>
  );
}

function Sidebar({ user }: { user: UserProfile }) {
  return (
    <aside className="hidden h-screen overflow-hidden border-r border-slate-200 bg-white px-4 py-5 lg:flex lg:flex-col">
      <AppLogo />

      <nav className="mt-7 space-y-2">
        <SidebarItem
          href="/dashboard"
          icon={<Home className="h-5 w-5" />}
          label="首页"
        />
        <SidebarItem
          href="/upload"
          icon={<UploadCloud className="h-5 w-5" />}
          label="上传"
        />
        <SidebarItem
          href="/records"
          icon={<ClipboardList className="h-5 w-5" />}
          label="记录"
        />
        <SidebarItem
          href="/statistics/weekly"
          icon={<BarChart3 className="h-5 w-5" />}
          label="每周统计"
        />
        <SidebarItem
          href="/settings"
          icon={<Settings className="h-5 w-5" />}
          label="设置"
        />
      </nav>

      <div className="mt-auto">
        <AccountMenu user={user || undefined} />
      </div>
    </aside>
  );
}

function SidebarItem({
  href,
  icon,
  label,
  active,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`flex h-[48px] items-center gap-4 rounded-xl px-4 text-[16px] font-black transition ${
        active
          ? "bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.08)]"
          : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
      }`}
    >
      <span className={active ? "text-green-600" : "text-slate-500"}>
        {icon}
      </span>
      {label}
    </Link>
  );
}

function CardShell({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-slate-200 bg-white shadow-[0_12px_30px_rgba(15,23,42,0.055)] ${className}`}
    >
      {children}
    </section>
  );
}

function SectionTitle({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="mb-5 flex items-start gap-3">
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-green-50 text-green-600">
        {icon}
      </div>

      <div>
        <h2 className="text-[19px] font-black tracking-[-0.04em] text-slate-950">
          {title}
        </h2>
        <p className="mt-1 text-[14px] font-semibold leading-6 text-slate-500">
          {desc}
        </p>
      </div>
    </div>
  );
}

function ProfileOverviewCard({
  user,
  settings,
  dash,
}: {
  user: UserProfile;
  settings: UserData;
  dash: DashboardToday;
}) {
  return (
    <CardShell className="p-5">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[28px] font-black text-white shadow-lg shadow-green-600/20">
            {user.avatarText || user.nickname?.[0] || "我"}
          </div>

          <div>
            <div className="text-[24px] font-black tracking-[-0.05em] text-slate-950">
              {user.nickname || "FoodFlow 用户"}
            </div>

            <div className="mt-1 text-[14px] font-semibold text-slate-500">
              {user.phone || "暂未获取手机号"}
            </div>

            <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-[12px] font-black text-green-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              账号正常
            </div>
          </div>
        </div>

        <div className="rounded-2xl bg-slate-50 px-4 py-3">
          <div className="flex items-center gap-2 text-[13px] font-bold text-slate-500">
            <CalendarDays className="h-4 w-4" />
            注册时间
          </div>
          <div className="mt-1 text-[15px] font-black text-slate-800">
            {formatDateTime(user.created_at)}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <StatBox
          label="今日摄入"
          value={
            dash.consumedCalories !== null
              ? `${dash.consumedCalories.toLocaleString()} kcal`
              : "暂无记录"
          }
        />
        <StatBox
          label="目标热量"
          value={formatTarget(
            dash.targetCalories ?? settings.target_calories,
            " kcal",
          )}
        />
        <StatBox label="目标类型" value={goalLabel(settings.goal_type)} />
      </div>
    </CardShell>
  );
}

function BasicProfileCard({
  user,
  nicknameDraft,
  saving,
  saved,
  onNicknameChange,
  onSave,
}: {
  user: UserProfile;
  nicknameDraft: string;
  saving: boolean;
  saved: boolean;
  onNicknameChange: (value: string) => void;
  onSave: () => void;
}) {
  const disabled =
    saving ||
    !nicknameDraft.trim() ||
    nicknameDraft.trim() === (user.nickname || "");

  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<UserRound className="h-5 w-5" />}
        title="基本资料"
        desc="修改你的个人昵称，手机号作为登录账号暂不支持修改。"
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Field
          label="昵称"
          value={nicknameDraft}
          onChange={onNicknameChange}
          placeholder="请输入昵称"
        />

        <ReadonlyField label="手机号" value={user.phone || "暂未获取手机号"} />

        <ReadonlyField
          label="头像标识"
          value={user.avatarText || user.nickname?.[0] || "我"}
        />

        <ReadonlyField label="注册时间" value={formatDateTime(user.created_at)} />
      </div>

      {saved ? (
        <p className="mt-5 rounded-xl bg-green-50 px-4 py-3 text-sm font-bold text-green-700">
          个人资料已保存
        </p>
      ) : null}

      <button
        type="button"
        onClick={onSave}
        disabled={disabled}
        className="mt-5 flex h-[52px] w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-base font-black text-white shadow-lg shadow-green-600/20 transition hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <Save className="h-5 w-5" />
        )}
        {saving ? "保存中..." : "保存资料"}
      </button>
    </CardShell>
  );
}

function GoalSummaryCard({ settings }: { settings: UserData }) {
  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<Target className="h-5 w-5" />}
        title="营养目标摘要"
        desc="这里展示当前目标，详细修改请前往设置页面。"
      />

      <div className="grid gap-3 md:grid-cols-2">
        <StatBox
          label="热量目标"
          value={formatTarget(settings.target_calories, " kcal")}
        />
        <StatBox label="目标类型" value={goalLabel(settings.goal_type)} />
        <StatBox
          label="蛋白质"
          value={formatTarget(settings.target_protein, "g")}
        />
        <StatBox label="碳水" value={formatTarget(settings.target_carbs, "g")} />
        <StatBox label="脂肪" value={formatTarget(settings.target_fat, "g")} />
      </div>

      <Link
        href="/settings"
        className="mt-5 flex h-[48px] items-center justify-center gap-2 rounded-xl bg-green-50 text-[15px] font-black text-green-700 transition hover:bg-green-100"
      >
        管理营养目标
        <ArrowRight className="h-4 w-4" />
      </Link>
    </CardShell>
  );
}

function AiInfoCard() {
  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<Sparkles className="h-5 w-5" />}
        title="AI 分析能力"
        desc="当前系统启用的饮食识别与总结能力。"
      />

      <div className="space-y-3">
        <InfoBadge icon={<Sparkles className="h-4 w-4" />} label="识别流程" value="OCR + Vision + Fusion" />
        <InfoBadge icon={<Sparkles className="h-4 w-4" />} label="AI 总结" value="百炼 qwen-plus" />
        <InfoBadge icon={<ShieldCheck className="h-4 w-4" />} label="缓存" value="Redis AI Cache" />
        <InfoBadge icon={<ShieldCheck className="h-4 w-4" />} label="日志" value="AI Logs" />
      </div>
    </CardShell>
  );
}

function SecurityCard({
  user,
  onLogout,
}: {
  user: UserProfile;
  onLogout: () => void;
}) {
  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<ShieldCheck className="h-5 w-5" />}
        title="账号安全"
        desc="管理你的登录状态和基础安全信息。"
      />

      <div className="space-y-3">
        <InfoRow label="登录方式" value="手机号登录" />
        <InfoRow label="登录账号" value={user.phone || "暂未获取手机号"} />
        <InfoRow label="账号状态" value="正常" />
      </div>

      <button
        type="button"
        onClick={onLogout}
        className="mt-5 flex h-[48px] w-full items-center justify-center gap-3 rounded-xl border border-red-100 bg-red-50 text-[15px] font-black text-red-600 transition hover:border-red-200 hover:bg-red-100"
      >
        <LogOut className="h-5 w-5" />
        退出登录
      </button>
    </CardShell>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-2 block text-[14px] font-black text-slate-700">
        {label}
      </label>

      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        maxLength={20}
        className="h-[52px] w-full rounded-xl border border-slate-200 bg-white px-4 text-[15px] font-semibold text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-green-500 focus:ring-4 focus:ring-green-500/10"
      />
    </div>
  );
}

function ReadonlyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="mb-2 block text-[14px] font-black text-slate-700">
        {label}
      </label>

      <div className="flex h-[52px] items-center rounded-xl border border-slate-200 bg-slate-50 px-4 text-[15px] font-semibold text-slate-500">
        {value}
      </div>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 px-4 py-3">
      <div className="text-[13px] font-bold text-slate-400">{label}</div>
      <div className="mt-1 text-[18px] font-black tracking-[-0.04em] text-slate-900">
        {value}
      </div>
    </div>
  );
}

function InfoBadge({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center gap-2 text-[14px] font-bold text-slate-500">
        <span className="text-green-600">{icon}</span>
        {label}
      </div>
      <div className="text-right text-[14px] font-black text-slate-800">
        {value}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
      <span className="text-[14px] font-bold text-slate-500">{label}</span>
      <span className="min-w-0 truncate text-right text-[14px] font-black text-slate-800">
        {value}
      </span>
    </div>
  );
}