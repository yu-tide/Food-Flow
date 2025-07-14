'use client'

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import {
  AlertCircle,
  ArrowLeft,
  BadgeCheck,
  BarChart3,
  Circle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  CloudUpload,
  Code2,

  Download,
  Droplet,
  Home,
  ImageIcon,
  Leaf,
  Loader2,
  PencilLine,
  Plus,
  RotateCcw,
  Save,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Wheat,
} from 'lucide-react'
import AccountMenu from '@/components/user/AccountMenu'
import ProfileEntry from '@/components/user/ProfileEntry';
import { ApiError } from '@/services/api'
import { formatFoodItemLabels } from '@/lib/foodLabels'
import { getFoodRecord, type AnalyzeResult, type FoodItem, type MacroInfo } from '@/services/foods'

type MacroKey = 'protein' | 'carbs' | 'fat'

type UserProfile = {
  nickname: string
  phone: string
  avatarText: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

function getUserProfile(): UserProfile {
  if (typeof window === 'undefined') return { nickname: '', phone: '', avatarText: '' }
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const u = JSON.parse(raw)
      return {
        nickname: u.nickname || '',
        phone: u.phone || '',
        avatarText: u.avatarText || u.nickname?.[0] || '',
      }
    }
  } catch { /* ignore */ }
  return { nickname: '', phone: '', avatarText: '' }
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function formatDate(value?: string) {
  if (!value) return '今天'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '今天'
  return date.toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
  })
}

const macroToneMap: Record<
  MacroKey,
  {
    icon: React.ReactNode
    iconClassName: string
    barClassName: string
    textClassName: string
  }
> = {
  protein: {
    icon: <Target className="h-5 w-5" />,
    iconClassName: 'bg-green-50 text-green-600',
    barClassName: 'bg-green-500',
    textClassName: 'text-green-600',
  },
  carbs: {
    icon: <Wheat className="h-5 w-5" />,
    iconClassName: 'bg-orange-50 text-orange-500',
    barClassName: 'bg-orange-400',
    textClassName: 'text-orange-500',
  },
  fat: {
    icon: <Droplet className="h-5 w-5" />,
    iconClassName: 'bg-violet-50 text-violet-600',
    barClassName: 'bg-violet-600',
    textClassName: 'text-violet-600',
  },
}

