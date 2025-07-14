'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  BadgeCheck,
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  ClipboardList,
  CloudUpload,
  Coffee,
  Droplet,
  FileText,
  Home,
  Info,
  Leaf,
  Loader2,
  Moon,
  Settings,
  Sparkles,
  Sun,
  Target,
  UploadCloud,
  Wheat,
} from 'lucide-react'
import { apiGet, ApiError } from '@/services/api'
import { useGreeting } from '@/lib/useGreeting'
import AccountMenu from '@/components/user/AccountMenu'
import ProfileEntry from '@/components/user/ProfileEntry'

type MacroKey = 'protein' | 'carbs' | 'fat'
type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'

type UserProfile = {
  nickname: string
  phone: string
  avatarText: string
}

type TodaySummary = {
  consumedCalories: number
  targetCalories: number
  remainingCalories: number
  statusText: string
}

type MacroProgress = {
  key: MacroKey
  label: string
  current: number
  target: number
  unit: string
  percent: number
}

type WeeklyPoint = {
  day: string
  calories: number
}

type ActiveTask = {
  id: string
  filename: string
  status: string
  statusText: string
  estimateText: string
  currentStep: number
}

type RecentMeal = {
  id: string
  mealType: MealType
  title: string
  time: string
  calories: number
  summary: string
  protein: number
  carbs: number
  fat: number
  imageUrl?: string | null
}

type DashboardData = {
  user: UserProfile
  today: TodaySummary
  macros: MacroProgress[]
  weekly: WeeklyPoint[]
  activeTask: ActiveTask | null
  recentMeals: RecentMeal[]
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

const mealTitleMap: Record<MealType, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '加餐',
}

const mealIconMap: Record<MealType, React.ReactNode> = {
  breakfast: <Coffee className="h-4 w-4" />,
  lunch: <Sun className="h-4 w-4" />,
  dinner: <Moon className="h-4 w-4" />,
  snack: <Sparkles className="h-4 w-4" />,
}

const macroToneMap: Record<
  MacroKey,
  {
    icon: React.ReactNode
    iconClassName: string
    barClassName: string
  }
> = {
  protein: {
    icon: <Target className="h-5 w-5" />,
    iconClassName: 'bg-green-50 text-green-600',
    barClassName: 'bg-green-500',
  },
  carbs: {
    icon: <Wheat className="h-5 w-5" />,
    iconClassName: 'bg-orange-50 text-orange-500',
    barClassName: 'bg-orange-400',
  },
  fat: {
    icon: <Droplet className="h-5 w-5" />,
    iconClassName: 'bg-violet-50 text-violet-600',
    barClassName: 'bg-violet-600',
  },
}

function resolveImageUrl(value?: string | null): string {
  if (!value) return ''
  if (value.startsWith('http')) return value
  if (value.startsWith('/') && API_BASE) return `${API_BASE}${value}`
  return value
}

