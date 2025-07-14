"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Circle,
  CloudUpload,
  Eye,
  Home,
  Leaf,
  Loader2,
  LockKeyhole,
  LogOut,
  Save,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
  Utensils,
  WandSparkles,
} from "lucide-react";
import AccountMenu from "@/components/user/AccountMenu";
import {
  getUserSettings,
  updateUserSettings,
  recommendTargets,
  type UserSettings,
  type RecommendTargetsResponse,
} from "@/services/settings";

type UserProfile = {
  nickname: string;
  phone: string;
  avatarText: string;
  created_at?: string | null;
};

type SettingsSection = "nutrition" | "diet" | "ai" | "notifications" | "privacy";
type Gender = "male" | "female" | "unknown";
type ActivityLevel = "sedentary" | "light" | "moderate" | "active";
type GoalType = "maintain" | "lose" | "gain";

type GoalProfileInput = {
  gender: Gender;
  age: string;
  heightCm: string;
  weightKg: string;
  activity: ActivityLevel;
  goalType: GoalType;
};

const goalOptions = [
  { value: "maintain", label: "维持体重", desc: "保持当前体重和饮食节奏" },
  { value: "lose", label: "减脂", desc: "控制热量缺口，关注蛋白质" },
  { value: "gain", label: "增肌", desc: "提高热量与蛋白质摄入" },
];

const activityOptions = [
  { value: "sedentary", label: "久坐", desc: "很少运动", multiplier: 1.2 },
  { value: "light", label: "轻度活动", desc: "每周 1-3 次", multiplier: 1.375 },
  { value: "moderate", label: "中等活动", desc: "每周 3-5 次", multiplier: 1.55 },
  { value: "active", label: "高活动", desc: "高频训练/体力劳动", multiplier: 1.725 },
] as const;

const sectionTabs: Array<{
  key: SettingsSection;
  label: string;
  desc: string;
  icon: React.ReactNode;
}> = [
  { key: "nutrition", label: "营养目标", desc: "由 AI 推荐热量与宏量目标", icon: <Target className="h-4 w-4" /> },
  { key: "diet", label: "饮食偏好", desc: "口味、忌口与常吃菜系", icon: <Utensils className="h-4 w-4" /> },
  { key: "ai", label: "AI 偏好", desc: "识别方式与确认规则", icon: <WandSparkles className="h-4 w-4" /> },
  { key: "notifications", label: "通知提醒", desc: "记录、总结与周报提醒", icon: <Bell className="h-4 w-4" /> },
  { key: "privacy", label: "数据隐私", desc: "图片、授权与数据操作", icon: <ShieldCheck className="h-4 w-4" /> },
];

function getUserProfile(): UserProfile {
  if (typeof window === "undefined") {
    return { nickname: "", phone: "", avatarText: "我" };
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
        created_at: u.created_at || null,
      };
    }
  } catch {
    // ignore
  }

  return { nickname: "", phone: "", avatarText: "我" };
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