export default function RecordDetailPage() {
  const router = useRouter()
  const params = useParams()

  const recordId = useMemo(() => {
    const value = params?.id
    return Array.isArray(value) ? value[0] : String(value ?? '')
  }, [params])

  const [user] = useState<UserProfile>(getUserProfile)
  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [foodItems, setFoodItems] = useState<FoodItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const loadRecord = useCallback(async () => {
    if (!recordId) return
    setLoading(true)
    setErrorMessage('')
    try {
      const data = await getFoodRecord(recordId)
      setResult(data)
      setFoodItems(data.foodItems)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          router.push('/login')
          return
        }
        if (err.status === 404) {
          setErrorMessage('记录不存在或无权限访问')
          setLoading(false)
          return
        }
      }
      setErrorMessage('结果加载失败')
    } finally {
      setLoading(false)
    }
  }, [recordId, router])

  useEffect(() => {
    loadRecord()
  }, [loadRecord])

  async function handleSaveRecord() {
    setSaving(true); setSaveMsg('')
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`${API_BASE}/api/foods/${recordId}/confirm`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: '{}',
      })
      if (res.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); router.push('/login'); return }
      if (!res.ok) throw new Error('保存失败')
      setSaveMsg('保存成功')
      router.push('/records')
    } catch {
      setSaveMsg('保存失败，请重试')
    } finally { setSaving(false) }
  }

  function handleReAnalyze() {
    router.push('/upload')
  }

  function handleExport() {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: 'application/json;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `foodflow-record-${result.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Render loading / error states
  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="h-10 w-10 animate-spin text-green-600" />
        </div>
      )
    }
    if (!result) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-[16px] font-semibold text-slate-500">{errorMessage || '数据加载失败'}</p>
        </div>
      )
    }
    const isNonFood = result.foodItems.length === 0 && result.totalCalories === 0

    if (isNonFood) {
      const isConfirmed = result?.status === 'confirmed'
      return (
        <div className="mt-4 grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-h-0 flex-col items-center justify-center gap-4 rounded-2xl border border-slate-200 bg-white p-10 text-center">
            <Circle className="h-12 w-12 text-slate-300" />
            <h2 className="text-xl font-black text-slate-700">未识别到可分析的食物</h2>
            <p className="max-w-md text-sm font-semibold text-slate-500">{result?.aiSummary?.[0] || '这张图片可能不包含食物，或食物内容不够清晰，暂时无法生成营养估算。'}</p>
            <p className="text-xs font-bold text-slate-400">状态：{isConfirmed ? '已保存' : '待确认'}</p>
            <div className="flex gap-3">
              {!isConfirmed && (
                <button onClick={handleSaveRecord} disabled={saving} className="rounded-xl bg-green-600 px-4 py-2 text-sm font-bold text-white hover:bg-green-700 disabled:opacity-60">
                  {saving ? '保存中...' : '保存这次记录'}
                </button>
              )}
              <button onClick={handleReAnalyze} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50">重新上传</button>
              <Link href="/records" className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50">返回记录</Link>
            </div>
            {saveMsg && <p className="text-[13px] font-bold text-green-600">{saveMsg}</p>}
          </div>
          <div className="flex min-h-0 flex-col gap-4 overflow-hidden">
            <MealImageCard imageUrl={result.imageUrl} />
            {result.aiSummary.length > 0 && <AiSummaryCard summary={result.aiSummary} />}
          </div>
        </div>
      )
    }

    return (
      <div className="mt-4 grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-h-0 min-w-0 flex-col gap-4 overflow-hidden">
          <div className="grid shrink-0 gap-4 lg:grid-cols-[330px_minmax(0,1fr)]">
            <CalorieResultCard result={result} />
            <MacroResultCard macros={result.macros} />
          </div>
          {result.analysisMode === "dish_with_components" || result.analysisMode === "whole_dish"
            ? <DishWithComponentsResult result={result} recordId={recordId} readOnly={result?.status === 'confirmed'} />
            : <FoodItemsCard items={foodItems} onItemsChange={setFoodItems} readOnly={result?.status === 'confirmed'} recordId={recordId} />
          }
          <ActionBar onSave={handleSaveRecord} onReAnalyze={handleReAnalyze} onExport={handleExport} confirmed={result?.status === 'confirmed'} saving={saving} saveMsg={saveMsg} />
        </div>
        <div className="flex min-h-0 flex-col gap-4 overflow-hidden">
          <MealImageCard imageUrl={result.imageUrl} />
          <AiSummaryCard summary={result.aiSummary} />
          <TechDetailsCard technical={result.technical} />
        </div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-white text-slate-950 lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={user} />

        <section className="min-w-0 bg-white lg:h-screen lg:overflow-hidden">
          <div className="flex min-h-screen w-full flex-col px-5 py-4 sm:px-6 lg:h-screen lg:min-h-0 lg:px-8">
            <TopHeader
              user={user}
              result={result}
              loading={loading}
              errorMessage={errorMessage}
            />
            {renderContent()}
          </div>
        </section>
      </div>
    </main>
  )
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
  )
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
          icon={<CloudUpload className="h-5 w-5" />}
          label="上传"
        />
        <SidebarItem
          href="/records"
          active
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

      <div className="mt-auto space-y-4">

        <AccountMenu user={user || undefined} />
      </div>
    </aside>
  )
}

function SidebarItem({
  href,
  icon,
  label,
  active,
}: {
  href: string
  icon: React.ReactNode
  label: string
  active?: boolean
}) {
  return (
    <Link
      href={href}
      className={`flex h-[48px] items-center gap-4 rounded-xl px-4 text-[16px] font-black transition ${
        active
          ? 'bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.08)]'
          : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
      }`}
    >
      <span className={active ? 'text-green-600' : 'text-slate-500'}>
        {icon}
      </span>
      {label}
    </Link>
  )
}

