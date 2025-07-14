"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  BarChart3,
  Beef,
  CheckCircle2,
  ChevronRight,
  Circle,
  ClipboardList,
  Download,
  Flame,
  Home,
  Info,
  Leaf,
  Loader2,
  PieChart as PieChartIcon,
  Settings,
  Sparkles,
  TrendingDown,
  TrendingUp,
  UploadCloud,
  Wheat,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet, ApiError } from "@/services/api";
import AccountMenu from "@/components/user/AccountMenu";

type UserProfile = {
  nickname: string;
  phone: string;
  avatarText: string;
};

type DayCalories = {
  day: string;
  calories: number;
};

type MacroTrend = {
  day: string;
  protein: number;
  carbs: number;
  fat: number;
};

type MealDistribution = {
  name: string;
  calories: number;
  color: string;
};

type WeeklyStats = {
  weekRange: string;
  targetCalories: number;
  avgDailyCalories: number;
  totalCalories: number;
  proteinTargetDays: number;
  highCarbDays: number;
  recordCount: number;
  averageMeals: number;
  todayGap: number;
  caloriesTrend: DayCalories[];
  macroTrend: MacroTrend[];
  mealDistribution: MealDistribution[];
  lastWeekComparison: {
    avgCaloriesDeltaPct: number;
    proteinDeltaPct: number;
    recordDeltaDays: number;
    avgCaloriesLastWeek: number;
    proteinLastWeek: number;
    recordDaysLastWeek: number;
  };
  aiSummary: string[];
};

const formatNumber = (value: number) =>
  new Intl.NumberFormat("en-US").format(value);

const classNames = (...classes: Array<string | false | undefined>) =>
  classes.filter(Boolean).join(" ");

function num(val: unknown, fallback = 0) {
  return typeof val === "number" && Number.isFinite(val) ? val : fallback;
}

function arr<T>(val: unknown): T[] {
  return Array.isArray(val) ? (val as T[]) : [];
}

function adaptWeeklyStats(raw: Record<string, unknown>): WeeklyStats {
  const r = (key: string) => raw[key] ?? null;

  const lastWeek =
    ((r("last_week_comparison") ?? r("lastWeekComparison") ?? {}) as Record<
      string,
      unknown
    >);

  return {
    weekRange: String(r("week_range") ?? r("weekRange") ?? ""),
    targetCalories: num(r("target_calories") ?? r("targetCalories")),
    avgDailyCalories: num(r("avg_daily_calories") ?? r("avgDailyCalories")),
    totalCalories: num(r("total_calories") ?? r("totalCalories")),
    proteinTargetDays: num(r("protein_target_days") ?? r("proteinTargetDays")),
    highCarbDays: num(r("high_carb_days") ?? r("highCarbDays")),
    recordCount: num(r("record_count") ?? r("recordCount")),
    averageMeals: num(r("average_meals") ?? r("averageMeals")),
    todayGap: num(r("today_gap") ?? r("todayGap")),
    caloriesTrend: arr<Record<string, unknown>>(
      r("daily_calories") ?? r("caloriesTrend"),
    ).map((d) => ({
      day: String(d.day ?? ""),
      calories: num(d.calories),
    })),
    macroTrend: arr<Record<string, unknown>>(
      r("macro_trend") ?? r("macroTrend"),
    ).map((d) => ({
      day: String(d.day ?? ""),
      protein: num(d.protein),
      carbs: num(d.carbs),
      fat: num(d.fat),
    })),
    mealDistribution: arr<Record<string, unknown>>(
      r("meal_distribution") ?? r("mealDistribution"),
    ).map((d) => ({
      name: String(d.name ?? ""),
      calories: num(d.calories),
      color: String(d.color ?? "#16A34A"),
    })),
    lastWeekComparison: {
      avgCaloriesDeltaPct: num(
        lastWeek.avg_calories_delta_pct ?? lastWeek.avgCaloriesDeltaPct,
      ),
      proteinDeltaPct: num(
        lastWeek.protein_delta_pct ?? lastWeek.proteinDeltaPct,
      ),
      recordDeltaDays: num(
        lastWeek.record_delta_days ?? lastWeek.recordDeltaDays,
      ),
      avgCaloriesLastWeek: num(
        lastWeek.avg_calories_last_week ?? lastWeek.avgCaloriesLastWeek,
      ),
      proteinLastWeek: num(
        lastWeek.protein_last_week ?? lastWeek.proteinLastWeek,
      ),
      recordDaysLastWeek: num(
        lastWeek.record_days_last_week ?? lastWeek.recordDaysLastWeek,
      ),
    },
    aiSummary: arr<string>(
      r("ai_summary") ?? r("aiSummary") ?? r("summary_items"),
    ).map(String),
  };
}