export default function SettingsPage() {
  const router = useRouter();

  const [user] = useState<UserProfile>(() => getUserProfile());
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<SettingsSection>("nutrition");

  const [goalProfile, setGoalProfile] = useState<GoalProfileInput>({
    gender: "unknown",
    age: "",
    heightCm: "",
    weightKg: "",
    activity: "light",
    goalType: "maintain",
  });

  const [recommended, setRecommended] = useState<RecommendTargetsResponse | null>(null);
  const [recommendError, setRecommendError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const data = await getUserSettings();
        if (!mounted) return;
        setSettings(data);
        setGoalProfile((prev) => ({
          ...prev,
          gender: (data.gender as Gender) || "unknown",
          age: data.age ? String(data.age) : "",
          heightCm: data.height_cm ? String(data.height_cm) : "",
          weightKg: data.weight_kg ? String(data.weight_kg) : "",
          activity: (data.activity_level as ActivityLevel) || "light",
          goalType: (data.goal_type as GoalType) || "maintain",
        }));
      } catch (err) {
        if (mounted) setError("加载设置失败");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  const updateSettings = (patch: Partial<UserSettings>) => {
    setSettings((prev) => (prev ? { ...prev, ...patch } : prev));
    setSaveMsg("");
    setError("");
  };

  const handleSave = async (patch?: Partial<UserSettings>) => {
    if (!settings) return;
    setSaving(true);
    setSaveMsg("");
    setError("");
    try {
      const body = patch ?? settings;
      const updated = await updateUserSettings(body);
      setSettings(updated);
      setSaveMsg("已保存");
      setTimeout(() => setSaveMsg(""), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleRecommend = async () => {
    const age = Number(goalProfile.age);
    const height = Number(goalProfile.heightCm);
    const weight = Number(goalProfile.weightKg);
    if (!age || !height || !weight) {
      setRecommendError("请填写完整的身体信息");
      return;
    }
    setRecommendError("");
    try {
      const result = await recommendTargets({
        gender: goalProfile.gender,
        age,
        height_cm: height,
        weight_kg: weight,
        activity_level: goalProfile.activity,
        goal_type: goalProfile.goalType,
      });
      setRecommended(result);
    } catch (err) {
      setRecommendError(err instanceof Error ? err.message : "推荐计算失败");
    }
  };

  const applyRecommendation = () => {
    if (!recommended) return;
    updateSettings({
      target_calories: recommended.calories,
      target_protein: recommended.protein,
      target_carbs: recommended.carbs,
      target_fat: recommended.fat,
      nutrition_goal_mode: "agent_recommended",
    });
  };

  const handleSaveField = (field: keyof UserSettings, value: unknown) => {
    handleSave({ [field]: value } as Partial<UserSettings>);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  const renderActiveSection = () => {
    if (!settings) return null;

    switch (activeSection) {
      case "nutrition":
        return (
          <NutritionTargetCard
            settings={settings}
            saving={saving}
            error={error}
            saveMsg={saveMsg}
            goalProfile={goalProfile}
            setGoalProfile={setGoalProfile}
            onChange={updateSettings}
            onSave={handleSave}
            onRecommend={handleRecommend}
            recommendError={recommendError}
            recommended={recommended}
            onApplyRecommendation={applyRecommendation}
          />
        );
      case "diet":
        return <DietPreferenceCard settings={settings} onChange={updateSettings} onSave={handleSave} saving={saving} />;
      case "ai":
        return <AiPreferenceCard settings={settings} onChange={updateSettings} onSave={handleSave} saving={saving} />;
      case "notifications":
        return <NotificationCard settings={settings} onChange={updateSettings} onSave={handleSave} saving={saving} />;
      case "privacy":
        return <PrivacyCard settings={settings} onChange={updateSettings} onSave={handleSave} saving={saving} />;
      default:
        return null;
    }
  };

  return (
    <SettingsPageShell user={user}>
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-green-600" />
            <p className="mt-3 text-[15px] font-bold text-slate-500">
              正在加载设置...
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
        <div className="mt-4 min-h-0 flex-1 overflow-hidden">
          <div className="grid h-full gap-4 xl:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
              <SettingsSectionNav active={activeSection} onChange={setActiveSection} />
              <div className="mt-4">{renderActiveSection()}</div>
            </div>

            <div className="min-h-0 space-y-4 overflow-y-auto pr-1">
              <AccountEntryCard user={user} />
              <SecurityCard onLogout={handleLogout} />
              <SettingsHelpCard activeSection={activeSection} />
            </div>
          </div>
        </div>
      ) : null}
    </SettingsPageShell>
  );
}

function SettingsPageShell({
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
            <SettingsPageHeader user={user} />
            {children}
          </div>
        </section>
      </div>
    </main>
  );
}

function SettingsPageHeader({ user }: { user: UserProfile }) {
  const router = useRouter();

  return (
    <header className="flex shrink-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="text-[28px] font-black leading-tight tracking-[-0.06em] text-slate-950 sm:text-[34px]">
          设置
        </h1>

        <p className="mt-1.5 text-[15px] font-semibold text-slate-500">
          让 AI 根据你的身体情况、饮食习惯和隐私偏好，生成更合适的分析与建议。
        </p>
      </div>

      <button
        type="button"
        onClick={() => router.push("/profile")}
        className="flex items-center gap-4 rounded-2xl px-2 py-1 text-left transition hover:bg-slate-50"
      >
        <div className="text-right">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            账号设置
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            点击进入个人主页
          </div>
        </div>

        <div className="grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[24px] font-black text-white shadow-xl shadow-green-600/20">
          {user.avatarText || user.nickname?.[0] || "我"}
        </div>
      </button>
    </header>
  );
}

function SettingsSectionNav({
  active,
  onChange,
}: {
  active: SettingsSection;
  onChange: (section: SettingsSection) => void;
}) {
  return (
    <CardShell className="p-2">
      <div className="grid gap-2 md:grid-cols-5">
        {sectionTabs.map((section) => {
          const selected = active === section.key;
          return (
            <button
              key={section.key}
              type="button"
              onClick={() => onChange(section.key)}
              className={`flex min-h-[76px] flex-col items-start justify-between rounded-xl border px-3 py-3 text-left transition ${
                selected
                  ? "border-green-300 bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.12)]"
                  : "border-transparent bg-white text-slate-500 hover:border-green-100 hover:bg-green-50/40"
              }`}
            >
              <span className="flex items-center gap-1.5 text-[13px] font-black">
                {section.icon}
                {section.label}
              </span>
              <span className="text-[11px] font-semibold leading-4 text-slate-400">
                {section.desc}
              </span>
            </button>
          );
        })}
      </div>
    </CardShell>
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
        <SidebarItem href="/dashboard" icon={<Home className="h-5 w-5" />} label="首页" />
        <SidebarItem href="/upload" icon={<CloudUpload className="h-5 w-5" />} label="上传" />
        <SidebarItem href="/records" icon={<ClipboardList className="h-5 w-5" />} label="记录" />
        <SidebarItem href="/statistics/weekly" icon={<BarChart3 className="h-5 w-5" />} label="每周统计" />
        <SidebarItem href="/settings" active icon={<SettingsIcon className="h-5 w-5" />} label="设置" />
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
      <span className={active ? "text-green-600" : "text-slate-500"}>{icon}</span>
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
  badge,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  badge?: string;
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-3">
      <div className="flex items-start gap-3">
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

      {badge ? (
        <span className="shrink-0 rounded-full bg-violet-50 px-3 py-1 text-[12px] font-black text-violet-600">
          {badge}
        </span>
      ) : null}
    </div>
  );
}

function NutritionTargetCard({
  settings, saving, error, saveMsg, goalProfile, setGoalProfile, onChange, onSave, onRecommend, recommendError, recommended, onApplyRecommendation,
}: {
  settings: UserSettings; saving: boolean; error: string; saveMsg: string;
  goalProfile: GoalProfileInput; setGoalProfile: React.Dispatch<React.SetStateAction<GoalProfileInput>>;
  onChange: (patch: Partial<UserSettings>) => void; onSave: (patch?: Partial<UserSettings>) => Promise<void>;
  onRecommend: () => void; recommendError: string; recommended: RecommendTargetsResponse | null;
  onApplyRecommendation: () => void;
}) {
  const [showManualEdit, setShowManualEdit] = useState(false);
  const [recommending, setRecommending] = useState(false);

  const canRecommend =
    Boolean(goalProfile.gender) &&
    Number(goalProfile.age) > 0 &&
    Number(goalProfile.heightCm) > 0 &&
    Number(goalProfile.weightKg) > 0 &&
    Boolean(goalProfile.activity) &&
    Boolean(goalProfile.goalType);

  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<Target className="h-5 w-5" />}
        title="营养目标"
        desc="不用手动猜蛋白质和碳水，填写基础信息后由系统推荐目标；你仍可在高级设置里微调。"
        badge="Agent 推荐"
      />

      <div className="rounded-2xl border border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[15px] font-black text-green-800">目标计算器</div>
            <div className="mt-1 text-[12px] font-bold text-green-700/75">
              根据性别、年龄、身高、体重、活动量和目标类型估算每日目标。
            </div>
          </div>
          {recommended ? (
            <span className="rounded-full bg-white px-3 py-1 text-[12px] font-black text-green-700 shadow-sm">
              已生成推荐
            </span>
          ) : (
            <span className="rounded-full bg-white px-3 py-1 text-[12px] font-black text-slate-400 shadow-sm">
              待补充信息
            </span>
          )}
        </div>

        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr_1fr]">
          <SelectField
            label="性别"
            value={goalProfile.gender}
            onChange={(value) => setGoalProfile((prev) => ({ ...prev, gender: value as Gender }))}
            options={[
              { value: "unknown", label: "不透露" },
              { value: "male", label: "男" },
              { value: "female", label: "女" },
            ]}
          />
          <Field
            label="年龄"
            suffix="岁"
            value={goalProfile.age}
            type="number"
            placeholder="例如 28"
            onChange={(value) => setGoalProfile((prev) => ({ ...prev, age: value }))}
          />
          <Field
            label="身高"
            suffix="cm"
            value={goalProfile.heightCm}
            type="number"
            placeholder="例如 175"
            onChange={(value) => setGoalProfile((prev) => ({ ...prev, heightCm: value }))}
          />
          <Field
            label="当前体重"
            suffix="kg"
            value={goalProfile.weightKg}
            type="number"
            placeholder="例如 70"
            onChange={(value) => setGoalProfile((prev) => ({ ...prev, weightKg: value }))}
          />
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-2 block text-[14px] font-black text-slate-700">活动水平</label>
            <div className="grid gap-2 sm:grid-cols-4">
              {activityOptions.map((item) => {
                const active = goalProfile.activity === item.value;
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setGoalProfile((prev) => ({ ...prev, activity: item.value }))}
                    className={`rounded-xl border px-3 py-2.5 text-left transition ${
                      active
                        ? "border-green-400 bg-white text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.12)]"
                        : "border-green-100 bg-white/70 text-slate-500 hover:border-green-200"
                    }`}
                  >
                    <div className="text-[13px] font-black">{item.label}</div>
                    <div className="mt-0.5 text-[10px] font-bold text-slate-400">{item.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-[14px] font-black text-slate-700">目标类型</label>
            <div className="grid gap-2 sm:grid-cols-3">
              {goalOptions.map((item) => {
                const active = goalProfile.goalType === item.value;
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setGoalProfile((prev) => ({ ...prev, goalType: item.value as GoalType }))}
                    className={`rounded-xl border px-3 py-2.5 text-left transition ${
                      active
                        ? "border-green-400 bg-white text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.12)]"
                        : "border-green-100 bg-white/70 text-slate-500 hover:border-green-200"
                    }`}
                  >
                    <div className="text-[13px] font-black">{item.label}</div>
                    <div className="mt-0.5 text-[10px] font-bold text-slate-400">{item.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_240px]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-[15px] font-black text-slate-900">系统推荐目标</div>
              <div className="mt-1 text-[12px] font-bold text-slate-400">
                推荐值会写入下方目标，保存后影响首页与周统计。
              </div>
            </div>
            <button
              type="button"
              onClick={onApplyRecommendation}
              disabled={!recommended}
              className="rounded-xl bg-green-600 px-4 py-2 text-[13px] font-black text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              应用推荐
            </button>
          </div>

          {recommended ? (
            <>
              <div className="grid gap-2 sm:grid-cols-4">
                <TargetMetric label="热量" value={recommended.calories} unit="kcal" tone="text-orange-500" />
                <TargetMetric label="蛋白质" value={recommended.protein} unit="g" tone="text-green-600" />
                <TargetMetric label="碳水" value={recommended.carbs} unit="g" tone="text-orange-500" />
                <TargetMetric label="脂肪" value={recommended.fat} unit="g" tone="text-violet-600" />
              </div>
              <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-[12px] font-bold text-slate-500">
                估算基础：BMR {recommended.bmr} kcal · TDEE {recommended.tdee} kcal · 目标调整后生成每日目标。
              </div>
            </>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center">
              {!canRecommend ? (
                <p className="text-[13px] font-bold text-slate-400">请先填写完整的身体信息</p>
              ) : (
                <button
                  type="button"
                  onClick={async () => { setRecommending(true); await onRecommend(); setRecommending(false); }}
                  className="rounded-xl bg-green-600 px-5 py-3 text-[14px] font-black text-white transition hover:bg-green-700"
                >
                  {recommending ? "计算中..." : "生成推荐目标"}
                </button>
              )}
              {recommendError ? (
                <p className="mt-2 text-[12px] font-bold text-red-500">{recommendError}</p>
              ) : null}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="text-[13px] font-black text-slate-700">当前已保存目标</div>
          <div className="mt-3 space-y-2 text-[13px] font-bold text-slate-500">
            <CompactGoalRow label="热量" value={`${settings.target_calories || 0} kcal`} />
            <CompactGoalRow label="蛋白质" value={settings.target_protein ? `${settings.target_protein} g` : "默认推荐"} />
            <CompactGoalRow label="碳水" value={settings.target_carbs ? `${settings.target_carbs} g` : "默认推荐"} />
            <CompactGoalRow label="脂肪" value={settings.target_fat ? `${settings.target_fat} g` : "默认推荐"} />
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowManualEdit((prev) => !prev)}
        className="mt-4 flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-[14px] font-black text-slate-600 transition hover:bg-slate-50"
      >
        <span>高级手动微调</span>
        <ChevronRight className={`h-4 w-4 transition ${showManualEdit ? "rotate-90" : ""}`} />
      </button>

      {showManualEdit ? (
        <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-3 text-[13px] font-bold text-slate-400">
            适合有明确营养方案的用户。普通用户建议使用系统推荐。
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="每日目标热量"
              suffix="kcal"
              value={settings.target_calories}
              type="number"
              onChange={(v) => onChange({ target_calories: Number(v) > 0 ? Number(v) : 0 })}
            />
            <Field
              label="蛋白质目标"
              suffix="g"
              value={settings.target_protein ?? ""}
              type="number"
              placeholder="默认推荐"
              onChange={(v) => onChange({ target_protein: v ? Number(v) : null })}
            />
            <Field
              label="碳水目标"
              suffix="g"
              value={settings.target_carbs ?? ""}
              type="number"
              placeholder="默认推荐"
              onChange={(v) => onChange({ target_carbs: v ? Number(v) : null })}
            />
            <Field
              label="脂肪目标"
              suffix="g"
              value={settings.target_fat ?? ""}
              type="number"
              placeholder="默认推荐"
              onChange={(v) => onChange({ target_fat: v ? Number(v) : null })}
            />
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
          {error}
        </p>
      ) : null}

      {saveMsg ? (
        <p className="mt-4 rounded-xl bg-green-50 px-4 py-3 text-sm font-bold text-green-700">
          设置已保存，首页和每周统计会使用最新目标。
        </p>
      ) : null}

      <button
        type="button"
        onClick={() => onSave()}
        disabled={saving || (canRecommend && settings.target_calories <= 0)}
        className="mt-5 flex h-[52px] w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-base font-black text-white shadow-lg shadow-green-600/20 transition hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
        {saving ? "保存中..." : "保存营养目标"}
      </button>
    </CardShell>
  );
}

function TargetMetric({ label, value, unit, tone }: { label: string; value: number; unit: string; tone: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-3 text-center">
      <div className={`text-[22px] font-black tracking-[-0.05em] ${tone}`}>{value}</div>
      <div className="mt-1 text-[11px] font-black text-slate-400">{label} {unit}</div>
    </div>
  );
}

function CompactGoalRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span>{label}</span>
      <span className="font-black text-slate-800">{value}</span>
    </div>
  );
}

function DietPreferenceCard({
  settings, onChange, onSave, saving,
}: {
  settings: UserSettings; onChange: (patch: Partial<UserSettings>) => void; onSave: (patch?: Partial<UserSettings>) => Promise<void>; saving: boolean;
}) {
  const cuisinesList = ["川菜", "粤菜", "东北菜", "西餐", "日料", "韩餐", "轻食", "家常菜"];
  const activeCuisines = settings.cuisines ?? [];
  return (
    <CardShell className="p-5">
      <SectionTitle icon={<Utensils className="h-5 w-5" />} title="饮食偏好" desc="影响 AI 总结的侧重点" badge="已同步" />
      <PreferenceBlock title="饮食方式">
        <ChoiceGrid value={settings.diet_style || "normal"} onChange={(value) => onChange({ diet_style: value })}
          options={[{ value: "normal", label: "普通饮食", desc: "均衡记录日常餐食" },{ value: "high_protein", label: "高蛋白", desc: "更关注蛋白质摄入" },{ value: "low_carb", label: "低碳", desc: "控制主食与糖类" },{ value: "vegetarian", label: "素食", desc: "偏向植物性食物" },{ value: "glucose_control", label: "控糖", desc: "提示高糖风险" }]} />
      </PreferenceBlock>
      <PreferenceBlock title="口味偏好">
        <SegmentedOptions value={settings.taste_preference || "normal"} onChange={(value) => onChange({ taste_preference: value })}
          options={[{ value: "light", label: "清淡" },{ value: "normal", label: "正常" },{ value: "spicy", label: "偏辣" }]} />
      </PreferenceBlock>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="忌口 / 不喜欢" value={settings.avoid_foods || ""} placeholder="例如 香菜、肥肉、动物内脏" onChange={(value) => onChange({ avoid_foods: value || null })} />
        <Field label="过敏原" value={settings.allergens || ""} placeholder="例如 花生、虾、牛奶" onChange={(value) => onChange({ allergens: value || null })} />
      </div>
      <PreferenceBlock title="常吃菜系">
        <div className="flex flex-wrap gap-2">
          {cuisinesList.map((item) => {
            const active = activeCuisines.includes(item);
            return (
              <button key={item} type="button" onClick={() => {
                const next = active ? activeCuisines.filter((v) => v !== item) : [...activeCuisines, item];
                onChange({ cuisines: next });
              }} className={`rounded-full border px-3 py-1.5 text-[13px] font-black transition ${active ? "border-green-500 bg-green-500 text-white" : "border-slate-200 bg-white text-slate-500 hover:border-green-200 hover:bg-green-50"}`}>
                {item}{active ? " ✓" : ""}
              </button>
            );
          })}
        </div>
      </PreferenceBlock>
      <div className="mt-4">
        <button type="button" onClick={() => onSave({ diet_style: settings.diet_style, taste_preference: settings.taste_preference, avoid_foods: settings.avoid_foods, allergens: settings.allergens, cuisines: settings.cuisines })} disabled={saving} className="flex h-10 items-center gap-2 rounded-xl bg-green-600 px-5 text-[13px] font-black text-white transition hover:bg-green-700 disabled:opacity-50">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}保存饮食偏好
        </button>
      </div>
    </CardShell>
  );
}

function AiPreferenceCard({
  settings, onChange, onSave, saving,
}: {
  settings: UserSettings; onChange: (patch: Partial<UserSettings>) => void; onSave: (patch?: Partial<UserSettings>) => Promise<void>; saving: boolean;
}) {
  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<WandSparkles className="h-5 w-5" />}
        title="AI 分析偏好"
        desc="这里不展示 Redis、Mock、模型名等开发信息，只保留用户能理解和控制的 AI 行为。"
        badge="已同步"
      />

      <div className="grid gap-4 md:grid-cols-2">
        <PreferenceBlock title="识别模式">
          <ChoiceGrid
            value={settings.ai_recognition_mode}
            onChange={(value) => onChange({ ai_recognition_mode: value })}
            options={[
              { value: "standard", label: "标准", desc: "速度和准确度平衡" },
              { value: "precise", label: "精细", desc: "更重视成分拆分" },
            ]}
          />
        </PreferenceBlock>
        <PreferenceBlock title="营养估算倾向">
          <ChoiceGrid
            value={settings.ai_estimate_mode}
            onChange={(value) => onChange({ ai_estimate_mode: value })}
            options={[
              { value: "conservative", label: "保守", desc: "偏低估算风险" },
              { value: "standard", label: "标准", desc: "按常规参考估算" },
              { value: "higher", label: "偏高", desc: "外卖/重油场景" },
            ]}
          />
        </PreferenceBlock>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <ToggleRow label="低置信度时提醒我确认" checked={settings.ai_low_confidence_confirm} onChange={(checked) => onChange({ ai_low_confidence_confirm: checked })} />
        <ToggleRow label="显示成分明细" checked={settings.ai_show_components} onChange={(checked) => onChange({ ai_show_components: checked })} />
        <ToggleRow label="显示 AI 营养总结" checked={settings.ai_show_summary} onChange={(checked) => onChange({ ai_show_summary: checked })} />
        <ToggleRow label="菜品相似时让我确认" checked={settings.ai_confirm_similar_dish} onChange={(checked) => onChange({ ai_confirm_similar_dish: checked })} />
      </div>

    </CardShell>
  );
}

function NotificationCard({
  settings, onChange, onSave, saving,
}: {
  settings: UserSettings; onChange: (patch: Partial<UserSettings>) => void; onSave: (patch?: Partial<UserSettings>) => Promise<void>; saving: boolean;
}) {
  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<Bell className="h-5 w-5" />}
        title="通知提醒"
        desc="规划记录提醒、每日总结和周报。推送能力接入后会使用这些时间。"
        badge="待接入"
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Field label="早餐提醒" value={settings.breakfast_reminder_time || ""} type="time" onChange={(value) => onChange({ breakfast_reminder_time: value })} />
        <Field label="午餐提醒" value={settings.lunch_reminder_time || ""} type="time" onChange={(value) => onChange({ lunch_reminder_time: value })} />
        <Field label="晚餐提醒" value={settings.dinner_reminder_time || ""} type="time" onChange={(value) => onChange({ dinner_reminder_time: value })} />
        <Field label="每日总结" value={settings.daily_summary_time || ""} type="time" onChange={(value) => onChange({ daily_summary_time: value })} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <ToggleRow label="每周报告提醒" checked={settings.weekly_report_enabled} onChange={(checked) => onChange({ weekly_report_enabled: checked })} />
        <ToggleRow label="长时间未记录提醒" checked={settings.inactivity_reminder_enabled} onChange={(checked) => onChange({ inactivity_reminder_enabled: checked })} />
      </div>

      <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-[13px] font-semibold leading-6 text-amber-700">
        提醒功能将在后续版本开启；当前设置仅用于前端预览，不会发送真实通知。
      </p>
    </CardShell>
  );
}