function TopHeader({
  user,
  result,
  loading,
  errorMessage,
}: {
  user: UserProfile
  result: AnalyzeResult | null
  loading: boolean
  errorMessage: string
}) {
  return (
    <header className="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <Link
          href="/records"
          className="mb-1.5 inline-flex items-center gap-2 text-[14px] font-black text-slate-500 transition hover:text-green-700"
        >
          <ArrowLeft className="h-4 w-4" />
          返回饮食记录
        </Link>

        <h1 className="flex flex-wrap items-center gap-3 text-[30px] font-black leading-tight tracking-[-0.06em] text-slate-950">
          分析结果
          <span className="text-3xl">🥗</span>

          <span className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[14px] font-black tracking-normal ${result?.status === 'confirmed' ? 'bg-green-50 text-green-700' : 'bg-orange-50 text-orange-600'}`}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : result?.status === 'confirmed' ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {loading ? '读取中' : result?.status === 'confirmed' ? (result?.statusLabel ?? '已确认') : '待确认'}
          </span>
        </h1>

        <p className="mt-1 text-[15px] font-semibold text-slate-500">
          {formatDate(result?.createdAt)} 的 OCR 识别、营养分析与 AI 总结结果。
        </p>

        {errorMessage ? (
          <p className="mt-1 text-[13px] font-bold text-orange-600">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="flex items-center gap-4 lg:pt-0.5">
        <div className="text-right">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
            <Sparkles className="h-4 w-4" />
            AI Workflow
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            本餐后还剩{' '}
            <span className="font-black text-slate-700">
              {result?.remainingCalories?.toLocaleString() ?? '0'}
            </span>{' '}
            kcal
          </div>
        </div>

        <ProfileEntry user={user || undefined} statusText="状态良好" detailText="点击进入个人中心" />
      </div>
    </header>
  )
}

function CardShell({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={`rounded-2xl border border-slate-200 bg-white shadow-[0_12px_30px_rgba(15,23,42,0.055)] ${className}`}
    >
      {children}
    </div>
  )
}

function CardTitle({
  icon,
  title,
}: {
  icon?: React.ReactNode
  title: string
}) {
  return (
    <div className="flex items-center gap-2.5">
      <h2 className="text-[19px] font-black tracking-[-0.04em] text-slate-950">
        {title}
      </h2>
      {icon}
    </div>
  )
}

function CalorieResultCard({ result }: { result: AnalyzeResult }) {
  const rawPercent =
    result.targetCalories > 0
      ? Math.round((result.totalCalories / result.targetCalories) * 100)
      : 0

  const progressPercent = clampPercent(rawPercent)
  const degrees = Math.round((progressPercent / 100) * 360)

  return (
    <CardShell className="flex h-[224px] flex-col p-5">
      <CardTitle title="本餐热量" />

      <div className="flex flex-1 items-center justify-center py-1">
        <div
          className="relative grid h-[118px] w-[118px] place-items-center rounded-full"
          style={{
            background: `conic-gradient(#35ad5f 0deg ${degrees}deg, #eef0f2 ${degrees}deg 360deg)`,
          }}
        >
          <div className="absolute h-[90px] w-[90px] rounded-full bg-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.02)]" />

          <div className="relative text-center">
            <div className="text-[27px] font-black tracking-[-0.06em] text-slate-950">
              {result.totalCalories.toLocaleString()}
            </div>
            <div className="mt-0.5 text-[12px] font-black text-slate-500">
              kcal
            </div>
          </div>
        </div>
      </div>

      <div className="mt-auto grid grid-cols-2 border-t border-slate-100 pt-3">
        <div className="min-w-0">
          <div className="truncate text-[21px] font-black leading-none tracking-[-0.05em] text-orange-500">
            {result.remainingCalories.toLocaleString()}
          </div>
          <div className="mt-1 text-[12px] font-black text-slate-500">
            今日剩余
          </div>
        </div>

        <div className="min-w-0 text-right">
          <div className="truncate text-[21px] font-black leading-none tracking-[-0.05em] text-slate-700">
            {result.targetCalories.toLocaleString()}
          </div>
          <div className="mt-1 text-[12px] font-black text-slate-500">
            今日目标
          </div>
        </div>
      </div>
    </CardShell>
  )
}

function MacroResultCard({ macros }: { macros: MacroInfo[] }) {
  return (
    <CardShell className="flex h-[224px] flex-col overflow-hidden">
      <div className="flex-1 p-5">
        <CardTitle title="宏量营养素" />

        <div className="mt-4 space-y-4">
          {macros.map((item) => (
            <MacroProgressRow key={item.key} item={item} />
          ))}
        </div>
      </div>

      <Link
        href="/statistics/weekly"
        className="flex h-[38px] shrink-0 items-center justify-center gap-3 border-t border-slate-200 text-[15px] font-black text-green-700 transition hover:bg-green-50"
      >
        查看每周趋势
        <ChevronRight className="h-4 w-4" />
      </Link>
    </CardShell>
  )
}