function getUserProfile(): UserProfile {
  if (typeof window === "undefined") {
    return { nickname: "", phone: "", avatarText: "" };
  }

  try {
    const raw = localStorage.getItem("user");
    if (raw) {
      const u = JSON.parse(raw);
      const nickname = u.nickname || "";
      return {
        nickname,
        phone: u.phone || "",
        avatarText: u.avatarText || nickname?.[0] || "我",
      };
    }
  } catch {
    // ignore
  }

  return { nickname: "", phone: "", avatarText: "我" };
}

export default function WeeklyStatisticsPage() {
  const router = useRouter();
  const [stats, setStats] = useState<WeeklyStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user] = useState<UserProfile>(() => getUserProfile());

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const raw = await apiGet<Record<string, unknown>>(
          "/api/statistics/weekly",
        );

        if (mounted) {
          setStats(adaptWeeklyStats(raw));
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          if (err instanceof ApiError) {
            if (err.status === 401) {
              localStorage.removeItem("token");
              localStorage.removeItem("user");
              router.push("/login");
              return;
            }

            setError(err.message);
          } else if (err instanceof TypeError && err.message.includes("fetch")) {
            setError("后端服务不可用，请确认已启动 uvicorn");
          } else {
            setError("数据加载失败");
          }
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, [router]);

  if (isLoading) {
    return (
      <WeeklyPageShell user={user} todayGap={null} isLoading>
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-green-600" />
            <p className="mt-3 text-[15px] font-bold text-slate-500">
              正在加载每周统计...
            </p>
          </div>
        </div>
      </WeeklyPageShell>
    );
  }

  if (error || !stats) {
    return (
      <WeeklyPageShell user={user} todayGap={null} isLoading={false}>
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Circle className="mx-auto h-10 w-10 text-slate-300" />
            <p className="mt-3 text-[15px] font-bold text-slate-500">
              {error || "暂无每周统计数据"}
            </p>
          </div>
        </div>
      </WeeklyPageShell>
    );
  }

  return (
    <WeeklyPageShell
      user={user}
      todayGap={stats.todayGap}
      isLoading={isLoading}
    >
      <div className="mt-4 min-h-0 flex-1 overflow-y-auto pb-6 pr-1">
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            icon={Flame}
            tone="green"
            title="平均每日热量"
            value={formatNumber(stats.avgDailyCalories)}
            suffix="kcal"
            description={
              stats.targetCalories > 0
                ? `目标 ${formatNumber(stats.targetCalories)} kcal`
                : "目标未设置"
            }
          />
          <KpiCard
            icon={Beef}
            tone="emerald"
            title="蛋白质达标"
            value={`${stats.proteinTargetDays} / 7`}
            suffix="天"
            description={`达标率 ${Math.round(
              (stats.proteinTargetDays / 7) * 100,
            )}%`}
          />
          <KpiCard
            icon={Wheat}
            tone="orange"
            title="高碳水天数"
            value={stats.highCarbDays}
            suffix="天"
            description={`占比 ${Math.round((stats.highCarbDays / 7) * 100)}%`}
          />
          <KpiCard
            icon={ClipboardList}
            tone="purple"
            title="本周记录"
            value={stats.recordCount}
            suffix="餐"
            description={`平均每日 ${stats.averageMeals} 餐`}
          />
        </section>

        <section className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="xl:col-span-6">
            <CaloriesBarChartCard stats={stats} />
          </div>

          <div className="xl:col-span-6">
            <MacroTrendChartCard stats={stats} />
          </div>
        </section>

        <section className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="xl:col-span-4">
            <MealDistributionCard stats={stats} />
          </div>

          <div className="xl:col-span-3">
            <LastWeekComparisonCard stats={stats} />
          </div>

          <div className="xl:col-span-5">
            <AiWeeklySummaryCard stats={stats} />
          </div>
        </section>

        <section className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          <button
            type="button"
            onClick={() => downloadWeeklyReport(stats)}
            className="group flex h-14 items-center justify-center gap-3 rounded-2xl border border-green-200 bg-white text-[15px] font-black text-green-700 shadow-[0_12px_30px_rgba(15,23,42,0.055)] transition hover:border-green-300 hover:bg-green-50"
          >
            <Download className="h-5 w-5 transition group-hover:-translate-y-0.5" />
            导出周报
          </button>

          <Link
            href="/records"
            className="group flex h-14 items-center justify-center gap-3 rounded-2xl bg-green-600 text-[15px] font-black text-white shadow-[0_18px_40px_rgba(22,163,74,0.25)] transition hover:bg-green-700"
          >
            <ClipboardList className="h-5 w-5 transition group-hover:-translate-y-0.5" />
            查看全部记录
          </Link>
        </section>
      </div>
    </WeeklyPageShell>
  );
}

