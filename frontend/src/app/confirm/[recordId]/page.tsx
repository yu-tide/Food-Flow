"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  BadgeCheck,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Circle,
  ClipboardList,
  CloudUpload,
  Home,
  ImageIcon,
  Info,
  Leaf,
  Loader2,
  PencilLine,
  Plus,
  RotateCcw,
  Save,
  Settings,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import AccountMenu from "@/components/user/AccountMenu";
import ProfileEntry from "@/components/user/ProfileEntry";
import { ApiError } from "@/services/api";
import { formatFoodItemLabels } from "@/lib/foodLabels";
import {
  getFoodRecord,
  type AnalyzeResult,
  type FoodItem,
} from "@/services/foods";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

type UserProfile = {
  nickname: string;
  phone: string;
  avatarText: string;
};

type FieldErrors = Record<string, string>;

type EditableFoodItem = FoodItem & {
  previewCalories?: number;
  previewProtein?: number;
  previewCarbs?: number;
  previewFat?: number;
  hasWeightChange?: boolean;
};

function getUserProfile(): UserProfile {
  if (typeof window === "undefined") {
    return { nickname: "", phone: "", avatarText: "" };
  }
  try {
    const raw = localStorage.getItem("user");
    if (raw) {
      const u = JSON.parse(raw);
      return {
        nickname: u.nickname || "",
        phone: u.phone || "",
        avatarText: u.avatarText || u.nickname?.[0] || "",
      };
    }
  } catch { /* ignore */ }
  return { nickname: "", phone: "", avatarText: "" };
}

function resolveImg(src?: string | null): string {
  if (!src) return "";
  if (src.startsWith("http")) return src;
  if (src.startsWith("/") && API_BASE) return `${API_BASE}${src}`;
  return src;
}

function normalizeErrorMessage(value: unknown): string {
  if (!value) return "请求失败，请重试";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const obj = item as Record<string, unknown>;
          return String(obj.msg || obj.message || obj.error_message || JSON.stringify(obj));
        }
        return String(item);
      })
      .join("；");
  }
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if (typeof obj.error_message === "string") return obj.error_message;
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.msg === "string") return obj.msg;
    if (Array.isArray(obj.detail)) return normalizeErrorMessage(obj.detail);
    if (typeof obj.detail === "string") return obj.detail;
    return "请求失败，请检查输入内容";
  }
  return String(value);
}

function parseWeightG(value?: string | number | null): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (!value) return 0;
  const match = String(value).match(/(\d+(?:\.\d+)?)/);
  return match ? Number.parseFloat(match[1]) : 0;
}

function formatWeight(value: string): string {
  const g = parseWeightG(value);
  if (!g) return value || "";
  return `${Math.round(g * 10) / 10}g`;
}

function roundMacro(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round(value);
}

function validateFoodName(name: string): string | null {
  const value = name.trim();
  if (!value) return "请输入食物名称";
  if (value.length > 30) return "食物名称不能超过 30 个字符";
  if (/^\d+$/.test(value)) return "食物名称不能为纯数字";
  if (/^[^一-龥a-zA-Z0-9]+$/.test(value)) return "食物名称不能只有符号";
  return null;
}

function validateWeight(weight: string): string | null {
  const grams = parseWeightG(weight);
  if (!grams || grams <= 0) return "请输入有效重量，例如 50g";
  if (grams > 5000) return "重量过大，请确认是否正确";
  return null;
}

function scrollToFirstFieldError() {
  requestAnimationFrame(() => {
    const el = document.querySelector('[data-field-error="true"]');
    if (el instanceof HTMLElement) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      const input = el.querySelector("input");
      if (input instanceof HTMLInputElement) input.focus();
    }
  });
}

function isNewItem(item: Pick<FoodItem, "id">): boolean {
  const id = String(item.id ?? "");
  return id.startsWith("new-") || id.startsWith("temp-");
}

function withPreview(item: FoodItem, inputWeight: string): EditableFoodItem {
  const oldWeight = parseWeightG(item.weight);
  const newWeight = parseWeightG(inputWeight || item.weight);
  const isNew = isNewItem(item);
  const hasWeightChange = oldWeight > 0 && newWeight > 0 && Math.abs(oldWeight - newWeight) > 0.01;
  if (isNew) {
    return { ...item, weight: inputWeight || item.weight, previewCalories: -1, previewProtein: -1, previewCarbs: -1, previewFat: -1, hasWeightChange: false };
  }
  if (oldWeight > 0 && newWeight > 0 && item.calories > 0) {
    const ratio = newWeight / oldWeight;
    return { ...item, weight: inputWeight || item.weight, previewCalories: roundMacro(item.calories * ratio), previewProtein: roundMacro(item.protein * ratio), previewCarbs: roundMacro(item.carbs * ratio), previewFat: roundMacro(item.fat * ratio), hasWeightChange };
  }
  return { ...item, weight: inputWeight || item.weight, previewCalories: item.calories, previewProtein: item.protein, previewCarbs: item.carbs, previewFat: item.fat, hasWeightChange: false };
}

function sumPreview(items: EditableFoodItem[]) {
  return items.reduce(
    (acc, item) => {
      const cal = item.previewCalories ?? item.calories;
      const pro = item.previewProtein ?? item.protein;
      const cb = item.previewCarbs ?? item.carbs;
      const ft = item.previewFat ?? item.fat;
      if (cal >= 0) acc.calories += Number(cal) || 0;
      if (pro >= 0) acc.protein += Number(pro) || 0;
      if (cb >= 0) acc.carbs += Number(cb) || 0;
      if (ft >= 0) acc.fat += Number(ft) || 0;
      return acc;
    },
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );
}