function MacroProgressRow({ item }: { item: MacroInfo }) {
  const tone = macroToneMap[item.key]
  const rawPercent = item.target > 0 ? Math.round((item.value / item.target) * 100) : 0
  const progressPercent = clampPercent(rawPercent)
  const isOver = rawPercent > 100
  const overAmount = Math.max(0, Math.round((item.value - item.target) * 10) / 10)

  return (
    <div className="grid grid-cols-[42px_minmax(0,1fr)] items-center gap-3">
      <div
        className={`grid h-10 w-10 place-items-center rounded-full ${tone.iconClassName}`}
      >
        {tone.icon}
      </div>

      <div className="min-w-0">
        <div className="mb-1.5 flex items-center justify-between gap-3">
          <div className="text-[15px] font-black text-slate-800">
            {item.label}
          </div>

          <div className="min-w-0 whitespace-nowrap text-right text-[14px] font-bold text-slate-500">
            <span className="font-black text-slate-700">
              {item.value}
              {item.unit}
            </span>{' '}
            / {item.target}
            {item.unit}
            <span className={`ml-3 font-black ${isOver ? 'text-orange-600' : 'text-slate-600'}`}>
              {rawPercent}%
            </span>
          </div>
        </div>

        <div className="h-2.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full rounded-full ${tone.barClassName}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {isOver ? (
          <div className="mt-1 text-right text-[11px] font-black text-orange-600">
            已超标 {overAmount}{item.unit}
          </div>
        ) : null}
      </div>
    </div>
  )
}