function WeeklyPageShell({
  user,
  todayGap,
  isLoading,
  children,
}: {
  user: UserProfile;
  todayGap: number | null;
  isLoading: boolean;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#f8faf8] text-slate-950 lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={user} />

        <section className="min-w-0 bg-white lg:h-screen lg:overflow-hidden">
          <div className="mx-auto flex min-h-screen w-full max-w-[1480px] flex-col px-5 py-4 sm:px-6 lg:h-screen lg:min-h-0 lg:px-7">
            <WeeklyPageHeader
              user={user}
              todayGap={todayGap}
              isLoading={isLoading}
            />

            {children}
          </div>
        </section>
      </div>
    </main>
  );
}

function WeeklyPageHeader({
  user,
  todayGap,
  isLoading,
}: {
  user: UserProfile;
  todayGap: number | null;
  isLoading: boolean;
}) {
  const router = useRouter();

  const gapText =
    todayGap === null
      ? "正在加载今日目标"
      : todayGap > 0
        ? `你今天还差 ${formatNumber(todayGap)} kcal 达标`
        : todayGap === 0
          ? "你今天刚好达标"
          : `你今天已超出 ${formatNumber(Math.abs(todayGap))} kcal`;

  const statusText =
    isLoading || todayGap === null
      ? "加载中"
      : todayGap < 0
        ? "今日摄入偏高"
        : todayGap === 0
          ? "今日刚好达标"
          : "状态良好";

  return (
    <header className="flex shrink-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="text-[28px] font-black leading-tight tracking-[-0.06em] text-slate-950 sm:text-[34px]">
          每周统计
        </h1>

        <p className="mt-1.5 text-[15px] font-semibold text-slate-500">
          查看你本周的热量趋势、宏量营养变化与 AI 周复盘。
        </p>
      </div>

      <button
        type="button"
        onClick={() => router.push("/profile")}
        className="flex items-center gap-4 rounded-2xl px-2 py-1 text-left transition hover:bg-slate-50"
      >
        <div className="text-right">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            {statusText}
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            {gapText}
          </div>
        </div>

        <div className="grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[24px] font-black text-white shadow-xl shadow-green-600/20">
          {user.avatarText || user.nickname?.[0] || "我"}
        </div>
      </button>
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
          active
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
    <article
      className={`rounded-2xl border border-slate-200 bg-white shadow-[0_12px_30px_rgba(15,23,42,0.055)] ${className}`}
    >
      {children}
    </article>
  );
}

function KpiCard({
  icon: Icon,
  tone,
  title,
  value,
  suffix,
  description,
}: {
  icon: LucideIcon;
  tone: "green" | "emerald" | "orange" | "purple";
  title: string;
  value: string | number;
  suffix: string;
  description: string;
}) {
  const toneClass = {
    green: "bg-green-50 text-green-600",
    emerald: "bg-emerald-50 text-emerald-600",
    orange: "bg-orange-50 text-orange-500",
    purple: "bg-violet-50 text-violet-600",
  }[tone];

  return (
    <CardShell className="p-5">
      <div className="flex items-center gap-4">
        <div
          className={classNames(
            "flex h-12 w-12 items-center justify-center rounded-full",
            toneClass,
          )}
        >
          <Icon className="h-6 w-6" />
        </div>

        <div className="min-w-0">
          <p className="text-[15px] font-black text-slate-700">{title}</p>
          <div className="mt-1 flex items-end gap-2">
            <span className="text-[26px] font-black tracking-[-0.06em] text-slate-950">
              {value}
            </span>
            <span className="pb-1 text-[14px] font-bold text-slate-600">
              {suffix}
            </span>
          </div>
          <p className="mt-1 text-[14px] font-semibold text-slate-400">
            {description}
          </p>
        </div>
      </div>
    </CardShell>
  );
}

function ChartCard({
  title,
  icon: Icon,
  children,
  right,
}: {
  title: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <CardShell className="h-full p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {Icon ? <Icon className="h-5 w-5 text-green-600" /> : null}
          <h2 className="text-[19px] font-black tracking-[-0.04em] text-slate-950">
            {title}
          </h2>
          <Info className="h-4 w-4 text-slate-300" />
        </div>

        {right}
      </div>

      {children}
    </CardShell>
  );
}