function PrivacyCard({
  settings, onChange, onSave, saving,
}: {
  settings: UserSettings; onChange: (patch: Partial<UserSettings>) => void; onSave: (patch?: Partial<UserSettings>) => Promise<void>; saving: boolean;
}) {
  const [toast, setToast] = useState("");
  const showPending = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(""), 2200);
  };

  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<ShieldCheck className="h-5 w-5" />}
        title="数据与隐私"
        desc="管理上传图片、AI 数据授权和数据操作。危险操作默认不执行，待后端接口接入。"
        badge="隐私"
      />

      <PreferenceBlock title="上传图片保存">
        <ChoiceGrid
          value={settings.image_retention_policy || "keep_history"}
          onChange={(value) => onChange({ image_retention_policy: value })}
          options={[
            { value: "history", label: "保存用于历史记录", desc: "可在记录详情中查看餐图" },
            { value: "deleteAfterAnalysis", label: "分析后自动删除", desc: "仅保留营养结果" },
          ]}
        />
      </PreferenceBlock>

      <PreferenceBlock title="AI 数据使用授权">
        <ToggleRow label="允许匿名改进识别（不包含账号身份信息）" checked={settings.allow_anonymous_ai_training} onChange={(checked) => onChange({ allow_anonymous_ai_training: checked })} />
      </PreferenceBlock>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <button type="button" onClick={() => showPending("数据导出功能待接入")} className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-[14px] font-black text-green-700 transition hover:bg-green-100">
          导出饮食数据
        </button>
        <button type="button" onClick={() => showPending("清空记录功能待接入")} className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-[14px] font-black text-red-600 transition hover:bg-red-100">
          清空所有记录
        </button>
        <button type="button" onClick={() => showPending("注销账号功能待接入")} className="rounded-xl border border-red-100 bg-white px-4 py-3 text-[14px] font-black text-red-600 transition hover:bg-red-50">
          注销账号
        </button>
      </div>

      {toast ? (
        <p className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-[13px] font-bold text-slate-500">
          {toast}
        </p>
      ) : null}
    </CardShell>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  suffix,
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  suffix?: string;
}) {
  return (
    <div>
      <label className="mb-2 block text-[14px] font-black text-slate-700">
        {label}
      </label>

      <div className="relative">
        <input
          type={type}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          className="h-[52px] w-full rounded-xl border border-slate-200 bg-white px-4 pr-14 text-[15px] font-semibold text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-green-500 focus:ring-4 focus:ring-green-500/10"
        />

        {suffix ? (
          <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[13px] font-black text-slate-400">
            {suffix}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value) ?? options[0];

  return (
    <div className="relative">
      <label className="mb-2 block text-[14px] font-black text-slate-700">{label}</label>

      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        className={`flex h-[52px] w-full items-center justify-between gap-3 rounded-xl border bg-white px-4 text-left text-[15px] font-black outline-none transition ${
          open
            ? "border-green-500 shadow-[0_0_0_4px_rgba(34,197,94,0.10)]"
            : "border-slate-200 hover:border-green-200 hover:bg-green-50/30"
        }`}
      >
        <span className={selected?.value === "unknown" ? "text-slate-600" : "text-slate-800"}>
          {selected?.label || "请选择"}
        </span>
        <span
          className={`grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-50 text-slate-400 transition ${
            open ? "rotate-180 bg-green-50 text-green-600" : ""
          }`}
        >
          <ChevronDown className="h-4 w-4" />
        </span>
      </button>

      {open ? (
        <div className="absolute left-0 right-0 z-30 mt-2 overflow-hidden rounded-2xl border border-green-100 bg-white p-1.5 shadow-[0_18px_40px_rgba(15,23,42,0.12)]">
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex h-10 w-full items-center justify-between rounded-xl px-3 text-left text-[14px] font-black transition ${
                  active
                    ? "bg-green-50 text-green-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <span>{option.label}</span>
                {active ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function PreferenceBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <div className="mb-2 text-[14px] font-black text-slate-700">{title}</div>
      {children}
    </div>
  );
}

function ChoiceGrid({
  value,
  options,
  onChange,
}: {
  value: string;
  options: Array<{ value: string; label: string; desc: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded-2xl border px-4 py-3 text-left transition ${
              active
                ? "border-green-500 bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.12)]"
                : "border-slate-200 bg-white text-slate-500 hover:border-green-200 hover:bg-green-50/40"
            }`}
          >
            <div className="text-[14px] font-black">{option.label}</div>
            <div className="mt-1 text-[11px] font-semibold leading-5 text-slate-400">{option.desc}</div>
          </button>
        );
      })}
    </div>
  );
}

function SegmentedOptions({
  value,
  options,
  onChange,
}: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1">
      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded-lg px-4 py-2 text-[13px] font-black transition ${
              active ? "bg-green-500 text-white shadow-sm" : "text-slate-500 hover:bg-white"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:bg-slate-50"
    >
      <span className="text-[14px] font-black text-slate-700">{label}</span>
      <span className={`relative h-7 w-12 rounded-full transition ${checked ? "bg-green-500" : "bg-slate-200"}`}>
        <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition ${checked ? "left-6" : "left-1"}`} />
      </span>
    </button>
  );
}

function AccountEntryCard({ user }: { user: UserProfile }) {
  const router = useRouter();

  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<UserRound className="h-5 w-5" />}
        title="账号入口"
        desc="完整个人资料将在个人主页管理。"
      />

      <div className="flex items-center gap-4 rounded-2xl bg-slate-50 p-4">
        <div className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-gradient-to-br from-green-400 to-green-700 text-[24px] font-black text-white shadow-lg shadow-green-600/20">
          {user.avatarText || user.nickname?.[0] || "我"}
        </div>

        <div className="min-w-0">
          <div className="truncate text-[18px] font-black text-slate-950">
            {user.nickname || "FoodFlow 用户"}
          </div>
          <div className="mt-1 truncate text-[14px] font-semibold text-slate-500">
            {user.phone || "暂未获取手机号"}
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => router.push("/profile")}
        className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-green-200 bg-green-50 text-[14px] font-black text-green-700 transition hover:bg-green-100"
      >
        进入个人主页
        <ChevronRight className="h-4 w-4" />
      </button>
    </CardShell>
  );
}

function SecurityCard({ onLogout }: { onLogout: () => void }) {
  const [message, setMessage] = useState("");
  const pending = (text: string) => {
    setMessage(text);
    setTimeout(() => setMessage(""), 2200);
  };

  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<LockKeyhole className="h-5 w-5" />}
        title="账号安全"
        desc="管理登录状态和安全操作。"
      />

      <div className="space-y-3">
        <InfoRow label="登录状态" value="已登录" />
        <InfoRow label="安全级别" value="基础保护" />
      </div>

      <div className="mt-4 space-y-2">
        <button type="button" onClick={() => pending("修改手机号功能待接入")} className="flex h-10 w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-[13px] font-black text-slate-600 transition hover:bg-slate-50">
          修改手机号 <ChevronRight className="h-4 w-4 text-slate-400" />
        </button>
        <button type="button" onClick={() => pending("登录设备管理功能待接入")} className="flex h-10 w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 text-[13px] font-black text-slate-600 transition hover:bg-slate-50">
          登录设备管理 <ChevronRight className="h-4 w-4 text-slate-400" />
        </button>
      </div>

      {message ? <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-[12px] font-bold text-slate-500">{message}</p> : null}

      <button
        type="button"
        onClick={onLogout}
        className="mt-4 flex h-[48px] w-full items-center justify-center gap-3 rounded-xl border border-red-100 bg-red-50 text-[15px] font-black text-red-600 transition hover:border-red-200 hover:bg-red-100"
      >
        <LogOut className="h-5 w-5" />
        退出登录
      </button>
    </CardShell>
  );
}

function SettingsHelpCard({ activeSection }: { activeSection: SettingsSection }) {
  const messages: Record<SettingsSection, string> = {
    nutrition: "目标由系统根据身体信息计算，普通用户不需要手动判断蛋白质、碳水和脂肪。",
    diet: "饮食偏好会让 AI 总结更贴近你的口味和忌口，例如低碳、控糖或偏辣。",
    ai: "AI 偏好用于控制何时提醒你确认、是否展示成分明细和营养总结。",
    notifications: "提醒功能当前为前端规划，后续接入推送后会按这些时间生效。",
    privacy: "隐私设置用于规划图片保留和数据授权策略，危险操作需要后端接口接入后才会执行。",
  };

  return (
    <CardShell className="p-5">
      <SectionTitle
        icon={<Eye className="h-5 w-5" />}
        title="设置说明"
        desc={messages[activeSection]}
      />
      <div className="rounded-xl bg-green-50 px-4 py-3 text-[13px] font-semibold leading-6 text-green-700">
        这里的目标是让设置页更像 Agent 配置面板：用户提供事实和偏好，系统负责推导目标和分析规则。
      </div>
    </CardShell>
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