function DishWithComponentsResult({
  result,
  recordId,
  readOnly,
}: {
  result: AnalyzeResult;
  recordId?: string;
  readOnly?: boolean;
}) {
  const dishItem = result.foodItems[0];
  const components = dishItem?.components && dishItem.components.length > 0
    ? dishItem.components
    : [];
  const hasComponents = components.length > 0;
  // When components present: totals from components sum. When empty: fallback to dishItem stored values.
  const totalWeight = hasComponents
    ? components.reduce((s, c) => s + (c.estimatedWeightG ?? 0), 0)
    : (parseFloat(dishItem?.weight || "0") || 0);
  const totalCal = hasComponents
    ? components.reduce((s, c) => s + (c.calories ?? 0), 0)
    : (dishItem?.calories ?? 0);
  const totalProtein = hasComponents
    ? components.reduce((s, c) => s + (c.protein ?? 0), 0)
    : (dishItem?.protein ?? 0);
  const totalCarbs = hasComponents
    ? components.reduce((s, c) => s + (c.carbs ?? 0), 0)
    : (dishItem?.carbs ?? 0);
  const totalFat = hasComponents
    ? components.reduce((s, c) => s + (c.fat ?? 0), 0)
    : (dishItem?.fat ?? 0);

  return (
    <CardShell className="flex min-h-0 flex-1 flex-col overflow-hidden p-5">
      {/* Dish summary card */}
      <div className="mb-4 flex items-start justify-between gap-4 rounded-2xl border border-green-200 bg-green-50/50 p-5">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-green-100 px-2.5 py-1 text-[11px] font-black text-green-700">识别为</span>
            <span className="text-[22px] font-black tracking-[-0.04em] text-slate-900">{dishItem?.userCorrection || dishItem?.name || "未知"}</span>
            {dishItem?.userCorrection && (
              <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-bold text-violet-600">用户校正</span>
            )}
          </div>
          {dishItem?.dishFamily && (
            <div className="mt-2 text-[12px] font-bold text-slate-500">菜系家族：{dishItem.dishFamily}</div>
          )}
          {(() => {
            const primary = dishItem?.userCorrection || dishItem?.name || "";
            const family = dishItem?.dishFamily ?? "";
            const aiNames = (dishItem?.alternatives ?? []).map((a: { name: string }) => a.name);
            const familyFallback: Record<string, string[]> = {
              "川式红汤混合菜": ["冒菜", "麻辣烫", "麻辣香锅", "火锅", "串串香"],
              "干锅炒制类": ["麻辣香锅", "干锅菜", "香辣炒菜"],
              "米饭盖浇类": ["盖饭", "烩饭", "拌饭", "咖喱饭", "卤肉饭"],
              "炒饭炒面类": ["炒饭", "蛋炒饭", "炒面", "炒粉"],
              "汤面粉类": ["牛肉面", "拉面", "米线", "酸辣粉", "螺蛳粉"],
            };
            const all = [primary, ...aiNames, ...(familyFallback[family] ?? [])];
            const deduped = [...new Set(all.filter(Boolean))];
            const others = deduped.filter(n => n !== primary);
            const highAmbiguity = new Set(["川式红汤混合菜", "干锅炒制类", "米饭盖浇类", "炒饭炒面类", "汤面粉类"]);
            const show = others.length > 0 && (highAmbiguity.has(family) || (dishItem?.confidence ?? 0) < 0.9);
            if (!show) return null;
            return (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-bold text-amber-600">相似候选：</span>
                {others.map((name) => (
                  <span key={name} className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold text-amber-600">{name}</span>
                ))}
              </div>
            );
          })()}
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            <div className="min-w-0 rounded-xl bg-white/85 px-3 py-2 shadow-[0_4px_14px_rgba(15,23,42,0.035)]">
              <div className="truncate text-[14px] font-black text-slate-700">{Math.round(totalWeight)}g</div>
              <div className="mt-0.5 text-[10px] font-black text-slate-400">重量</div>
            </div>
            <div className="min-w-0 rounded-xl bg-white/85 px-3 py-2 shadow-[0_4px_14px_rgba(15,23,42,0.035)]">
              <div className="truncate text-[14px] font-black text-orange-500">{Math.round(totalCal)} kcal</div>
              <div className="mt-0.5 text-[10px] font-black text-slate-400">热量</div>
            </div>
            <div className="min-w-0 rounded-xl bg-white/85 px-3 py-2 shadow-[0_4px_14px_rgba(15,23,42,0.035)]">
              <div className="truncate text-[14px] font-black text-green-600">{Math.round(totalProtein)}g</div>
              <div className="mt-0.5 text-[10px] font-black text-slate-400">蛋白质</div>
            </div>
            <div className="min-w-0 rounded-xl bg-white/85 px-3 py-2 shadow-[0_4px_14px_rgba(15,23,42,0.035)]">
              <div className="truncate text-[14px] font-black text-orange-500">{Math.round(totalCarbs)}g</div>
              <div className="mt-0.5 text-[10px] font-black text-slate-400">碳水</div>
            </div>
            <div className="min-w-0 rounded-xl bg-white/85 px-3 py-2 shadow-[0_4px_14px_rgba(15,23,42,0.035)]">
              <div className="truncate text-[14px] font-black text-violet-600">{Math.round(totalFat)}g</div>
              <div className="mt-0.5 text-[10px] font-black text-slate-400">脂肪</div>
            </div>
          </div>
        </div>
        {!readOnly && (
          <Link href={`/confirm/${recordId}`} className="flex h-9 shrink-0 items-center gap-2 rounded-xl border border-green-200 bg-white px-4 text-[13px] font-black text-green-700 transition hover:bg-green-100">
            <PencilLine className="h-4 w-4" />编辑
          </Link>
        )}
      </div>

      {/* Components table */}
      {!hasComponents && (
        <div className="mb-4 flex items-center gap-3 rounded-xl bg-amber-50 px-4 py-3 text-[13px] font-bold text-amber-700">
          <AlertCircle className="h-5 w-5 shrink-0" />
          未获取到成分明细，当前显示为 AI 估算值。请进入编辑页补充成分以精确计算营养。
        </div>
      )}
      <div className="mb-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <ClipboardList className="h-5 w-5 text-green-600" />
          <h2 className="text-[17px] font-black tracking-[-0.04em] text-slate-950">成分明细</h2>
          <span className="text-[11px] font-bold text-slate-400">这些成分共同构成本餐，汇总后计入总热量</span>
        </div>
        <span className="rounded-full bg-green-50 px-3 py-1 text-[12px] font-black text-green-700">{components.length} 项成分</span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-100">
        <div className="grid h-10 shrink-0 grid-cols-[minmax(110px,1.2fr)_80px_80px_56px_72px] items-center bg-slate-50 px-3 text-[13px] font-black text-slate-500">
          <div>成分</div><div>重量</div><div>热量</div><div>置信度</div><div>来源</div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {components.map((c, ci) => {
            const hasWeight = c.estimatedWeightG != null && c.estimatedWeightG > 0;
            const hasCal = c.calories != null && c.calories > 0;
            const sourceLabel = c.confidence && c.confidence >= 0.5 ? "AI识别" : "估算";
            return (
              <div key={ci} className="grid min-h-[40px] grid-cols-[minmax(110px,1.2fr)_80px_80px_56px_72px] items-center border-t border-slate-100 px-3 text-[13px]">
                <div className="truncate font-black text-slate-800">{c.name}</div>
                <div className="font-bold text-slate-500 tabular-nums">{hasWeight ? `${Math.round(c.estimatedWeightG ?? 0)}g` : "-"}</div>
                <div className="font-bold text-orange-500 tabular-nums">{hasCal ? `${Math.round(c.calories ?? 0)}kcal` : "-"}</div>
                <div>
                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">{Math.round((c.confidence ?? 0) * 100)}%</span>
                </div>
                <div>
                  <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-400">{sourceLabel}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Totals summary */}
      <div className="mt-3 flex items-center gap-4 rounded-xl bg-slate-50 px-4 py-3 text-[13px]">
        <span className="font-black text-slate-700">成分合计</span>
        <span className="font-bold text-slate-600">{Math.round(totalWeight)}g</span>
        <span className="font-bold text-orange-500">{Math.round(totalCal)} kcal</span>
        <span className="ml-auto text-[11px] font-bold text-green-600">已计入本餐总量</span>
      </div>
    </CardShell>
  );
}

function FoodItemsCard({ items, onItemsChange, readOnly = false, recordId }: { items: FoodItem[]; onItemsChange: (items: FoodItem[]) => void; readOnly?: boolean; recordId?: string }) {
  const [adding, setAdding] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [newItem, setNewItem] = useState<Partial<FoodItem>>({})
  const [editDraft, setEditDraft] = useState<Partial<FoodItem>>({})

  const startAdd = () => { setAdding(true); setNewItem({ name: "", weight: "", calories: 0, protein: 0, carbs: 0, fat: 0, category: "unknown", source: "manual", estimated: false, confidence: 1 }) }
  const cancelAdd = () => { setAdding(false); setNewItem({}) }
  const confirmAdd = () => {
    if (!newItem.name?.trim()) return
    const id = "new-" + Date.now()
    onItemsChange([...items, { id, name: newItem.name || "", weight: newItem.weight || "", calories: Number(newItem.calories) || 0, protein: Number(newItem.protein) || 0, carbs: Number(newItem.carbs) || 0, fat: Number(newItem.fat) || 0, category: newItem.category || "unknown", source: "manual", estimated: false, confidence: 1, imageUrl: "", components: null }])
    setAdding(false); setNewItem({})
  }

  const startEdit = (index: number) => {
    setEditingIndex(index)
    setEditDraft({ ...items[index] })
  }
  const cancelEdit = () => { setEditingIndex(null); setEditDraft({}) }
  const confirmEdit = (index: number) => {
    const updated = items.map((it, i) => i === index ? {
      ...it,
      name: editDraft.name || it.name,
      weight: editDraft.weight || it.weight,
      calories: Number(editDraft.calories) ?? it.calories,
      protein: Number(editDraft.protein) ?? it.protein,
      carbs: Number(editDraft.carbs) ?? it.carbs,
      fat: Number(editDraft.fat) ?? it.fat,
      source: "manual",
      estimated: false,
      confidence: 1,
      components: it.components ?? null,
    } : it)
    onItemsChange(updated)
    setEditingIndex(null); setEditDraft({})
  }

  return (
    <CardShell className="flex min-h-0 flex-1 flex-col overflow-hidden p-5">
      <div className="mb-3 flex shrink-0 items-center justify-between gap-4">
        <CardTitle title="识别食物明细" icon={<ClipboardList className="h-5 w-5 text-green-600" />} />
        {/* 分析结果页只展示结果；修改入口使用每行铅笔图标进入 /confirm/{id}。 */}
        {false && !readOnly && (
        <button onClick={startAdd} className="flex h-9 items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-3 text-[14px] font-black text-green-700 transition hover:bg-green-100">
          <Plus className="h-4 w-4" />添加
        </button>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-100">
        <div className="grid h-10 shrink-0 grid-cols-[minmax(160px,1.4fr)_0.65fr_0.75fr_0.75fr_0.75fr_0.75fr_70px] items-center bg-slate-50 px-3 text-[13px] font-black text-slate-500">
          <div>食物</div><div>重量</div><div>热量</div><div>蛋白质</div><div>碳水</div><div>脂肪</div><div className="text-right">操作</div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {items.map((item, index) => (
            <div key={item.id} className={`grid min-h-[58px] grid-cols-[minmax(160px,1.4fr)_0.65fr_0.75fr_0.75fr_0.75fr_0.75fr_70px] items-center border-t border-slate-100 px-3 text-[14px] ${editingIndex === index ? 'bg-amber-50/30' : ''}`}>
              {editingIndex === index ? (
                <>
                  <InlineInput value={editDraft.name || ""} onChange={(v) => setEditDraft({ ...editDraft, name: v })} />
                  <InlineInput value={editDraft.weight || ""} onChange={(v) => setEditDraft({ ...editDraft, weight: v })} />
                  <InlineInput type="number" value={String(editDraft.calories || "")} onChange={(v) => setEditDraft({ ...editDraft, calories: Number(v) })} />
                  <InlineInput type="number" value={String(editDraft.protein || "")} onChange={(v) => setEditDraft({ ...editDraft, protein: Number(v) })} />
                  <InlineInput type="number" value={String(editDraft.carbs || "")} onChange={(v) => setEditDraft({ ...editDraft, carbs: Number(v) })} />
                  <InlineInput type="number" value={String(editDraft.fat || "")} onChange={(v) => setEditDraft({ ...editDraft, fat: Number(v) })} />
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => confirmEdit(index)} className="rounded-lg bg-green-600 px-2 py-1 text-[12px] font-bold text-white">保存</button>
                    <button onClick={cancelEdit} className="rounded-lg bg-slate-200 px-2 py-1 text-[12px] font-bold text-slate-600">取消</button>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex min-w-0 items-center gap-3">
                    <FoodThumb imageUrl={item.imageUrl} />
                    <div className="min-w-0">
                      <div className="truncate font-black text-slate-800">{item.name}</div>
                      <div className="mt-0.5 text-[11px] font-bold text-slate-500">{formatFoodItemLabels(item)}</div>
                    </div>
                  </div>
                  <div className="font-bold text-slate-500">{item.weight}</div>
                  <div className="font-bold text-orange-500">{item.calories}kcal</div>
                  <div className="font-bold text-slate-500">{item.protein}g</div>
                  <div className="font-bold text-slate-500">{item.carbs}g</div>
                  <div className="font-bold text-slate-500">{item.fat}g</div>
                  <div className="text-right">
                    {!readOnly && (
                    <Link href={`/confirm/${recordId}`} className="inline-flex h-8 items-center justify-center rounded-lg px-2 text-green-700 transition hover:bg-green-50" onClick={() => console.log("[records edit target]", { recordId, target: `/confirm/${recordId}` })}>
                      <PencilLine className="h-4 w-4" />
                    </Link>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
          {adding && (
            <div className="grid min-h-[58px] grid-cols-[minmax(160px,1.4fr)_0.65fr_0.75fr_0.75fr_0.75fr_0.75fr_70px] items-center border-t border-slate-100 bg-green-50/20 px-3 text-[14px]">
              <InlineInput value={newItem.name || ""} onChange={(v) => setNewItem({ ...newItem, name: v })} placeholder="食物名" />
              <InlineInput value={newItem.weight || ""} onChange={(v) => setNewItem({ ...newItem, weight: v })} placeholder="份量" />
              <InlineInput type="number" value={String(newItem.calories || "")} onChange={(v) => setNewItem({ ...newItem, calories: Number(v) })} />
              <InlineInput type="number" value={String(newItem.protein || "")} onChange={(v) => setNewItem({ ...newItem, protein: Number(v) })} />
              <InlineInput type="number" value={String(newItem.carbs || "")} onChange={(v) => setNewItem({ ...newItem, carbs: Number(v) })} />
              <InlineInput type="number" value={String(newItem.fat || "")} onChange={(v) => setNewItem({ ...newItem, fat: Number(v) })} />
              <div className="flex items-center justify-end gap-1">
                <button onClick={confirmAdd} className="rounded-lg bg-green-600 px-2 py-1 text-[12px] font-bold text-white">确定</button>
                <button onClick={cancelAdd} className="rounded-lg bg-slate-200 px-2 py-1 text-[12px] font-bold text-slate-600">取消</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </CardShell>
  )
}

function InlineInput({ value, onChange, type = "text", placeholder = "" }: { value: string; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="h-8 w-full rounded border border-slate-200 bg-white px-2 text-[13px] font-semibold text-slate-800 outline-none focus:border-green-500"
    />
  )
}

function FoodThumb({ imageUrl }: { imageUrl?: string }) {
  const [failed, setFailed] = useState(false)

  if (imageUrl && !failed) {
    return (
      <img
        src={imageUrl}
        alt="食物缩略图"
        className="h-9 w-9 shrink-0 rounded-lg object-cover"
        onError={() => setFailed(true)}
      />
    )
  }

  return (
    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-orange-100 to-green-100 text-[18px]">
      🍽️
    </div>
  )
}

function MealImageCard({ imageUrl }: { imageUrl: string }) {
  const [failed, setFailed] = useState(false)
  const showImage = imageUrl && !failed

  return (
    <CardShell className="shrink-0 overflow-hidden p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <CardTitle
          title="餐食图片"
          icon={<ImageIcon className="h-5 w-5 text-green-600" />}
        />

        <span className="rounded-full bg-green-50 px-3 py-1 text-[12px] font-black text-green-700">
          已上传
        </span>
      </div>

      <div className="h-[218px] overflow-hidden rounded-xl 2xl:h-[240px]">
        {showImage ? (
          <img
            src={imageUrl}
            alt="上传的餐食图片"
            className="h-full w-full object-cover"
            onError={() => setFailed(true)}
          />
        ) : (
          <MealMockImage />
        )}
      </div>
    </CardShell>
  )
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
  )
}

function AiSummaryCard({ summary }: { summary: string[] }) {
  return (
    <CardShell className="flex min-h-0 flex-1 flex-col p-4">
      <div className="mb-3 flex shrink-0 items-center gap-2.5">
        <Sparkles className="h-5 w-5 text-violet-600" />
        <CardTitle title="AI 营养总结" icon={null} />
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {summary.map((text, index) => (
          <div key={`${text}-${index}`} className="flex gap-2.5">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
            <p className="text-[14px] font-semibold leading-6 text-slate-600">
              {text}
            </p>
          </div>
        ))}
      </div>
    </CardShell>
  )
}

function TechDetailsCard({
  technical,
}: {
  technical: AnalyzeResult['technical']
}) {
  return (
    <CardShell className="shrink-0 p-4">
      <div className="mb-3 flex items-center gap-2.5">
        <Code2 className="h-5 w-5 text-slate-700" />
        <CardTitle title="技术详情" icon={null} />
      </div>

      <div className="space-y-2.5 text-[13px]">
        <DetailRow label="OCR 文本" value={technical.ocrText} />
        <DetailRow label="Prompt" value={technical.promptVersion} />
        <DetailRow label="AI 延迟" value={technical.aiLatency} />
        <DetailRow
          label="缓存命中"
          value={technical.cacheHit ? '命中' : '未命中'}
        />
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-xl bg-green-50 px-3 py-2 text-[12px] font-bold text-green-700">
        <ShieldCheck className="h-4 w-4" />
        AI 分析结果仅供参考，可手动修正食物重量。
      </div>
    </CardShell>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[78px_minmax(0,1fr)] items-start gap-3">
      <span className="font-black text-slate-400">{label}</span>
      <span className="truncate text-right font-bold text-slate-600">
        {value}
      </span>
    </div>
  )
}

function ActionBar({
  onSave, onReAnalyze, onExport,
  confirmed = false,
  saving = false, saveMsg = "",
}: {
  onSave: () => void; onReAnalyze: () => void; onExport: () => void
  confirmed?: boolean; saving?: boolean; saveMsg?: string
}) {
  return (
    <div className="grid shrink-0 gap-3 md:grid-cols-3">
      <button type="button" onClick={onSave} disabled={saving || confirmed}
        className={`flex h-[52px] items-center justify-center gap-3 rounded-xl text-[17px] font-black text-white shadow-[0_12px_28px_rgba(34,197,94,0.24)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(34,197,94,0.3)] disabled:opacity-60 disabled:hover:translate-y-0 ${confirmed ? 'bg-gradient-to-b from-slate-400 to-slate-500' : 'bg-gradient-to-b from-green-500 to-green-700'}`}
      >
        {saving ? <Loader2 className="h-5 w-5 animate-spin" /> : confirmed ? <BadgeCheck className="h-5 w-5" /> : <Save className="h-5 w-5" />}
        {saving ? '保存中...' : confirmed ? '已保存' : '保存记录'}
      </button>
      <button type="button" onClick={onReAnalyze}
        className="flex h-[52px] items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white text-[16px] font-black text-slate-600 shadow-[0_12px_30px_rgba(15,23,42,0.045)] transition hover:bg-slate-50"
      >
        <RotateCcw className="h-5 w-5" />
        重新分析
      </button>

      <button
        type="button"
        onClick={onExport}
        className="flex h-[52px] items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white text-[16px] font-black text-slate-600 shadow-[0_12px_30px_rgba(15,23,42,0.045)] transition hover:bg-slate-50"
      >
        <Download className="h-5 w-5" />
        导出结果
      </button>

      {saveMsg && <div className="col-span-full text-center text-[13px] font-bold text-green-600">{saveMsg}</div>}
    </div>
  )
}