function CaloriesBarChartCard({ stats }: { stats: WeeklyStats }) {
  const showTarget = stats.targetCalories > 0;

  return (
    <ChartCard title="每日热量趋势" icon={BarChart3}>
      <div className="h-[250px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={stats.caloriesTrend}
            margin={{ top: 20, right: 26, left: 0, bottom: 0 }}
          >
            <CartesianGrid vertical={false} stroke="#EEF2F7" />
            <XAxis
              dataKey="day"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#64748B", fontSize: 12, fontWeight: 600 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#64748B", fontSize: 12, fontWeight: 600 }}
              width={42}
            />
            <Tooltip
              cursor={{ fill: "rgba(22, 163, 74, 0.08)" }}
              content={<ChartTooltip unit="kcal" />}
            />
            {showTarget ? (
              <ReferenceLine
                y={stats.targetCalories}
                stroke="#94A3B8"
                strokeDasharray="4 4"
                label={{
                  value: `目标 ${formatNumber(stats.targetCalories)}`,
                  position: "right",
                  fill: "#475569",
                  fontSize: 12,
                  fontWeight: 700,
                }}
              />
            ) : null}
            <Bar
              dataKey="calories"
              name="热量"
              barSize={28}
              radius={[12, 12, 0, 0]}
            >
              {stats.caloriesTrend.map((item) => (
                <Cell
                  key={item.day}
                  fill={
                    showTarget && item.calories > stats.targetCalories
                      ? "#22C55E"
                      : "#16A34A"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

function MacroTrendChartCard({ stats }: { stats: WeeklyStats }) {
  return (
    <ChartCard
      title="宏量营养趋势"
      icon={Activity}
      right={
        <div className="hidden items-center gap-4 text-xs font-bold text-slate-500 sm:flex">
          <LegendDot color="#16A34A" label="蛋白质 (g)" />
          <LegendDot color="#F97316" label="碳水 (g)" />
          <LegendDot color="#6D5DF6" label="脂肪 (g)" />
        </div>
      }
    >
      <div className="h-[250px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={stats.macroTrend}
            margin={{ top: 14, right: 22, left: 0, bottom: 0 }}
          >
            <CartesianGrid vertical={false} stroke="#EEF2F7" />
            <XAxis
              dataKey="day"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#64748B", fontSize: 12, fontWeight: 600 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#64748B", fontSize: 12, fontWeight: 600 }}
              width={42}
            />
            <Tooltip content={<ChartTooltip unit="g" />} />
            <Line
              type="monotone"
              dataKey="protein"
              name="蛋白质"
              stroke="#16A34A"
              strokeWidth={2.6}
              dot={{ r: 3, strokeWidth: 2 }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="carbs"
              name="碳水"
              stroke="#F97316"
              strokeWidth={2.6}
              dot={{ r: 3, strokeWidth: 2 }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="fat"
              name="脂肪"
              stroke="#6D5DF6"
              strokeWidth={2.6}
              dot={{ r: 3, strokeWidth: 2 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

function MealDistributionCard({ stats }: { stats: WeeklyStats }) {
  const total = useMemo(
    () => stats.mealDistribution.reduce((sum, item) => sum + item.calories, 0),
    [stats.mealDistribution],
  );

  return (
    <ChartCard title="餐别热量分布" icon={PieChartIcon}>
      {stats.mealDistribution.length === 0 ? (
        <EmptyCardText text="暂无餐别分布数据" />
      ) : (
        <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-[170px_1fr] xl:grid-cols-1 2xl:grid-cols-[170px_1fr]">
          <div className="relative h-[170px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={stats.mealDistribution}
                  dataKey="calories"
                  innerRadius={52}
                  outerRadius={80}
                  paddingAngle={1}
                  stroke="none"
                >
                  {stats.mealDistribution.map((item) => (
                    <Cell key={item.name} fill={item.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>

            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-xl font-black text-slate-950">
                  {formatNumber(total)}
                </div>
                <div className="mt-0.5 text-xs font-bold text-slate-500">
                  kcal
                </div>
                <div className="text-xs font-semibold text-slate-400">
                  总摄入
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {stats.mealDistribution.map((item) => {
              const percent = total
                ? ((item.calories / total) * 100).toFixed(1)
                : "0";

              return (
                <div key={item.name} className="flex items-start gap-3">
                  <span
                    className="mt-1.5 h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-black text-slate-700">
                      {item.name}
                    </div>
                    <div className="mt-0.5 text-sm font-semibold text-slate-500">
                      {formatNumber(item.calories)} kcal{" "}
                      <span className="text-slate-400">({percent}%)</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </ChartCard>
  );
}

function LastWeekComparisonCard({ stats }: { stats: WeeklyStats }) {
  const items = [
    {
      label: "平均热量",
      value: `${stats.lastWeekComparison.avgCaloriesDeltaPct}%`,
      description: `较上周 ${formatNumber(
        stats.lastWeekComparison.avgCaloriesLastWeek,
      )} kcal`,
      icon: TrendingDown,
      positive: stats.lastWeekComparison.avgCaloriesDeltaPct < 0,
    },
    {
      label: "蛋白质",
      value: `+${stats.lastWeekComparison.proteinDeltaPct}%`,
      description: `较上周 ${stats.lastWeekComparison.proteinLastWeek} g`,
      icon: Beef,
      positive: true,
    },
    {
      label: "记录频率",
      value: `+${stats.lastWeekComparison.recordDeltaDays} 天`,
      description: `较上周 ${stats.lastWeekComparison.recordDaysLastWeek} 天`,
      icon: TrendingUp,
      positive: true,
    },
  ];

  return (
    <ChartCard title="与上周相比" icon={Activity}>
      <div className="space-y-1">
        {items.map((item, index) => (
          <div
            key={item.label}
            className={classNames(
              "flex items-center gap-3 py-4",
              index !== items.length - 1 && "border-b border-slate-100",
            )}
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-green-50 text-green-600">
              <item.icon className="h-5 w-5" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-sm font-black text-slate-700">
                {item.label}
              </div>
              <div className="mt-0.5 text-sm font-semibold text-slate-400">
                {item.description}
              </div>
            </div>

            <div
              className={classNames(
                "text-lg font-black",
                item.positive ? "text-green-600" : "text-orange-500",
              )}
            >
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </ChartCard>
  );
}

function AiWeeklySummaryCard({ stats }: { stats: WeeklyStats }) {
  const iconStyles = [
    "bg-green-50 text-green-600",
    "bg-emerald-50 text-emerald-600",
    "bg-orange-50 text-orange-500",
    "bg-violet-50 text-violet-600",
  ];

  return (
    <ChartCard
      title="AI 周总结"
      icon={Sparkles}
      right={
        <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-black text-violet-600">
          AI Insight
        </span>
      }
    >
      {stats.aiSummary.length === 0 ? (
        <EmptyCardText text="暂无 AI 周总结" />
      ) : (
        <div className="space-y-4">
          {stats.aiSummary.map((item, index) => (
            <div key={`${item}-${index}`} className="flex items-start gap-3">
              <div
                className={classNames(
                  "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                  iconStyles[index % iconStyles.length],
                )}
              >
                {index === 0 && <CheckCircle2 className="h-5 w-5" />}
                {index === 1 && <Beef className="h-5 w-5" />}
                {index === 2 && <Wheat className="h-5 w-5" />}
                {index >= 3 && <Sparkles className="h-5 w-5" />}
              </div>

              <p className="text-sm font-semibold leading-7 text-slate-600">
                {item}
              </p>
            </div>
          ))}
        </div>
      )}
    </ChartCard>
  );
}

function EmptyCardText({ text }: { text: string }) {
  return (
    <div className="flex min-h-[150px] items-center justify-center rounded-xl bg-slate-50 text-center text-sm font-bold text-slate-400">
      {text}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
  }>;
  label?: string;
  unit: string;
}) {
  if (!active || !payload?.length) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-100 bg-white px-4 py-3 shadow-[0_16px_36px_rgba(15,23,42,0.12)]">
      <div className="mb-2 text-sm font-black text-slate-700">{label}</div>
      <div className="space-y-1">
        {payload.map((item) => (
          <div
            key={item.name}
            className="flex min-w-[128px] items-center justify-between gap-4 text-sm"
          >
            <span className="flex items-center gap-2 font-semibold text-slate-500">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.name}
            </span>
            <span className="font-black text-slate-900">
              {formatNumber(Number(item.value))} {unit}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function downloadWeeklyReport(stats: WeeklyStats) {
  const rows = [
    ["day", "calories", "protein", "carbs", "fat"],
    ...stats.caloriesTrend.map((dayItem) => {
      const macro = stats.macroTrend.find((item) => item.day === dayItem.day);

      return [
        dayItem.day,
        String(dayItem.calories),
        String(macro?.protein ?? ""),
        String(macro?.carbs ?? ""),
        String(macro?.fat ?? ""),
      ];
    }),
  ];

  const csv = `\uFEFF${rows.map((row) => row.join(",")).join("\n")}`;
  const blob = new Blob([csv], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = "foodflow-weekly-report.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}