export default function ConfirmPage() {
  const router = useRouter();
  const params = useParams();
  const recordId = useMemo(() => {
    const value = params?.recordId;
    return Array.isArray(value) ? value[0] : String(value ?? "");
  }, [params]);

  const [user, setUser] = useState<UserProfile | null>(null);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [items, setItems] = useState<FoodItem[]>([]);
  const [weightInputs, setWeightInputs] = useState<string[]>([]);
  const [originalNames, setOriginalNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const dishComponentsRef = useRef<Array<Record<string, unknown>>>([]);
  const userCorrectionRef = useRef<string | null>(null);

  useEffect(() => { setUser(getUserProfile()); }, []);

  const loadRecord = useCallback(async () => {
    if (!recordId) return;
    setLoading(true);
    setError("");
    setFieldErrors({});
    try {
      const data = await getFoodRecord(recordId);
      console.log("[confirm loadRecord]", {
        analysisMode: data.analysisMode,
        foodItemsCount: data.foodItems?.length,
        firstItemName: data.foodItems?.[0]?.name,
        firstComponentsCount: data.foodItems?.[0]?.components?.length,
        firstComponents: data.foodItems?.[0]?.components,
      });
      const nextItems = (data.foodItems || []).map((item) => ({ ...item }));
      setResult(data);
      setItems(nextItems);
      setWeightInputs(nextItems.map((item) => item.weight || ""));
      setOriginalNames(nextItems.map((item) => item.name || ""));
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) { localStorage.removeItem("token"); localStorage.removeItem("user"); router.push("/login"); return; }
        if (err.status === 404) { setError("记录不存在或无权限访问"); return; }
        setError(err.message || "加载失败"); return;
      }
      setError("加载失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [recordId, router]);

  useEffect(() => { loadRecord(); }, [loadRecord]);

  const isConfirmed = result?.status === "confirmed";
  const previewItems = useMemo(() => items.map((item, index) => withPreview(item, weightInputs[index] || item.weight)), [items, weightInputs]);
  const totals = useMemo(() => sumPreview(previewItems), [previewItems]);
  const changedCount = previewItems.filter((item) => item.hasWeightChange).length;

  const clearFieldError = useCallback((index: number, field: "name" | "weight") => {
    const key = `${index}.${field}`;
    setFieldErrors((prev) => { if (!prev[key]) return prev; const next = { ...prev }; delete next[key]; return next; });
    setError("");
  }, []);

  const validateBeforeSubmit = useCallback((): boolean => {
    const nextErrors: FieldErrors = {};
    if (items.length === 0) { setError("请至少保留一个食物，或返回重新分析"); return false; }
    items.forEach((item, index) => {
      const nameError = validateFoodName(item.name || "");
      const weightError = validateWeight(weightInputs[index] || item.weight || "");
      if (nameError) nextErrors[`${index}.name`] = nameError;
      if (weightError) nextErrors[`${index}.weight`] = weightError;
    });
    if (Object.keys(nextErrors).length > 0) { setFieldErrors(nextErrors); setError("请先修正标红的食物信息"); scrollToFirstFieldError(); return false; }
    setFieldErrors({}); return true;
  }, [items, weightInputs]);

  const updateName = (index: number, name: string) => { clearFieldError(index, "name"); setMessage(""); setItems((prev) => prev.map((item, i) => (i === index ? { ...item, name } : item))); };
  const updateWeight = (index: number, value: string) => { clearFieldError(index, "weight"); setMessage(""); setWeightInputs((prev) => { const next = [...prev]; next[index] = value; return next; }); setItems((prev) => prev.map((item, i) => (i === index ? { ...item, weight: value } : item))); };

  function hasNameChanged(index: number): boolean {
    const orig = originalNames[index];
    if (orig === undefined) return true;
    return (items[index]?.name || "").trim() !== orig.trim();
  }

  const handleAddItem = () => {
    if (isConfirmed) return;
    const newItem = { id: `new-${Date.now()}`, name: "", weight: "", calories: 0, protein: 0, carbs: 0, fat: 0, category: "unknown", source: "manual", estimated: true, confidence: 1, imageUrl: "", components: null } as FoodItem;
    setItems((prev) => [...prev, newItem]);
    setWeightInputs((prev) => [...prev, ""]);
    setOriginalNames((prev) => [...prev, ""]);
    setError(""); setMessage("");
  };

  const handleDeleteItem = (index: number) => {
    if (isConfirmed) return;
    setItems((prev) => prev.filter((_, i) => i !== index));
    setWeightInputs((prev) => prev.filter((_, i) => i !== index));
    setOriginalNames((prev) => prev.filter((_, i) => i !== index));
    setFieldErrors({}); setError(""); setMessage("");
  };

  const handleBackToResult = () => { router.push(`/records/${recordId}`); };

  const handleUpdateDraft = async () => {
    if (!recordId || isConfirmed) return;
    setError(""); setMessage("");
    if (!validateBeforeSubmit()) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      const analysisMode = result?.analysisMode ?? "dish_with_components";
      const isDishMode = analysisMode === "dish_with_components" || analysisMode === "whole_dish";
      const currentComps = isDishMode ? dishComponentsRef.current : [];

      const body: Record<string, unknown> = isDishMode
        ? {
            analysis_mode: analysisMode,
            user_correction: userCorrectionRef.current,
            ...(currentComps.length > 0 ? {
              dish: {
                name: items[0]?.name || "",
                weight: Math.round(currentComps.reduce((s: number, c: Record<string, unknown>) => s + (Number(c.estimatedWeightG) || 0), 0)),
                calories: Math.round(currentComps.reduce((s: number, c: Record<string, unknown>) => s + (Number(c.calories) || 0), 0)),
                protein: Math.round(currentComps.reduce((s: number, c: Record<string, unknown>) => s + (Number(c.protein) || 0), 0)),
                carbs: Math.round(currentComps.reduce((s: number, c: Record<string, unknown>) => s + (Number(c.carbs) || 0), 0)),
                fat: Math.round(currentComps.reduce((s: number, c: Record<string, unknown>) => s + (Number(c.fat) || 0), 0)),
              },
              components: currentComps.map((c: Record<string, unknown>) => ({
                name: c.name,
                estimated_weight_g: Number(c.estimatedWeightG) || null,
                calories: Number(c.calories) || null,
                protein: Number(c.protein) || null,
                carbs: Number(c.carbs) || null,
                fat: Number(c.fat) || null,
                confidence: Number(c.confidence) || null,
                include_in_total: true,
              })),
            } : {
              ...(userCorrectionRef.current ? { user_correction: userCorrectionRef.current } : {}),
            }),
          }
        : {
            items: items.map((item, index) => {
              const weight = weightInputs[index] || item.weight || "";
              const weightG = parseWeightG(weight);
              const itemIsNew = isNewItem(item);
              const trimmedName = (item.name || "").trim();
              const formattedWeight = formatWeight(weight) || weight;
              return { id: itemIsNew ? undefined : item.id, food_name: trimmedName, display_name: trimmedName, name: trimmedName, weight: formattedWeight, estimated_weight_g: weightG, quantity_description: formattedWeight, category: item.category || "unknown", is_new: itemIsNew, name_changed: itemIsNew || hasNameChanged(index) };
            }),
          };

      const res = await fetch(`${API_BASE}/api/foods/${recordId}/draft`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify(body),
      });

      if (res.status === 401) { localStorage.removeItem("token"); localStorage.removeItem("user"); router.push("/login"); return; }
      if (res.status === 409) { setError("该记录已保存，不能继续修改草稿"); return; }
      if (res.status === 422) { try { const payload = await res.json(); setError(normalizeErrorMessage(payload?.detail || payload)); } catch { setError("食物名称无效，请输入更具体的食物名称"); } return; }
      if (!res.ok) { try { const payload = await res.json(); setError(normalizeErrorMessage(payload?.detail || payload?.error_message || payload)); } catch { setError("修改失败，请重试"); } return; }

      setMessage("修改已应用，返回分析结果页后可保存记录");
      router.push(`/records/${recordId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "修改失败，请重试");
    } finally { setSaving(false); }
  };

  return (
    <main className="h-screen overflow-hidden bg-[#f8faf8] text-slate-950">
      <div className="grid h-screen grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={user} />
        <section className="flex h-screen min-w-0 flex-col overflow-hidden bg-white">
          <div className="mx-auto flex w-full max-w-[1480px] shrink-0 flex-col border-b border-slate-100/70 px-5 py-3.5 sm:px-6 lg:px-7">
            <TopHeader result={result} loading={loading} error={error} user={user} totals={totals} changedCount={changedCount} onBack={handleBackToResult} />
          </div>

          <div className="mx-auto flex w-full max-w-[1480px] flex-1 flex-col overflow-y-auto px-5 pb-6 sm:px-6 lg:px-7">
            {loading ? (
              <div className="flex flex-1 items-center justify-center"><Loader2 className="h-10 w-10 animate-spin text-green-600" /></div>
            ) : error && !result ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="text-center">
                  <Circle className="mx-auto h-10 w-10 text-slate-300" />
                  <p className="mt-3 text-[15px] font-bold text-slate-500">{error}</p>
                  <button type="button" onClick={handleBackToResult} className="mt-5 rounded-xl border border-slate-200 bg-white px-5 py-3 text-[15px] font-black text-slate-600 transition hover:bg-slate-50">返回分析结果</button>
                </div>
              </div>
            ) : result ? (
              <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_352px]">
                <div className="flex min-w-0 flex-col gap-4">
                  <NoticeCard isConfirmed={isConfirmed} changedCount={changedCount} />

                  <FoodEditSection
                    items={previewItems}
                    isConfirmed={isConfirmed}
                    analysisMode={result.analysisMode ?? "dish_with_components"}
                    recordId={recordId}
                    onNameChange={updateName}
                    onWeightChange={updateWeight}
                    onAdd={handleAddItem}
                    onDelete={handleDeleteItem}
                    hasNameChanged={hasNameChanged}
                    fieldErrors={fieldErrors}
                    onDishComponentsChange={(comps) => { dishComponentsRef.current = comps as Array<Record<string, unknown>>; }}
                    onUserCorrectionChange={(name) => { userCorrectionRef.current = name; }}
                  />

                  {error ? <p className="text-[13px] font-bold text-red-500">{error}</p> : null}
                  {message ? <p className="text-[13px] font-bold text-green-600">{message}</p> : null}

                  <ActionBar saving={saving} isConfirmed={isConfirmed} onConfirm={handleUpdateDraft} onBack={handleBackToResult} />
                </div>

                <div className="space-y-4 xl:sticky xl:top-5 xl:self-start">
                  <MealImageCard imageUrl={result.imageUrl} />
                  <NutritionPreviewCard totals={totals} changedCount={changedCount} />
                  <GuideCard />
                </div>
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </main>
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
      <span className="text-[24px] font-black tracking-[-0.04em] text-green-700">FoodFlow</span>
    </Link>
  );
}

function Sidebar({ user }: { user?: UserProfile | null }) {
  return (
    <aside className="hidden h-screen overflow-hidden border-r border-slate-200 bg-white px-4 py-5 lg:flex lg:flex-col">
      <AppLogo />
      <nav className="mt-7 space-y-2">
        <SidebarItem href="/dashboard" icon={<Home className="h-5 w-5" />} label="首页" />
        <SidebarItem href="/upload" icon={<CloudUpload className="h-5 w-5" />} label="上传" />
        <SidebarItem href="/records" active icon={<ClipboardList className="h-5 w-5" />} label="记录" />
        <SidebarItem href="/statistics/weekly" icon={<BarChart3 className="h-5 w-5" />} label="每周统计" />
        <SidebarItem href="/settings" icon={<Settings className="h-5 w-5" />} label="设置" />
      </nav>
      <div className="mt-auto"><AccountMenu user={user || undefined} /></div>
    </aside>
  );
}

function SidebarItem({ href, icon, label, active }: { href: string; icon: React.ReactNode; label: string; active?: boolean }) {
  return (
    <Link href={href} className={`flex h-[48px] items-center gap-4 rounded-xl px-4 text-[16px] font-black transition ${active ? "bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.08)]" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"}`}>
      <span className={active ? "text-green-600" : "text-slate-500"}>{icon}</span>{label}
    </Link>
  );
}

function TopHeader({ result, loading, error, user, totals, changedCount, onBack }: { result: AnalyzeResult | null; loading: boolean; error: string; user?: UserProfile | null; totals: { calories: number; protein: number; carbs: number; fat: number }; changedCount: number; onBack: () => void; }) {
  const isConfirmed = result?.status === "confirmed";
  void totals;
  return (
    <header className="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0">
        <button type="button" onClick={onBack} className="mb-1 inline-flex items-center gap-1.5 text-[13px] font-bold text-slate-500 transition hover:text-green-700"><ArrowLeft className="h-4 w-4" />返回分析结果</button>
        <h1 className="flex flex-wrap items-center gap-2.5 text-[27px] font-black leading-tight tracking-[-0.055em] text-slate-950">
          修改识别结果 <span className="text-[24px]">✍️</span>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-black tracking-normal ${isConfirmed ? "bg-green-50 text-green-700" : "bg-orange-50 text-orange-600"}`}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : isConfirmed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <PencilLine className="h-3.5 w-3.5" />}
            {loading ? "读取中" : isConfirmed ? "已保存" : "待确认"}
          </span>
        </h1>
        <p className="mt-0.5 text-[13px] font-semibold text-slate-500">校准菜名与成分重量，系统自动重算营养。</p>
        {error && !loading ? <p className="mt-0.5 text-[12px] font-bold text-red-500">{error}</p> : null}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <div className="text-right">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1.5 text-[12px] font-black text-green-700"><Sparkles className="h-3.5 w-3.5" />AI Workflow</div>
          <div className="mt-1 text-[12px] font-bold text-slate-500">已调整 <span className="text-slate-700">{changedCount}</span> 项</div>
        </div>
        <ProfileEntry user={user || undefined} statusText="状态良好" detailText="点击进入个人中心" />
      </div>
    </header>
  );
}

function CardShell({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-slate-200 bg-white shadow-[0_12px_30px_rgba(15,23,42,0.055)] ${className}`}>{children}</div>;
}

function CardTitle({ title, icon }: { title: string; icon?: React.ReactNode }) {
  return <div className="flex items-center gap-2.5"><h2 className="text-[19px] font-black tracking-[-0.04em] text-slate-950">{title}</h2>{icon === undefined ? <Info className="h-4 w-4 text-slate-400" /> : icon}</div>;
}

function NoticeCard({ isConfirmed, changedCount }: { isConfirmed: boolean; changedCount: number }) {
  return (
    <div className={`flex min-h-[42px] items-center gap-2.5 rounded-2xl border px-4 py-2 text-[13px] font-bold ${isConfirmed ? "border-green-200 bg-green-50 text-green-700" : "border-orange-200 bg-orange-50 text-orange-700"}`}>
      {isConfirmed ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <Info className="h-4 w-4 shrink-0" />}
      <span className="min-w-0 truncate">{isConfirmed ? "该记录已保存，不可继续修改。" : changedCount > 0 ? `当前有 ${changedCount} 项调整；确认修改仅更新草稿，正式保存请回到分析结果页。` : "修改后仍是草稿，保存记录请回到分析结果页点击「保存记录」。"}</span>
    </div>
  );
}

function FoodEditSection({
  items, isConfirmed, analysisMode = "dish_with_components", onNameChange, onWeightChange, onAdd, onDelete, hasNameChanged, fieldErrors, onDishComponentsChange, onUserCorrectionChange, recordId,
}: {
  items: EditableFoodItem[]; isConfirmed: boolean; analysisMode?: string;
  onNameChange: (index: number, value: string) => void; onWeightChange: (index: number, value: string) => void;
  onAdd: () => void; onDelete: (index: number) => void; hasNameChanged: (index: number) => boolean; fieldErrors: FieldErrors;
  onDishComponentsChange?: (components: Array<Record<string, unknown>>) => void;
  onUserCorrectionChange?: (name: string) => void;
  recordId?: string;
}) {
  const isDishMode = analysisMode === "dish_with_components" || analysisMode === "whole_dish";
  const addButtonLabel = isDishMode ? "添加成分" : "补充漏识别食物";

  console.log("[confirm FoodEditSection]", { analysisMode, isDishMode, itemsCount: items.length, hasComponents: items[0]?.components != null, componentsLength: items[0]?.components?.length, willUseEditor: isDishMode && items.length >= 1 });

  if (isDishMode && items.length >= 1) {
    return <DishWithComponentsEditor dishItem={items[0]} isConfirmed={isConfirmed} recordId={recordId} onComponentsChange={onDishComponentsChange} onUserCorrectionChange={onUserCorrectionChange} />;
  }

  return (
    <CardShell className="flex flex-col p-5">
      <div className="mb-4 flex shrink-0 items-center justify-between gap-4">
        <CardTitle title="食物重量修正" icon={<ClipboardList className="h-5 w-5 text-green-600" />} />
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-green-50 px-3 py-1 text-[12px] font-black text-green-700">{items.length} 项食物</span>
          {!isConfirmed && <button type="button" onClick={onAdd} className="flex h-9 items-center gap-1.5 rounded-xl border border-green-200 bg-green-50 px-3 text-[13px] font-black text-green-700 transition hover:bg-green-100"><Plus className="h-4 w-4" />{addButtonLabel}</button>}
        </div>
      </div>
      {items.length === 0 && !isConfirmed ? (
        <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 text-center"><Circle className="h-10 w-10 text-slate-300" /><div className="mt-3 text-[16px] font-black text-slate-700">暂无可编辑食物</div><div className="mt-1 text-[13px] font-semibold text-slate-500">点击「补充漏识别食物」添加图片中 AI 未识别的食物。</div></div>
      ) : items.length === 0 ? (
        <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 text-center"><Circle className="h-10 w-10 text-slate-300" /><div className="mt-3 text-[16px] font-black text-slate-700">暂无可编辑食物</div><div className="mt-1 text-[13px] font-semibold text-slate-500">非食物记录或空结果无需修改。</div></div>
      ) : (
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {items.map((item, index) => (
            <React.Fragment key={item.id || index}>
              <FoodEditCard item={item} index={index} isConfirmed={isConfirmed} onNameChange={onNameChange} onWeightChange={onWeightChange} onDelete={onDelete} nameChanged={hasNameChanged(index)} nameError={fieldErrors[`${index}.name`]} weightError={fieldErrors[`${index}.weight`]} />
              {item.components && item.components.length > 0 && <ComponentsBreakdown components={item.components} />}
            </React.Fragment>
          ))}
        </div>
      )}
    </CardShell>
  );
}

function DishWithComponentsEditor({
  dishItem, isConfirmed, recordId, onComponentsChange, onUserCorrectionChange,
}: {
  dishItem: EditableFoodItem; isConfirmed: boolean; recordId?: string;
  onComponentsChange?: (components: Array<{ name: string; estimatedWeightG?: number | null; calories?: number | null; protein?: number | null; carbs?: number | null; fat?: number | null; confidence?: number | null; includeInTotal?: boolean | null }>) => void;
  onUserCorrectionChange?: (name: string) => void;
}) {
  const [userCorrection, setUserCorrection] = useState<string | null>(dishItem.userCorrection ?? null);
  const [addName, setAddName] = useState("");
  const [addWeight, setAddWeight] = useState("");
  const [addChecking, setAddChecking] = useState(false);
  const [addResult, setAddResult] = useState<{ present: string; reason: string } | null>(null);
  const [showAddComponent, setShowAddComponent] = useState(false);

  const primaryName = dishItem.name || "";
  const dishFamily = dishItem.dishFamily ?? "";

  // --- DishNameCorrection: candidate generation ---
  // Primary name → candidate group (used when AI doesn't return dishFamily)
  const PRIMARY_NAME_GROUPS: Array<{ names: string[]; candidates: string[] }> = [
    { names: ["冒菜", "麻辣烫", "麻辣香锅", "火锅", "串串香"], candidates: ["冒菜", "麻辣烫", "麻辣香锅", "火锅", "串串香"] },
    { names: ["麻辣香锅", "干锅菜", "香辣炒菜"], candidates: ["麻辣香锅", "干锅菜", "香辣炒菜"] },
    { names: ["盖饭", "烩饭", "拌饭", "咖喱饭", "卤肉饭"], candidates: ["盖饭", "烩饭", "拌饭", "咖喱饭", "卤肉饭"] },
    { names: ["炒饭", "蛋炒饭", "炒面", "炒粉", "炒河粉"], candidates: ["炒饭", "蛋炒饭", "炒面", "炒粉", "炒河粉"] },
    { names: ["牛肉面", "拉面", "米线", "酸辣粉", "螺蛳粉", "热干面"], candidates: ["牛肉面", "拉面", "米线", "酸辣粉", "螺蛳粉", "热干面"] },
    { names: ["沙拉", "轻食碗", "鸡胸肉沙拉", "水果沙拉", "波奇饭"], candidates: ["沙拉", "轻食碗", "鸡胸肉沙拉", "水果沙拉", "波奇饭"] },
    { names: ["红烧肉", "红烧牛肉", "土豆牛腩", "番茄牛腩", "炖牛肉"], candidates: ["红烧肉", "红烧牛肉", "土豆牛腩", "番茄牛腩", "炖牛肉"] },
  ];

  // family → candidates (used when AI returns dishFamily)
  const FAMILY_FALLBACK: Record<string, string[]> = {};
  for (const g of PRIMARY_NAME_GROUPS) { FAMILY_FALLBACK[g.candidates[0]] = g.candidates; }
  FAMILY_FALLBACK["川式红汤混合菜"] = ["冒菜", "麻辣烫", "麻辣香锅", "火锅", "串串香"];
  FAMILY_FALLBACK["干锅炒制类"] = ["麻辣香锅", "干锅菜", "香辣炒菜"];
  FAMILY_FALLBACK["米饭盖浇类"] = ["盖饭", "烩饭", "拌饭", "咖喱饭", "卤肉饭"];
  FAMILY_FALLBACK["炒饭炒面类"] = ["炒饭", "蛋炒饭", "炒面", "炒粉", "炒河粉"];
  FAMILY_FALLBACK["汤面粉类"] = ["牛肉面", "拉面", "米线", "酸辣粉", "螺蛳粉", "热干面"];
  FAMILY_FALLBACK["沙拉轻食类"] = ["沙拉", "轻食碗", "鸡胸肉沙拉", "水果沙拉", "波奇饭"];
  FAMILY_FALLBACK["炖煮红烧类"] = ["红烧肉", "红烧牛肉", "土豆牛腩", "番茄牛腩", "炖牛肉"];

  const candidates = useMemo(() => {
    const aiNames = (dishItem.alternatives ?? []).map(a => a.name);
    // 1) dishFamily fallback
    let familyCandidates = FAMILY_FALLBACK[dishFamily] ?? [];
    // 2) primaryName fallback — match against known groups
    if (familyCandidates.length === 0) {
      for (const g of PRIMARY_NAME_GROUPS) {
        if (g.names.includes(primaryName)) { familyCandidates = g.candidates; break; }
      }
    }
    const seen = new Set<string>();
    const result: string[] = [];
    for (const name of [primaryName, ...aiNames, ...familyCandidates]) {
      if (name && !seen.has(name)) { seen.add(name); result.push(name); }
    }
    return result;
  }, [primaryName, dishFamily, dishItem.alternatives]);

  const showCandidates = candidates.length > 1;

  const handleSelectAlternative = (name: string) => { setUserCorrection(name); onUserCorrectionChange?.(name); };

  type EditableComponent = { name: string; estimatedWeightG: number | null; calories: number | null; protein: number | null; carbs: number | null; fat: number | null; confidence: number | null; includeInTotal: boolean; };

  const initComponents: EditableComponent[] = (dishItem.components?.length ?? 0) > 0
    ? dishItem.components!.map((c) => ({ name: c.name, estimatedWeightG: c.estimatedWeightG ?? null, calories: c.calories ?? null, protein: c.protein ?? null, carbs: c.carbs ?? null, fat: c.fat ?? null, confidence: c.confidence ?? null, includeInTotal: c.includeInTotal ?? true }))
    : [];

  const [comps, setComps] = useState<EditableComponent[]>(initComponents);

  const notifyChange = (next: EditableComponent[]) => { onComponentsChange?.(next.map(c => ({ name: c.name, estimatedWeightG: c.estimatedWeightG, calories: c.calories, protein: c.protein, carbs: c.carbs, fat: c.fat, confidence: c.confidence, includeInTotal: c.includeInTotal }))); };

  const updateWeight = (ci: number, value: string) => {
    setComps((prev) => {
      const next = prev.map((c, i) => {
        if (i !== ci) return c;
        const newWeight = value === "" ? null : Number(value);
        if (newWeight == null || !Number.isFinite(newWeight) || newWeight <= 0) return { ...c, estimatedWeightG: null, calories: null, protein: null, carbs: null, fat: null };
        const oldWeight = c.estimatedWeightG ?? 0;
        if (oldWeight > 0 && c.calories != null && c.calories > 0) {
          const ratio = newWeight / oldWeight;
          return { ...c, estimatedWeightG: Math.round(newWeight * 10) / 10, calories: Math.round((c.calories ?? 0) * ratio), protein: Math.round((c.protein ?? 0) * ratio * 10) / 10, carbs: Math.round((c.carbs ?? 0) * ratio * 10) / 10, fat: Math.round((c.fat ?? 0) * ratio * 10) / 10 };
        }
        return { ...c, estimatedWeightG: Math.round(newWeight * 10) / 10 };
      });
      notifyChange(next);
      return next;
    });
  };

  const deleteComponent = (ci: number) => { setComps((prev) => { const next = prev.filter((_, i) => i !== ci); notifyChange(next); return next; }); };

  const handleCheckAndAdd = async () => {
    const name = addName.trim();
    if (!name) return;
    setAddChecking(true); setAddResult(null);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/foods/check-component`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ food_name: name, record_id: recordId, context_food_items: comps.map(c => c.name).filter(Boolean) }),
      });
      const json = await res.json().catch(() => ({}));
      const present = String(json.present ?? "uncertain");
      setAddResult({ present, reason: json.reason ?? "" });
      if (present === "true") {
        const weightG = parseFloat(addWeight) || 100;
        let estCal = null, estPro = null, estCarb = null, estFat = null;
        try {
          const estRes = await fetch(`${API_BASE}/api/foods/estimate-nutrition`, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ food_name: name, weight_g: weightG }) });
          const estJson = await estRes.json().catch(() => ({}));
          estCal = estJson.calories ?? null; estPro = estJson.protein ?? null; estCarb = estJson.carbs ?? null; estFat = estJson.fat ?? null;
        } catch { /* fallback */ }
        const newComp: EditableComponent = { name, estimatedWeightG: weightG, calories: estCal, protein: estPro, carbs: estCarb, fat: estFat, confidence: 0.5, includeInTotal: true };
        setComps((prev) => { const n = [...prev, newComp]; notifyChange(n); return n; });
        setAddName(""); setAddWeight(""); setAddResult(null);
      }
    } catch {
      setAddResult({ present: "uncertain", reason: "校验请求失败，请稍后重试" });
    } finally { setAddChecking(false); }
  };

  const totalWeight = comps.length > 0 ? comps.reduce((s, c) => s + (c.estimatedWeightG ?? 0), 0) : (parseFloat(dishItem.weight) || 0);
  const totalCal = comps.length > 0 ? comps.reduce((s, c) => s + (c.calories ?? 0), 0) : (dishItem.calories ?? 0);
  const totalProtein = comps.length > 0 ? comps.reduce((s, c) => s + (c.protein ?? 0), 0) : (dishItem.protein ?? 0);
  const totalCarbs = comps.length > 0 ? comps.reduce((s, c) => s + (c.carbs ?? 0), 0) : (dishItem.carbs ?? 0);
  const totalFat = comps.length > 0 ? comps.reduce((s, c) => s + (c.fat ?? 0), 0) : (dishItem.fat ?? 0);

  const displayName = userCorrection || dishItem.name || "未知";
  const shouldScrollComponents = comps.length > 8;

  return (
    <CardShell className="relative flex flex-col overflow-visible p-5">
      {/* Dish hero */}
      <div className="mb-4 rounded-2xl border border-green-200 bg-gradient-to-br from-green-50 via-emerald-50/70 to-white p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="rounded-full bg-green-100 px-2.5 py-1 text-[11px] font-black text-green-700">识别为</span>
          <span className="text-[23px] font-black tracking-[-0.045em] text-slate-900">{displayName}</span>
          {userCorrection ? <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-bold text-violet-600">用户已校正</span> : <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-bold text-slate-400 ring-1 ring-slate-200">名称只读</span>}
          {dishFamily ? <span className="rounded-full bg-white/75 px-2 py-0.5 text-[11px] font-bold text-green-700 ring-1 ring-green-100">{dishFamily}</span> : null}
        </div>

        {!isConfirmed && (
          <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-2 rounded-xl bg-white/45 px-3 py-2 ring-1 ring-green-100/80">
            {showCandidates ? (
              <>
                <span className="text-[12px] font-black text-slate-600">菜名确认：</span>
                {candidates.map((name) => {
                  const isSelected = name === displayName;
                  return (
                    <button key={name} type="button" onClick={() => !isSelected && handleSelectAlternative(name)}
                      className={`rounded-full px-3 py-1.5 text-[12px] font-black transition ${
                        isSelected ? "bg-green-500 text-white shadow-[0_6px_14px_rgba(34,197,94,0.24)] cursor-default" : "border border-amber-200 bg-white text-amber-700 hover:border-green-200 hover:bg-green-50 hover:text-green-700"
                      }`}>
                      {name}{isSelected ? " ✓" : ""}
                    </button>
                  );
                })}
              </>
            ) : (
              <div className="flex flex-wrap items-center gap-2 text-[12px] font-bold text-amber-700">
                <span>菜名不准确？</span>
                <span className="text-amber-600">菜名校准校验能力待接入，当前请通过重新分析处理。</span>
              </div>
            )}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <DishMetric label="热量" value={Math.round(totalCal)} unit="kcal" tone="text-orange-500" />
          <DishMetric label="重量" value={Math.round(totalWeight)} unit="g" tone="text-slate-700" />
          <DishMetric label="蛋白质" value={Math.round(totalProtein)} unit="g" tone="text-green-600" />
          <DishMetric label="碳水" value={Math.round(totalCarbs)} unit="g" tone="text-orange-500" />
          <DishMetric label="脂肪" value={Math.round(totalFat)} unit="g" tone="text-violet-600" />
        </div>

        {comps.length === 0 ? (
          <div className="mt-3 flex items-center gap-2 rounded-xl bg-amber-50 px-3 py-2 text-[12px] font-bold text-amber-700"><AlertCircle className="h-4 w-4 shrink-0" />未获取到成分明细，当前显示为 AI 估算值。</div>
        ) : (
          <p className="mt-2 text-[11px] font-bold text-green-700">总量由下方成分自动汇总，修改重量后实时更新。</p>
        )}
      </div>

      {/* Components table */}
      <div className="mb-2.5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5"><ClipboardList className="h-5 w-5 text-green-600" /><h2 className="text-[18px] font-black tracking-[-0.04em] text-slate-950">成分明细</h2></div>
        <span className="rounded-full bg-green-50 px-3 py-1 text-[12px] font-black text-green-700">{comps.length} 项成分</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-100 bg-white">
        <div className="grid h-10 shrink-0 grid-cols-[minmax(120px,1.35fr)_84px_82px_82px_56px_36px] items-center bg-slate-50/90 px-3.5 text-[12px] font-black text-slate-500"><div>成分</div><div>重量</div><div>热量</div><div>蛋白质</div><div>置信</div><div></div></div>
        <div className={shouldScrollComponents ? "max-h-[372px] overflow-y-auto" : ""}>
          {comps.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-1.5 py-8 text-center"><AlertCircle className="h-7 w-7 text-amber-400" /><p className="text-[13px] font-black text-slate-500">未获取到成分明细</p><p className="text-[11px] font-bold text-slate-400">请使用下方「检查并添加」补充成分</p></div>
          )}
          {comps.map((c, ci) => (
            <div key={ci} className="grid min-h-[44px] grid-cols-[minmax(120px,1.35fr)_84px_82px_82px_56px_36px] items-center gap-1 border-t border-slate-100 px-3.5 text-[13px] transition hover:bg-slate-50/70">
              <span className="truncate font-black text-slate-800">{c.name}</span>
              <input value={c.estimatedWeightG ?? ""} disabled={isConfirmed} placeholder="g" onChange={(e) => updateWeight(ci, e.target.value)} className="h-8 w-full rounded-lg border border-slate-200 bg-white px-2 text-[12px] font-bold text-slate-700 outline-none focus:border-green-500 focus:ring-2 focus:ring-green-500/10 tabular-nums disabled:bg-slate-50 disabled:text-slate-400" />
              <span className="font-bold text-orange-500 tabular-nums text-[12px]">{c.calories != null && c.calories > 0 ? `${Math.round(c.calories)}kcal` : "-"}</span>
              <span className="font-bold text-green-600 tabular-nums text-[12px]">{c.protein != null && c.protein > 0 ? `${Math.round(c.protein)}g` : "-"}</span>
              <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-center text-[10px] font-bold text-slate-500">{c.confidence ? Math.round(c.confidence * 100) + "%" : "-"}</span>
              {!isConfirmed && <button type="button" onClick={() => deleteComponent(ci)} className="grid h-7 w-7 place-items-center rounded-lg text-slate-300 transition hover:bg-red-50 hover:text-red-500"><X className="h-3.5 w-3.5" /></button>}
            </div>
          ))}
        </div>
      </div>

      {/* Add component — compact popover */}
      {!isConfirmed && (
        <div className="relative mt-3 rounded-xl border border-slate-200 bg-white">
          <button type="button" onClick={() => setShowAddComponent(!showAddComponent)} className="flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left transition hover:bg-green-50/45">
            <span className="flex min-w-0 items-center gap-2">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-green-50 text-green-600"><Plus className="h-4 w-4" /></span>
              <span className="min-w-0">
                <span className="block text-[13px] font-black text-slate-700">添加餐内成分</span>
                <span className="block truncate text-[11px] font-bold text-slate-400">仅可添加系统能在当前餐图中确认可能存在的成分</span>
              </span>
            </span>
            <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${showAddComponent ? "rotate-180" : ""}`} />
          </button>
          {showAddComponent && (
            <div className="absolute left-0 right-0 top-full z-30 mt-2 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-[0_18px_45px_rgba(15,23,42,0.14)]">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <div className="text-[13px] font-black text-slate-800">让 AI 检查并添加餐内成分</div>
                  <div className="mt-0.5 text-[11px] font-bold text-slate-400">通过图片存在性校验后才会加入明细</div>
                </div>
                <button type="button" onClick={() => setShowAddComponent(false)} className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-50 hover:text-slate-700"><X className="h-3.5 w-3.5" /></button>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input value={addName} onChange={(e) => { setAddName(e.target.value); setAddResult(null); }} placeholder="成分名称，例如：虾仁、豆腐" className="h-9 min-w-[150px] flex-1 rounded-lg border border-slate-200 bg-white px-3 text-[13px] font-bold outline-none transition focus:border-green-500 focus:ring-2 focus:ring-green-500/10" />
                <div className="flex items-center gap-1"><input value={addWeight} onChange={(e) => setAddWeight(e.target.value)} placeholder="100" className="h-9 w-[76px] rounded-lg border border-slate-200 bg-white px-2.5 text-[13px] font-bold outline-none focus:border-green-500 tabular-nums" /><span className="text-[11px] font-bold text-slate-400">g</span></div>
                <button type="button" onClick={handleCheckAndAdd} disabled={addChecking || !addName.trim()} className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-green-600 px-4 text-[12px] font-black text-white shadow-[0_6px_16px_rgba(34,197,94,0.18)] transition hover:bg-green-700 disabled:opacity-50">
                  {addChecking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}检查并添加
                </button>
              </div>
              {addResult && (
                <div className={`mt-2 flex items-start gap-2 rounded-lg px-3 py-2 text-[12px] font-bold ${addResult.present === "true" ? "bg-green-50 text-green-700" : addResult.present === "false" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-700"}`}>
                  {addResult.present === "true" ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : addResult.present === "false" ? <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                  <span>{addResult.present === "true" ? "系统判断该成分可能存在，已添加到成分明细" : addResult.present === "false" ? "未在当前餐图中识别到该成分，暂不能添加" : addResult.reason || "系统无法确认该成分是否在图中，建议重新分析或重新拍摄"}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Totals — light footer */}
      <div className="mt-3 flex items-center gap-3 rounded-xl bg-slate-50 px-3.5 py-2.5 text-[12px]">
        <span className="font-black text-slate-600">成分合计</span>
        <span className="font-bold text-slate-600">{Math.round(totalWeight)}g</span>
        <span className="font-bold text-orange-500">{Math.round(totalCal)} kcal</span>
        <span className="ml-auto text-[10px] font-bold text-green-600">此合计即主餐总量，计入饮食记录</span>
      </div>
    </CardShell>
  );
}

function DishMetric({ label, value, unit, tone }: { label: string; value: number; unit: string; tone: string }) {
  return (
    <div className="inline-flex h-9 min-w-[92px] items-center justify-center gap-1.5 rounded-xl bg-white/80 px-3 text-center ring-1 ring-white/90">
      <span className={`text-[14px] font-black tracking-[-0.04em] ${tone}`}>{value}</span>
      <span className="text-[10px] font-black text-slate-400">{unit}</span>
      <span className="text-[10px] font-black text-slate-400">{label}</span>
    </div>
  );
}


function ComponentsBreakdown({ components }: { components: Array<{ name: string; confidence?: number | null; estimatedWeightG?: number | null; calories?: number | null; role?: string | null; includeInTotal?: boolean | null }>; }) {
  const totalWeight = components.reduce((sum, c) => sum + (c.estimatedWeightG ?? 0), 0);
  const totalCal = components.reduce((sum, c) => sum + (c.calories ?? 0), 0);
  return (
    <div className="rounded-2xl border border-dashed border-green-200 bg-green-50/30 p-4">
      <div className="mb-3 flex items-center gap-2"><Info className="h-4 w-4 text-green-600" /><span className="text-[14px] font-black text-green-800">可能包含</span><span className="text-[11px] font-bold text-green-600">成分仅用于解释，不重复计入总热量</span></div>
      <div className="space-y-2">
        {components.map((c, ci) => {
          const sourceLabel = c.confidence && c.confidence >= 0.5 ? "AI识别" : "估算补全";
          const hasWeight = c.estimatedWeightG != null && c.estimatedWeightG > 0;
          const hasCal = c.calories != null && c.calories > 0;
          return (
            <div key={ci} className="flex flex-wrap items-center gap-2 rounded-xl bg-white px-3 py-2 text-[13px] shadow-[0_2px_8px_rgba(15,23,42,0.03)]">
              <span className="font-black text-slate-700 min-w-[90px]">{c.name}</span>
              {hasWeight ? <span className="font-bold text-slate-500 tabular-nums">{c.estimatedWeightG}g</span> : <span className="font-bold text-slate-400">-</span>}
              {hasCal ? <span className="font-bold text-orange-500 tabular-nums">{c.calories}kcal</span> : <span className="font-bold text-slate-400">-</span>}
              <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">{Math.round((c.confidence ?? 0) * 100)}%</span>
              <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-400">{sourceLabel}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center gap-4 text-[11px] font-bold text-green-700"><span>成分总重: {totalWeight}g</span><span>成分总热量: {totalCal}kcal</span><span className="text-slate-400">(不计入总计)</span></div>
    </div>
  );
}

function FoodEditCard({ item, index, isConfirmed, onNameChange, onWeightChange, onDelete, nameChanged = false, nameError, weightError }: { item: EditableFoodItem; index: number; isConfirmed: boolean; onNameChange: (index: number, value: string) => void; onWeightChange: (index: number, value: string) => void; onDelete: (index: number) => void; nameChanged?: boolean; nameError?: string; weightError?: string; }) {
  const itemIsNew = isNewItem(item);
  const isPending = itemIsNew && (item.previewCalories ?? 0) < 0;
  const needsReEstimate = nameChanged && !isPending;
  const components = Array.isArray(item.components) ? item.components : [];
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-[0_8px_24px_rgba(15,23,42,0.035)]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[12px] font-black">
            {itemIsNew ? <span className="text-violet-600">补充漏识别</span> : <span className="text-slate-400">{formatFoodItemLabels(item)}</span>}
            {!itemIsNew && components.length > 0 && (
              <div className="flex flex-wrap items-center gap-1"><span className="text-[10px] font-bold text-slate-400">可能包含</span>{components.map((component, componentIndex) => (<span key={`${component.name || "component"}-${componentIndex}`} className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">{component.name || "未知"}</span>))}</div>
            )}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-[15px] font-black text-slate-700">#{index + 1}</span>
            {isPending ? <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-black text-violet-600">待估算</span> : needsReEstimate ? <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-black text-violet-600">待重新估算</span> : item.hasWeightChange ? <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[11px] font-black text-orange-600">预览重算</span> : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-black text-slate-500">原始估算</span>}
          </div>
        </div>
        {!isConfirmed && <button type="button" onClick={() => onDelete(index)} className="grid h-8 w-8 place-items-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-500"><X className="h-4 w-4" /></button>}
      </div>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_156px]">
        <Field label="食物名称" value={item.name} disabled={isConfirmed} error={nameError} onChange={(value) => onNameChange(index, value)} />
        <Field label="重量" value={item.weight} disabled={isConfirmed} placeholder="例如 150g" error={weightError} onChange={(value) => onWeightChange(index, value)} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {isPending || needsReEstimate ? (<><PendingMetric label="热量" /><PendingMetric label="蛋白质" /><PendingMetric label="碳水" /><PendingMetric label="脂肪" /></>) : (<>
          <ReadOnlyMetric label="热量" value={`${item.previewCalories ?? item.calories} kcal`} highlight={item.hasWeightChange} tone="text-orange-500" />
          <ReadOnlyMetric label="蛋白质" value={`${item.previewProtein ?? item.protein}g`} highlight={item.hasWeightChange} tone="text-green-600" />
          <ReadOnlyMetric label="碳水" value={`${item.previewCarbs ?? item.carbs}g`} highlight={item.hasWeightChange} tone="text-orange-500" />
          <ReadOnlyMetric label="脂肪" value={`${item.previewFat ?? item.fat}g`} highlight={item.hasWeightChange} tone="text-violet-600" />
        </>)}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, disabled, placeholder, error }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean; placeholder?: string; error?: string; }) {
  return (
    <label className="block" data-field-error={error ? "true" : "false"}>
      <span className="mb-1.5 block text-[12px] font-black text-slate-500">{label}</span>
      <input value={value} disabled={disabled} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className={`h-11 w-full rounded-xl border bg-white px-3 text-[14px] font-black text-slate-800 outline-none transition disabled:bg-slate-50 disabled:text-slate-400 ${error ? "border-red-300 bg-red-50/40 focus:border-red-400 focus:ring-4 focus:ring-red-500/10" : "border-slate-200 focus:border-green-500 focus:ring-4 focus:ring-green-500/10"}`} />
      {error ? <p className="mt-1.5 text-[12px] font-bold text-red-500">{error}</p> : null}
    </label>
  );
}

function PendingMetric({ label }: { label: string }) { return <div className="rounded-xl bg-violet-50 px-3 py-2.5 text-center"><div className="text-[11px] font-black text-violet-400">{label}</div><div className="mt-1 text-[14px] font-black text-violet-500">待估算</div></div>; }

function ReadOnlyMetric({ label, value, highlight, tone }: { label: string; value: string; highlight?: boolean; tone: string }) {
  return <div className={`rounded-xl px-3 py-2.5 text-center ${highlight ? "bg-orange-50" : "bg-slate-50"}`}><div className="text-[11px] font-black text-slate-400">{label}</div><div className={`mt-1 text-[14px] font-black ${highlight ? "text-orange-600" : tone}`}>{value}</div></div>;
}

function MealImageCard({ imageUrl }: { imageUrl?: string }) {
  const [failed, setFailed] = useState(false);
  const src = resolveImg(imageUrl);
  return (
    <CardShell className="overflow-hidden p-4">
      <div className="mb-3 flex items-center justify-between gap-3"><CardTitle title="餐食图片" icon={<ImageIcon className="h-5 w-5 text-green-600" />} /><span className="rounded-full bg-green-50 px-3 py-1 text-[12px] font-black text-green-700">已上传</span></div>
      <div className="h-[206px] overflow-hidden rounded-xl bg-gradient-to-br from-amber-50 to-stone-100 2xl:h-[228px]">{src && !failed ? <img src={src} alt="餐食图片" className="h-full w-full object-cover" onError={() => setFailed(true)} /> : <MealMockImage />}</div>
    </CardShell>
  );
}

function MealMockImage() {
  return (
    <div className="relative h-full overflow-hidden rounded-xl bg-gradient-to-br from-amber-50 to-stone-100">
      <div className="absolute inset-x-5 bottom-[-34px] h-[128px] rounded-[50%] bg-white shadow-[inset_0_-14px_24px_rgba(120,113,108,0.12),0_18px_24px_rgba(15,23,42,0.12)]" />
      <div className="absolute left-8 top-10 h-[58px] w-[92px] rotate-[-12deg] rounded-[45%] bg-orange-400 shadow-[0_0_0_4px_#fdba74]" />
      <div className="absolute left-[116px] top-12 h-11 w-14 rounded-[45%] bg-yellow-300 shadow-[24px_6px_0_#facc15,52px_-4px_0_#fde047]" />
      <div className="absolute right-8 top-12 h-14 w-18 rounded-[45%] bg-green-500 shadow-[-18px_18px_0_#22c55e]" />
      <div className="absolute bottom-10 left-12 h-6 w-6 rounded-full bg-red-400 shadow-[28px_7px_0_#ef4444,58px_1px_0_#f97316]" />
    </div>
  );
}

function NutritionPreviewCard({ totals, changedCount }: { totals: { calories: number; protein: number; carbs: number; fat: number }; changedCount: number }) {
  return (
    <CardShell className="p-5">
      <div className="mb-4 flex items-center justify-between gap-3"><CardTitle title="营养预览" icon={<Sparkles className="h-5 w-5 text-violet-600" />} />{changedCount > 0 ? <span className="rounded-full bg-orange-100 px-3 py-1 text-[12px] font-black text-orange-600">已重算</span> : null}</div>
      <div className="grid grid-cols-2 gap-3.5">
        <PreviewTotal label="热量" value={Math.round(totals.calories)} unit="kcal" tone="text-orange-500" />
        <PreviewTotal label="蛋白质" value={Math.round(totals.protein)} unit="g" tone="text-green-600" />
        <PreviewTotal label="碳水" value={Math.round(totals.carbs)} unit="g" tone="text-orange-500" />
        <PreviewTotal label="脂肪" value={Math.round(totals.fat)} unit="g" tone="text-violet-600" />
      </div>
    </CardShell>
  );
}

function PreviewTotal({ label, value, unit, tone }: { label: string; value: number; unit: string; tone: string }) {
  return <div className="rounded-xl bg-slate-50 px-3 py-3 text-center"><div className={`text-[22px] font-black tracking-[-0.06em] ${tone}`}>{value}</div><div className="mt-0.5 text-[11px] font-black text-slate-400">{label} {unit}</div></div>;
}

function GuideCard() {
  return (
    <CardShell className="p-5">
      <div className="mb-4 flex items-center gap-2.5"><ShieldCheck className="h-5 w-5 text-green-600" /><CardTitle title="修改说明" icon={null} /></div>
      <div className="space-y-3">
        <GuideRow icon={<CheckCircle2 className="h-4 w-4" />} text="普通用户只需修改食物名称与重量。" />
        <GuideRow icon={<CheckCircle2 className="h-4 w-4" />} text="热量、蛋白质、碳水、脂肪会按原营养密度自动重算。" />
        <GuideRow icon={<RotateCcw className="h-4 w-4" />} text="确认修改后仍是草稿，不会进入正式饮食记录。" />
        <GuideRow icon={<Save className="h-4 w-4" />} text={'回到分析结果页后，再点击「保存记录」才正式保存。'} />
      </div>
    </CardShell>
  );
}

function GuideRow({ icon, text }: { icon: React.ReactNode; text: string }) {
  return <div className="flex items-start gap-2.5 text-[14px] font-semibold leading-6 text-slate-600"><span className="mt-1 shrink-0 text-green-600">{icon}</span><span>{text}</span></div>;
}

function ActionBar({ saving, isConfirmed, onConfirm, onBack }: { saving: boolean; isConfirmed: boolean; onConfirm: () => void; onBack: () => void; }) {
  return (
    <div className="mt-4 grid shrink-0 gap-3 border-t border-slate-100 pt-5 md:grid-cols-2">
      <div>
        <button type="button" onClick={onConfirm} disabled={saving || isConfirmed} className="flex h-[52px] w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-b from-orange-400 to-orange-600 text-[17px] font-black text-white shadow-[0_12px_28px_rgba(249,115,22,0.24)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(249,115,22,0.3)] disabled:opacity-60 disabled:hover:translate-y-0">
          {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : isConfirmed ? <BadgeCheck className="h-5 w-5" /> : <PencilLine className="h-5 w-5" />}
          {saving ? "修改中..." : isConfirmed ? "已保存" : "确认修改"}
        </button>
        {!isConfirmed && <p className="mt-1.5 text-center text-[11px] font-bold text-slate-400">仅更新草稿，不保存为正式饮食记录</p>}
      </div>
      <button type="button" onClick={onBack} className="flex h-[52px] items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white text-[16px] font-black text-slate-600 shadow-[0_12px_30px_rgba(15,23,42,0.045)] transition hover:bg-slate-50"><ArrowLeft className="h-5 w-5" />返回分析结果</button>
    </div>
  );
}