export default function DashboardPage() {
  const router = useRouter()

  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    const load = async () => {
      try {
        const result = await apiGet<DashboardData>('/api/dashboard/summary')
        if (!ignore) {
          const u = result.user || ({} as any)
          const adapted: DashboardData = {
            ...result,
            user: {
              nickname: u.nickname || '',
              phone: u.phone || '',
              avatarText: u.avatarText || '',
            },
            recentMeals: (result.recentMeals || []).map((m: any) => ({
              ...m,
              imageUrl: m.imageUrl ?? m.image_url ?? null,
            })),
          }
          setData(adapted)
        }
      } catch (err) {
        console.error('[Dashboard] load failed:', err)
        if (!ignore) {
          if (err instanceof ApiError) {
            if (err.status === 401) {
              localStorage.removeItem('token')
              localStorage.removeItem('user')
              router.push('/login')
              return
            }
            setError(err.message)
          } else if (err instanceof TypeError && err.message.includes('fetch')) {
            setError('后端服务不可用，请确认已启动 uvicorn')
          } else {
            setError(`加载失败: ${err instanceof Error ? err.message : '未知错误'}`)
          }
        }
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    load()

    return () => {
      ignore = true
    }
  }, [router])

  return (
    <main className="min-h-screen bg-[#f8faf8] text-slate-950 lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={data?.user} />

        <section className="min-w-0 bg-white lg:h-screen lg:overflow-hidden">
          <div className="mx-auto flex min-h-screen w-full max-w-[1480px] flex-col px-5 py-4 sm:px-6 lg:h-screen lg:min-h-0 lg:px-7">
            <TopHeader
              user={data?.user}
              today={data?.today}
              loading={loading}
            />

            {loading ? (
              <div className="flex flex-1 items-center justify-center">
                <Loader2 className="h-10 w-10 animate-spin text-green-600" />
              </div>
            ) : error ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="text-center">
                  <Circle className="mx-auto h-10 w-10 text-slate-300" />
                  <p className="mt-3 text-[15px] font-bold text-slate-500">{error}</p>
                </div>
              </div>
            ) : data ? (
              <div className="mt-4 grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                <div className="min-w-0 space-y-4 lg:overflow-hidden">
                  <div className="grid gap-4 lg:grid-cols-[330px_minmax(0,1fr)]">
                    <CalorieCard today={data.today} />
                    <MacroCard macros={data.macros} />
                  </div>

                  <WeeklyTrendCard weekly={data.weekly} />

                  <RecentMealsSection meals={data.recentMeals} onMealClick={(id) => router.push(`/records/${id}`)} />
                </div>

                <div className="space-y-4 lg:overflow-hidden">
                  <QuickUploadCard onUpload={() => router.push('/upload')} />
                  <ActiveTaskCard task={data.activeTask} onClick={data.activeTask ? () => router.push(`/analyze/${data.activeTask!.id}`) : undefined} />
                </div>
              </div>
            ) : null}
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

function Sidebar({ user }: { user?: UserProfile | null }) {
  return (
    <aside className="hidden h-screen overflow-hidden border-r border-slate-200 bg-white px-4 py-5 lg:flex lg:flex-col">
      <AppLogo />

      <nav className="mt-7 space-y-2">
        <SidebarItem
          href="/dashboard"
          active
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
  today,
  loading,
}: {
  user?: UserProfile | null
  today?: TodaySummary | null
  loading: boolean
}) {
  return (
    <header className="flex shrink-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="flex items-center gap-3 text-[28px] font-black leading-tight tracking-[-0.06em] text-slate-950 sm:text-[34px]">
          {useGreeting()}，{user?.nickname || '...'}
          <span className="text-3xl">☀️</span>
        </h1>

        <p className="mt-1.5 text-[15px] font-semibold text-slate-500">
          这是你今天的营养概览。
        </p>
      </div>

      <div className="flex items-center gap-4 lg:pt-0.5">
        <div className="text-right">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            {today?.statusText || '加载中'}
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            你今天还差{' '}
            <span className="font-black text-slate-700">
              {today ? Math.max(today.targetCalories - today.consumedCalories, 0) : 0}
            </span>{' '}
            kcal 达标
          </div>
        </div>

        <ProfileEntry user={user || undefined} statusText="加载中" detailText="点击进入个人中心" />
      </div>
    </header>
  )
}

function CardShell({
  children,
  className = '',
  onClick,
}: {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
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
      {icon === undefined ? (
        <Info className="h-4 w-4 text-slate-400" />
      ) : (
        icon
      )}
    </div>
  )
}

function CalorieCard({ today }: { today: TodaySummary }) {
  const percent = Math.min(
    Math.round((today.consumedCalories / today.targetCalories) * 100),
    100,
  )

  const degrees = Math.round((percent / 100) * 360)

  return (
    <CardShell className="flex h-[260px] flex-col p-5">
      <CardTitle title="今日热量" />

      <div className="flex flex-1 items-center justify-center py-2">
        <div
          className="relative grid h-[136px] w-[136px] place-items-center rounded-full"
          style={{
            background: `conic-gradient(#35ad5f 0deg ${degrees}deg, #eef0f2 ${degrees}deg 360deg)`,
          }}
        >
          <div className="absolute h-[104px] w-[104px] rounded-full bg-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.02)]" />

          <div className="relative text-center">
            <div className="text-[26px] font-black tracking-[-0.06em] text-slate-950">
              {today.consumedCalories.toLocaleString()}
            </div>
            <div className="mt-0.5 text-[12px] font-black text-slate-500">
              已摄入 kcal
            </div>
          </div>
        </div>
      </div>

      <div className="mt-auto grid grid-cols-2 border-t border-slate-100 pt-3">
        <div>
          <div className="text-[22px] font-black leading-none tracking-[-0.05em] text-orange-500">
            {today.remainingCalories.toLocaleString()}
          </div>
          <div className="mt-1 text-[12px] font-black text-slate-500">
            剩余 kcal
          </div>
        </div>

        <div className="text-right">
          <div className="text-[22px] font-black leading-none tracking-[-0.05em] text-slate-700">
            {today.targetCalories.toLocaleString()}
          </div>
          <div className="mt-1 text-[12px] font-black text-slate-500">
            目标 kcal
          </div>
        </div>
      </div>
    </CardShell>
  )
}

function MacroCard({ macros }: { macros: MacroProgress[] }) {
  return (
    <CardShell className="flex h-[260px] flex-col overflow-hidden">
      <div className="flex-1 p-5">
        <CardTitle title="宏量营养素" />

        <div className="mt-5 space-y-5">
          {macros.map((item) => (
            <MacroProgressRow key={item.key} item={item} />
          ))}
        </div>
      </div>

      <Link
        href="/records"
        className="flex h-[42px] shrink-0 items-center justify-center gap-3 border-t border-slate-200 text-[15px] font-black text-green-700 transition hover:bg-green-50"
      >
        查看营养详情
        <ChevronRight className="h-4 w-4" />
      </Link>
    </CardShell>
  )
}

function MacroProgressRow({ item }: { item: MacroProgress }) {
  const tone = macroToneMap[item.key]

  return (
    <div className="grid grid-cols-[44px_minmax(0,1fr)] items-center gap-3">
      <div
        className={`grid h-10 w-10 place-items-center rounded-full ${tone.iconClassName}`}
      >
        {tone.icon}
      </div>

      <div className="min-w-0">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="text-[15px] font-black text-slate-800">
            {item.label}
          </div>

          <div className="whitespace-nowrap text-[14px] font-bold text-slate-500">
            <span className="font-black text-slate-700">
              {item.current}
              {item.unit}
            </span>{' '}
            / {item.target}
            {item.unit}
            <span className="ml-3 font-black text-slate-600">
              {item.percent}%
            </span>
          </div>
        </div>

        <div className="h-2.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full rounded-full ${tone.barClassName}`}
            style={{ width: `${Math.min(item.percent, 100)}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function QuickUploadCard({ onUpload }: { onUpload: () => void }) {
  return (
    <CardShell className="cursor-pointer p-5 transition hover:shadow-[0_18px_42px_rgba(15,23,42,0.1)]" onClick={onUpload}>
      <div className="flex items-center gap-3">
        <Sparkles className="h-6 w-6 text-violet-600" />
        <CardTitle title="快捷操作" icon={null} />
      </div>

      <p className="mt-3 text-[14px] font-semibold leading-6 text-slate-500">
        上传一张食物图片，其余交给 AI。
      </p>

      <button
        type="button"
        onClick={onUpload}
        className="mt-4 flex h-[50px] w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-[17px] font-black text-white shadow-[0_12px_28px_rgba(34,197,94,0.24)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(34,197,94,0.3)]"
      >
        <UploadCloud className="h-6 w-6" />
        上传食物图片
      </button>

      <div className="mt-3 text-center text-[13px] font-bold text-slate-500">
        支持 JPG、PNG，最大 10MB
      </div>
    </CardShell>
  )
}

function ActiveTaskCard({ task, onClick }: { task: ActiveTask | null; onClick?: () => void }) {
  const steps = [
    {
      label: 'OCR',
      desc: '处理中',
      icon: <FileText className="h-4 w-4" />,
    },
    {
      label: '食物识别',
      desc: '',
      icon: <Target className="h-4 w-4" />,
    },
    {
      label: '营养分析',
      desc: '',
      icon: <Brain className="h-4 w-4" />,
    },
    {
      label: '完成',
      desc: '',
      icon: <BadgeCheck className="h-4 w-4" />,
    },
  ]

  return (
    <CardShell className={`flex h-[304px] flex-col p-5 ${task && onClick ? 'cursor-pointer hover:shadow-[0_16px_36px_rgba(15,23,42,0.09)]' : ''}`}>
      <div className="mb-4 flex shrink-0 items-start justify-between gap-4">
        <CardTitle title="进行中的分析" icon={null} />

        <span className="shrink-0 rounded-full bg-violet-100 px-3 py-1.5 text-[13px] font-black text-violet-600">
          处理中
        </span>
      </div>

      {task ? (
        <div className="flex min-h-0 flex-1 flex-col" onClick={onClick}>
          <div className="truncate text-[14px] font-black text-slate-700">
            {task.filename}
          </div>

          <div className="mt-1.5 line-clamp-1 text-[14px] font-semibold text-slate-500">
            {task.statusText}
          </div>

          <div className="mt-6 grid shrink-0 grid-cols-[1fr_1fr_1fr_1fr] items-start">
            {steps.map((step, index) => {
              const active = index <= task.currentStep
              const current = index === task.currentStep

              return (
                <div key={step.label} className="relative text-center">
                  {index < steps.length - 1 ? (
                    <div
                      className={`absolute left-1/2 top-[22px] h-1 w-full ${
                        active ? 'bg-violet-500' : 'bg-slate-200'
                      }`}
                    />
                  ) : null}

                  <div className="relative z-10 mx-auto grid h-11 w-11 place-items-center rounded-full border bg-white">
                    <div
                      className={`grid h-9 w-9 place-items-center rounded-full ${
                        current
                          ? 'bg-violet-600 text-white shadow-lg shadow-violet-500/25'
                          : active
                            ? 'bg-violet-50 text-violet-600'
                            : 'bg-slate-50 text-slate-400'
                      }`}
                    >
                      {step.icon}
                    </div>
                  </div>

                  <div
                    className={`mt-2 text-[12px] font-black ${
                      active ? 'text-slate-800' : 'text-slate-400'
                    }`}
                  >
                    {step.label}
                  </div>

                  {step.desc ? (
                    <div className="mt-0.5 text-[12px] font-semibold text-slate-500">
                      {step.desc}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>

          <div className="mt-auto border-t border-slate-100 pt-4 text-[14px] font-semibold text-slate-500">
            {task.estimateText}
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center text-center">
          <Circle className="h-8 w-8 text-slate-300" />
          <div className="mt-3 text-[15px] font-black text-slate-700">
            暂无进行中的任务
          </div>
          <div className="mt-1.5 text-[13px] font-semibold text-slate-500">
            上传食物图片后，AI Workflow 状态会显示在这里。
          </div>
        </div>
      )}
    </CardShell>
  )
}

function WeeklyTrendCard({ weekly }: { weekly: WeeklyPoint[] }) {
  const max = Math.max(...weekly.map((item) => item.calories), 2400)
  const points = weekly.map((item, index) => {
    const x = 60 + index * 126
    const y = 170 - (item.calories / max) * 120

    return { ...item, x, y }
  })

  const path = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')

  return (
    <CardShell className="p-5">
      <div className="mb-2 flex items-center justify-between">
        <CardTitle title="每周热量趋势" />

        <button className="flex h-9 items-center gap-2 rounded-xl border border-slate-200 px-4 text-[14px] font-black text-slate-500 transition hover:bg-slate-50">
          本周
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>

      <div className="relative overflow-hidden rounded-xl">
        <svg viewBox="0 0 900 250" className="h-[142px] w-full">
          <defs>
            <linearGradient id="weeklyArea" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#22c55e" stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {[0, 60, 120, 180].map((y, index) => (
            <line
              key={y}
              x1="58"
              x2="860"
              y1={30 + y}
              y2={30 + y}
              stroke={index === 1 ? '#94a3b8' : '#e5e7eb'}
              strokeDasharray={index === 1 ? '5 7' : '0'}
              strokeWidth="1.5"
            />
          ))}

          <text x="16" y="38" className="fill-slate-500 text-[15px] font-bold">
            2,400
          </text>
          <text x="16" y="98" className="fill-slate-500 text-[15px] font-bold">
            1,800
          </text>
          <text x="16" y="158" className="fill-slate-500 text-[15px] font-bold">
            1,200
          </text>
          <text x="26" y="218" className="fill-slate-500 text-[15px] font-bold">
            0
          </text>

          <path
            d={`${path} L ${points[points.length - 1]?.x ?? 816} 210 L ${
              points[0]?.x ?? 60
            } 210 Z`}
            fill="url(#weeklyArea)"
          />

          <path
            d={path}
            fill="none"
            stroke="#2faf5b"
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {points.map((point) => (
            <circle
              key={point.day}
              cx={point.x}
              cy={point.y}
              r="6"
              fill="#fff"
              stroke="#2faf5b"
              strokeWidth="4"
            />
          ))}

          {points.map((point) => (
            <text
              key={`${point.day}-label`}
              x={point.x}
              y="236"
              textAnchor="middle"
              className="fill-slate-500 text-[15px] font-bold"
            >
              {point.day}
            </text>
          ))}

          <text
            x="850"
            y="80"
            textAnchor="middle"
            className="fill-slate-500 text-[15px] font-black"
          >
            目标
          </text>
          <text
            x="850"
            y="105"
            textAnchor="middle"
            className="fill-slate-700 text-[18px] font-black"
          >
            2,000
          </text>
        </svg>
      </div>
    </CardShell>
  )
}

function RecentMealsSection({ meals, onMealClick }: { meals: RecentMeal[]; onMealClick?: (id: string) => void }) {
  return (
    <section className="min-h-0">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <Sparkles className="h-6 w-6 text-green-600" />
          <h2 className="text-[20px] font-black tracking-[-0.04em] text-slate-950">
            最近饮食记录
          </h2>
        </div>

        <Link
          href="/records"
          className="flex items-center gap-2 text-[15px] font-black text-green-700 transition hover:text-green-600"
        >
          查看全部记录
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {meals.map((meal) => (
          <MealCard key={meal.id} meal={meal} onClick={onMealClick ? () => onMealClick(meal.id) : undefined} />
        ))}
      </div>
    </section>
  )
}

function MealCard({ meal, onClick }: { meal: RecentMeal; onClick?: () => void }) {
  return (
    <CardShell className={`overflow-hidden p-3 ${onClick ? 'cursor-pointer hover:shadow-[0_16px_36px_rgba(15,23,42,0.09)]' : ''}`}>
      <div onClick={onClick} className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-green-600">{mealIconMap[meal.mealType]}</span>
          <span className="text-[16px] font-black text-slate-900">
            {meal.title}
          </span>
        </div>

        <span className="text-[13px] font-black text-slate-500">
          {meal.time}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-[112px_minmax(0,1fr)] xl:grid-cols-[112px_minmax(0,1fr)]">
        <MealImage meal={meal} />

        <div className="min-w-0">
          <div className="mb-2 text-[22px] font-black tracking-[-0.05em] text-orange-500">
            {meal.calories}{' '}
            <span className="text-[13px] tracking-normal">kcal</span>
          </div>

          <div className="mb-2 inline-flex items-center gap-1.5 rounded-lg bg-violet-100 px-2.5 py-1 text-[12px] font-black text-violet-600">
            <Sparkles className="h-3.5 w-3.5" />
            AI 总结
          </div>

          <p className="line-clamp-2 text-[13px] font-semibold leading-5 text-slate-500">
            {meal.summary}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-3 text-[13px] font-black text-slate-500">
            <span>
              <span className="text-green-600">P</span> {meal.protein}g
            </span>
            <span>
              <span className="text-orange-500">C</span> {meal.carbs}g
            </span>
            <span>
              <span className="text-violet-600">F</span> {meal.fat}g
            </span>
          </div>
        </div>
      </div>
    </CardShell>
  )
}

function MealImage({ meal }: { meal: RecentMeal }) {
  const src = resolveImageUrl(meal.imageUrl)
  if (src) {
    return (
      <img
        src={src}
        alt={meal.title}
        className="h-[112px] w-full rounded-xl object-cover"
      />
    )
  }

  return <MealMockImage type={meal.mealType} />
}

function MealMockImage({ type }: { type: MealType }) {
  const isBreakfast = type === 'breakfast'
  const isLunch = type === 'lunch'
  const isDinner = type === 'dinner'

  return (
    <div className="relative h-[112px] overflow-hidden rounded-xl bg-gradient-to-br from-amber-50 to-stone-100">
      <div className="absolute inset-x-3 bottom-[-22px] h-[82px] rounded-[50%] bg-white shadow-[inset_0_-14px_24px_rgba(120,113,108,0.12),0_18px_24px_rgba(15,23,42,0.12)]" />

      {isBreakfast ? (
        <>
          <div className="absolute left-6 top-9 h-7 w-7 rounded-full bg-blue-950 shadow-[26px_5px_0_#172554,50px_0_0_#111827]" />
          <div className="absolute left-[45px] top-6 h-9 w-9 rounded-full bg-yellow-100 shadow-[24px_5px_0_#fde68a,48px_-2px_0_#fef3c7]" />
          <div className="absolute bottom-6 left-7 h-5 w-5 rounded-full bg-amber-800 shadow-[22px_6px_0_#92400e,44px_-1px_0_#78350f,66px_5px_0_#a16207]" />
        </>
      ) : null}

      {isLunch ? (
        <>
          <div className="absolute left-5 top-6 h-[58px] w-[68px] rounded-[45%] bg-orange-100 shadow-[18px_6px_0_#fed7aa,42px_-2px_0_#ffedd5]" />
          <div className="absolute left-[78px] top-7 h-10 w-10 rounded-[50%] bg-green-600 shadow-[18px_-5px_0_#16a34a,34px_5px_0_#22c55e]" />
          <div className="absolute bottom-5 right-6 h-6 w-6 rounded-full bg-red-500 shadow-[-18px_5px_0_#ef4444]" />
        </>
      ) : null}

      {isDinner ? (
        <>
          <div className="absolute left-5 top-7 h-[45px] w-[82px] rotate-[-12deg] rounded-[45%] bg-orange-400 shadow-[0_0_0_3px_#fdba74]" />
          <div className="absolute left-[88px] top-8 h-8 w-10 rounded-[45%] bg-yellow-300 shadow-[18px_5px_0_#facc15,38px_-3px_0_#fde047]" />
          <div className="absolute right-5 top-7 h-10 w-12 rounded-[45%] bg-green-500 shadow-[-15px_14px_0_#22c55e]" />
        </>
      ) : null}

      {!isBreakfast && !isLunch && !isDinner ? (
        <>
          <div className="absolute left-7 top-8 h-10 w-10 rounded-full bg-lime-400 shadow-[30px_4px_0_#84cc16,60px_-4px_0_#65a30d]" />
          <div className="absolute right-8 top-10 h-8 w-8 rounded-full bg-red-400" />
        </>
      ) : null}
    </div>
  )
}