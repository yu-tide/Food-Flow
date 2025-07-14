'use client'

import React, { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  CloudUpload,
  Coffee,

  Flame,
  Home,
  Info,
  Leaf,
  Loader2,
  Moon,
  Plus,
  Settings,
  Sparkles,
  Sun,
  Target,
  UploadCloud,
  Utensils,
  Wheat,
} from 'lucide-react'
import { apiGet, ApiError } from '@/services/api'
import DatePopover from '@/components/ui/DatePopover'
import AccountMenu from '@/components/user/AccountMenu'
import ProfileEntry from '@/components/user/ProfileEntry'

type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'
type RangeType = 'today' | 'yesterday' | 'week' | 'custom'
type MealFilter = 'all' | MealType

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

type FoodRecord = {
  id: string
  mealType: MealType
  title: string
  time: string
  createdAt: string
  calories: number
  summary: string
  protein: number
  carbs: number
  fat: number
  foods: string[]
  imageUrl: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

function isToday(d: Date) { const t = new Date(); return d.getFullYear()===t.getFullYear() && d.getMonth()===t.getMonth() && d.getDate()===t.getDate() }
function isYesterday(d: Date) { const y = new Date(); y.setDate(y.getDate()-1); return d.getFullYear()===y.getFullYear() && d.getMonth()===y.getMonth() && d.getDate()===y.getDate() }
function getDateKey(d: Date|string) { const dt = new Date(d); return Number.isNaN(dt.getTime()) ? '' : `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}` }

function getUserProfile(): UserProfile {
  if (typeof window === 'undefined') return { nickname: '', phone: '', avatarText: '' }
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const u = JSON.parse(raw)
      return { nickname: u.nickname || '', phone: u.phone || '', avatarText: u.avatarText || u.nickname?.[0] || '' }
    }
  } catch { /* ignore */ }
  return { nickname: '', phone: '', avatarText: '' }
}

function isMealType(value?: string): value is MealType {
  return value === 'breakfast' || value === 'lunch' || value === 'dinner' || value === 'snack'
}

function adaptRecord(raw: any): FoodRecord {
  const mealType: MealType = isMealType(raw.meal_type) ? raw.meal_type : 'snack'
  const foodsRaw = raw.foods || ''
  const foodsArr = typeof foodsRaw === 'string'
    ? foodsRaw.split(/[,、]/).map((s: string) => s.trim()).filter(Boolean)
    : Array.isArray(foodsRaw) ? foodsRaw : []
  return {
    id: String(raw.id),
    mealType,
    title: raw.title || mealTitleMap[mealType] || '',
    time: raw.time || '',
    createdAt: raw.created_at || raw.createdAt || '',
    calories: Number(raw.total_calories || 0),
    summary: raw.summary || '',
    protein: Number(raw.protein || 0),
    carbs: Number(raw.carbohydrate || 0),
    fat: Number(raw.fat || 0),
    foods: foodsArr,
    imageUrl: raw.image_url ? (raw.image_url.startsWith('http') ? raw.image_url : raw.image_url.startsWith('/') ? `${API_BASE}${raw.image_url}` : raw.image_url) : '',
  }
}

type FoodListApi = { data: any[] }

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

const filterTabs: Array<{ label: string; value: MealFilter }> = [
  { label: '全部', value: 'all' },
  { label: '早餐', value: 'breakfast' },
  { label: '午餐', value: 'lunch' },
  { label: '晚餐', value: 'dinner' },
  { label: '加餐', value: 'snack' },
]

const rangeTabs: Array<{ label: string; value: RangeType }> = [
  { label: '今天', value: 'today' },
  { label: '昨天', value: 'yesterday' },
  { label: '本周', value: 'week' },
]

export default function RecordsPage() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [user] = useState<UserProfile>(getUserProfile)
  const [range, setRange] = useState<RangeType>('week')
  const [filter, setFilter] = useState<MealFilter>('all')
  const [selectedDate, setSelectedDate] = useState(() => new Date())
  const [datePickerOpen, setDatePickerOpen] = useState(false)
  const [uploadMealType, setUploadMealType] = useState<MealType>('snack')
  const [records, setRecords] = useState<FoodRecord[]>([])
  const [allRecords, setAllRecords] = useState<FoodRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')

  const handleRangeChange = (nextRange: RangeType) => {
    setRange(nextRange)
    if (nextRange === 'yesterday') { const y = new Date(); y.setDate(y.getDate() - 1); setSelectedDate(y) }
    else setSelectedDate(new Date())
  }

  useEffect(() => {
    let ignore = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await apiGet<FoodListApi>(`/api/foods?range=${range}`)
        if (!ignore) setRecords((res.data || []).map(adaptRecord))
      } catch (err) {
        if (!ignore && err instanceof ApiError && err.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); router.push('/login'); return }
      }
      // allRecords for streak (not affected by range)
      try { const allRes = await apiGet<FoodListApi>('/api/foods?limit=200'); if (!ignore) setAllRecords((allRes.data||[]).map(adaptRecord)) } catch {}
      if (!ignore) setLoading(false)
    }
    load()
    return () => { ignore = true }
  }, [range, router])

  const filteredRecords = useMemo(() => {
    if (filter === 'all') return records
    return records.filter((item) => item.mealType === filter)
  }, [records, filter])

  const streakDays = useMemo(() => {
    const days = new Set(allRecords.map(r => r.createdAt ? getDateKey(r.createdAt) : '').filter(Boolean))
    const today = getDateKey(new Date())
    let cursor = new Date(); if (!days.has(today)) cursor.setDate(cursor.getDate() - 1)
    let s = 0; while (days.has(getDateKey(cursor))) { s++; cursor.setDate(cursor.getDate() - 1) }
    return s
  }, [allRecords])

  const consumedCalories = records.reduce((t, r) => t + r.calories, 0)
  const targetCalories = 2000
  const today: TodaySummary = {
    consumedCalories,
    targetCalories,
    remainingCalories: Math.max(targetCalories - consumedCalories, 0),
    statusText: consumedCalories === 0 ? '今天还没有记录饮食' : consumedCalories < 1600 ? '摄入偏少' : consumedCalories <= 2200 ? '摄入较均衡' : '今日摄入偏高',
  }
  const totalProtein = records.reduce((t, r) => t + r.protein, 0)
  const totalCarbs = records.reduce((t, r) => t + r.carbs, 0)
  const totalFat = records.reduce((t, r) => t + r.fat, 0)

  const uploadButtonText = uploading ? '上传中...' : '上传饮食图片'

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadStatus(`正在上传 ${file.name}...`)
    try {
      const formData = new FormData()
      formData.append('image', file)
      formData.append('meal_type', uploadMealType)
      const token = localStorage.getItem('token')
      const res = await fetch(`${API_BASE}/api/foods/upload`, {
        method: 'POST',
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error('上传失败')
      const data = await res.json()
      const taskId = data.task_id || data.taskId || data.id
      if (taskId) { setUploadStatus('上传成功，正在进入分析流程...'); router.push(`/analyze/${taskId}`); return }
      setUploadStatus('上传成功，但后端暂未返回 task_id。')
    } catch (err) {
      console.error(err)
      setUploadStatus('上传失败，请重试')
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  return (
    <main className="min-h-screen bg-[#f8faf8] text-slate-950 lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={user} />

        <section className="min-w-0 bg-white lg:h-screen lg:overflow-hidden">
          <div className="mx-auto flex min-h-screen w-full max-w-[1480px] flex-col px-5 py-4 sm:px-6 lg:h-screen lg:min-h-0 lg:px-7">
            <TopHeader user={user} today={today} loading={loading} />

            <div className="mt-4 grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
              <div className="min-w-0 space-y-4 lg:overflow-y-auto lg:pr-1">
                <SummaryCards
                  today={today}
                  recordCount={records.length}
                  totalProtein={totalProtein}
                  streakDays={streakDays}
                />

                <FilterBar
                  range={range}
                  filter={filter}
                  onRangeChange={handleRangeChange}
                  onFilterChange={setFilter}
                  selectedDate={selectedDate}
                  onDateChange={setSelectedDate}
                  datePickerOpen={datePickerOpen}
                  setDatePickerOpen={setDatePickerOpen}
                />

                <MealRecordsList
                  records={filteredRecords}
                  loading={loading}
                  onRecordClick={(id) => router.push(`/records/${id}`)}
                />
              </div>

              <aside className="space-y-4 lg:overflow-y-auto lg:pr-1">
                <DailySummaryCard
                  today={today}
                  protein={totalProtein}
                  carbs={totalCarbs}
                  fat={totalFat}
                />

                <QuickUploadCard
                  fileInputRef={fileInputRef}
                  uploadMealType={uploadMealType}
                  onMealTypeChange={setUploadMealType}
                  onFileChange={handleFileChange}
                  uploadButtonText={uploadButtonText}
                  uploadStatus={uploadStatus}
                />
              </aside>
            </div>
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

      <div className="mt-auto">
        <AccountMenu user={user} />
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
  user: UserProfile
  today: TodaySummary
  loading: boolean
}) {
  return (
    <header className="flex shrink-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h1 className="flex items-center gap-3 text-[28px] font-black leading-tight tracking-[-0.06em] text-slate-950 sm:text-[34px]">
          饮食记录
          <span className="text-3xl">🥗</span>
        </h1>

        <p className="mt-1.5 text-[15px] font-semibold text-slate-500">
          按日期查看你的饮食分析记录与 AI 总结。
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
            {today.statusText}
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            你今天还差{' '}
            <span className="font-black text-slate-700">
              {Math.max(today.targetCalories - today.consumedCalories, 0)}
            </span>{' '}
            kcal 达标
          </div>
        </div>

        <ProfileEntry user={user} statusText={today.statusText} detailText="点击进入个人中心" loading={loading} />
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
      {icon === undefined ? (
        <Info className="h-4 w-4 text-slate-400" />
      ) : (
        icon
      )}
    </div>
  )
}

function SummaryCards({
  today,
  recordCount,
  totalProtein,
  streakDays,
}: {
  today: TodaySummary
  recordCount: number
  totalProtein: number
  streakDays: number
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        icon={<Leaf className="h-5 w-5" />}
        iconClassName="bg-green-50 text-green-600"
        label="今日摄入"
        value={today.consumedCalories.toLocaleString()}
        unit="kcal"
        helper={`剩余 ${today.remainingCalories} kcal`}
      />

      <MetricCard
        icon={<Utensils className="h-5 w-5" />}
        iconClassName="bg-blue-50 text-blue-600"
        label="已记录"
        value={String(recordCount)}
        unit="餐"
        helper="早餐 · 午餐 · 晚餐"
      />

      <MetricCard
        icon={<Wheat className="h-5 w-5" />}
        iconClassName="bg-orange-50 text-orange-500"
        label="蛋白质"
        value={String(totalProtein)}
        unit="g"
        helper="目标 120 g"
      />

      <MetricCard
        icon={<Flame className="h-5 w-5" />}
        iconClassName="bg-violet-50 text-violet-600"
        label="连续记录"
        value={String(streakDays)}
        unit="天"
        helper="保持良好习惯！"
      />
    </div>
  )
}

function MetricCard({
  icon,
  iconClassName,
  label,
  value,
  unit,
  helper,
}: {
  icon: React.ReactNode
  iconClassName: string
  label: string
  value: string
  unit: string
  helper: string
}) {
  return (
    <CardShell className="p-5">
      <div className="flex items-center gap-4">
        <div
          className={`grid h-12 w-12 shrink-0 place-items-center rounded-full ${iconClassName}`}
        >
          {icon}
        </div>

        <div className="min-w-0">
          <div className="text-[14px] font-black text-slate-500">{label}</div>

          <div className="mt-1 flex items-end gap-1">
            <span className="text-[26px] font-black leading-none tracking-[-0.06em] text-slate-950">
              {value}
            </span>
            <span className="pb-0.5 text-[13px] font-black text-slate-500">
              {unit}
            </span>
          </div>

          <div className="mt-1 truncate text-[12px] font-bold text-slate-500">
            {helper}
          </div>
        </div>
      </div>
    </CardShell>
  )
}

function FilterBar({
  range, filter, onRangeChange, onFilterChange,
  selectedDate, onDateChange,
  datePickerOpen, setDatePickerOpen,
}: {
  range: RangeType; filter: MealFilter
  onRangeChange: (v: RangeType) => void; onFilterChange: (v: MealFilter) => void
  selectedDate: Date; onDateChange: (d: Date) => void
  datePickerOpen: boolean; setDatePickerOpen: (v: boolean) => void
}) {
  return (
    <CardShell className="p-2">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex rounded-xl bg-slate-50 p-1">
          {rangeTabs.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => onRangeChange(item.value)}
              className={`h-10 rounded-lg px-5 text-[15px] font-black transition ${
                range === item.value
                  ? 'bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.08)]'
                  : 'text-slate-500 hover:bg-white hover:text-slate-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="relative">
          <button type="button"
            onClick={() => setDatePickerOpen(!datePickerOpen)}
            className="flex h-10 items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 text-[15px] font-black text-slate-600 transition hover:bg-slate-50 xl:min-w-[220px]"
          >
            <span className="flex items-center gap-2">
              <CalendarDays className="h-4 w-4 text-slate-400" />
              {range === 'week' ? '本周' : range === 'today' || isToday(selectedDate) ? '今天' : range === 'yesterday' || isYesterday(selectedDate) ? '昨天' : selectedDate.toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric'})}
            </span>
            <ChevronDown className="h-4 w-4 text-slate-400" />
          </button>
          {datePickerOpen && (<DatePopover selected={selectedDate} onSelect={(d) => { onDateChange(d); onRangeChange(isToday(d)?'today':isYesterday(d)?'yesterday':'custom'); }} onClose={() => setDatePickerOpen(false)} />)}
        </div>

        <div className="flex flex-wrap rounded-xl bg-slate-50 p-1">
          {filterTabs.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => onFilterChange(item.value)}
              className={`h-10 rounded-lg px-4 text-[15px] font-black transition ${
                filter === item.value
                  ? 'bg-green-50 text-green-700 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.08)]'
                  : 'text-slate-500 hover:bg-white hover:text-slate-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </CardShell>
  )
}

function MealRecordsList({
  records,
  loading,
  onRecordClick,
}: {
  records: FoodRecord[]
  loading: boolean
  onRecordClick?: (id: string) => void
}) {
  if (loading) {
    return (
      <div className="space-y-4">
  {[1, 2, 3].map((item) => (
    <CardShell key={item} className="h-[172px] animate-pulse bg-slate-50"> </CardShell>
  ))}
</div>
    )
  }

  if (!records.length) {
    return (
      <CardShell className="flex h-[320px] flex-col items-center justify-center p-8 text-center">
        <div className="grid h-16 w-16 place-items-center rounded-full bg-green-50 text-green-600">
          <ClipboardList className="h-8 w-8" />
        </div>

        <div className="mt-4 text-[20px] font-black text-slate-900">
          暂无饮食记录
        </div>

        <p className="mt-2 max-w-[360px] text-[14px] font-semibold leading-6 text-slate-500">
          上传食物图片后，AI 会自动识别食物、计算热量并生成饮食总结。
        </p>
      </CardShell>
    )
  }

  return (
    <div className="space-y-4 pb-4">
      {records.map((record) => (
        <MealRecordCard key={record.id} record={record} onClick={onRecordClick ? () => onRecordClick(record.id) : undefined} />
      ))}
    </div>
  )
}

function MealRecordCard({ record, onClick }: { record: FoodRecord; onClick?: () => void }) {
  return (
    <CardShell className={`overflow-hidden p-4 transition ${onClick ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-[0_18px_42px_rgba(15,23,42,0.08)]' : ''}`}>
      <div onClick={onClick} className="grid gap-4 md:grid-cols-[190px_minmax(0,1fr)]">
        <MealImage record={record} />

        <div className="min-w-0 py-1">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-green-600">{mealIconMap[record.mealType]}</span>
                <h3 className="text-[20px] font-black tracking-[-0.04em] text-slate-950">
                  {record.title}
                </h3>
                <span className="text-[14px] font-black text-slate-500">
                  {record.time}
                </span>
              </div>

              <div className="mt-3 flex items-end gap-1">
                <span className="text-[31px] font-black leading-none tracking-[-0.06em] text-orange-500">
                  {record.calories}
                </span>
                <span className="pb-1 text-[14px] font-black text-orange-500">
                  kcal
                </span>
              </div>
            </div>

            <div className="flex w-fit items-center gap-5 rounded-full bg-slate-50 px-4 py-2">
              <MacroBadge label="P" value={record.protein} className="text-green-600" />
              <MacroBadge label="C" value={record.carbs} className="text-orange-500" />
              <MacroBadge label="F" value={record.fat} className="text-violet-600" />
            </div>
          </div>

          <div className="mt-3 text-[15px] font-semibold leading-6 text-slate-500">
            <span className="font-black text-slate-600">主要食物：</span>
            <span className="font-bold text-slate-700">
              {record.foods.join('、')}
            </span>
          </div>

          <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 flex-1 items-start gap-3">
              <span className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-violet-100 px-2.5 py-1 text-[12px] font-black text-violet-600">
                <Sparkles className="h-3.5 w-3.5" />
                AI 总结
              </span>

              <p className="line-clamp-2 text-[14px] font-semibold leading-6 text-slate-500">
                {record.summary}
              </p>
            </div>

            <Link
              href={`/records/${record.id}`}
              className="flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-[14px] font-black text-slate-700 transition hover:bg-green-50 hover:text-green-700"
            >
              查看详情
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </CardShell>
  )
}

function MacroBadge({
  label,
  value,
  className,
}: {
  label: string
  value: number
  className: string
}) {
  return (
    <span className="text-[14px] font-black text-slate-500">
      <span className={className}>{label}</span> {value}g
    </span>
  )
}

function MealImage({ record }: { record: FoodRecord }) {
  if (record.imageUrl) {
    return (
      <img
        src={record.imageUrl}
        alt={record.title}
        className="h-[140px] w-full rounded-xl object-cover md:h-[150px]"
      />
    )
  }

  return <MealMockImage type={record.mealType} />
}

function MealMockImage({ type }: { type: MealType }) {
  const isBreakfast = type === 'breakfast'
  const isLunch = type === 'lunch'
  const isDinner = type === 'dinner'

  return (
    <div className="relative h-[140px] overflow-hidden rounded-xl bg-gradient-to-br from-amber-50 to-stone-100 md:h-[150px]">
      <div className="absolute inset-x-5 bottom-[-36px] h-[110px] rounded-[50%] bg-white shadow-[inset_0_-14px_24px_rgba(120,113,108,0.12),0_18px_24px_rgba(15,23,42,0.12)]" />

      {isBreakfast ? (
        <>
          <div className="absolute left-9 top-12 h-8 w-8 rounded-full bg-blue-950 shadow-[30px_8px_0_#172554,63px_1px_0_#111827]" />
          <div className="absolute left-[70px] top-7 h-11 w-11 rounded-full bg-yellow-100 shadow-[28px_8px_0_#fde68a]" />
          <div className="absolute bottom-9 left-8 h-6 w-6 rounded-full bg-amber-800 shadow-[27px_6px_0_#92400e,54px_-1px_0_#78350f,82px_5px_0_#a16207]" />
        </>
      ) : null}

      {isLunch ? (
        <>
          <div className="absolute left-7 top-8 h-[70px] w-[82px] rounded-[45%] bg-orange-100 shadow-[22px_8px_0_#fed7aa,48px_-2px_0_#ffedd5]" />
          <div className="absolute left-[92px] top-8 h-12 w-12 rounded-[50%] bg-green-600 shadow-[22px_-5px_0_#16a34a,40px_7px_0_#22c55e]" />
          <div className="absolute bottom-8 right-9 h-7 w-7 rounded-full bg-red-500 shadow-[-22px_6px_0_#ef4444]" />
        </>
      ) : null}

      {isDinner ? (
        <>
          <div className="absolute left-8 top-10 h-[54px] w-[98px] rotate-[-12deg] rounded-[45%] bg-orange-400 shadow-[0_0_0_4px_#fdba74]" />
          <div className="absolute left-[108px] top-10 h-9 w-12 rounded-[45%] bg-yellow-300 shadow-[22px_7px_0_#facc15,44px_-3px_0_#fde047]" />
          <div className="absolute right-7 top-8 h-12 w-14 rounded-[45%] bg-green-500 shadow-[-18px_18px_0_#22c55e]" />
        </>
      ) : null}

      {!isBreakfast && !isLunch && !isDinner ? (
        <>
          <div className="absolute left-8 top-9 h-12 w-12 rounded-full bg-lime-400 shadow-[36px_5px_0_#84cc16,72px_-4px_0_#65a30d]" />
          <div className="absolute right-10 top-12 h-9 w-9 rounded-full bg-red-400" />
        </>
      ) : null}

      <div className="absolute bottom-3 left-4 rounded-lg bg-white/90 px-3 py-1 text-[12px] font-black text-slate-500 shadow-sm backdrop-blur">
        AI 识别图片
      </div>
    </div>
  )
}

function DailySummaryCard({
  today,
  protein,
  carbs,
  fat,
}: {
  today: TodaySummary
  protein: number
  carbs: number
  fat: number
}) {
  return (
    <CardShell className="p-5">
      <CardTitle
        title="本日小结"
        icon={<CalendarDays className="h-5 w-5 text-green-600" />}
      />

      <div className="mt-5 space-y-1">
        <InsightItem
          icon={<Target className="h-5 w-5" />}
          title="热量 接近目标"
          text={`你今天还剩 ${today.remainingCalories} kcal 可用。`}
        />

        <InsightItem
          icon={<Leaf className="h-5 w-5" />}
          title="宏量营养 分布稳定"
          text={`蛋白质 ${protein}g，碳水 ${carbs}g，脂肪 ${fat}g。`}
        />

        <InsightItem
          icon={<Wheat className="h-5 w-5" />}
          title="建议明日早餐 补充更多蛋白质"
          text="可尝试鸡蛋、酸奶或蛋白奶昔。"
          noBorder
        />
      </div>

      <Link
        href="/upload"
        className="mt-5 flex h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-[16px] font-black text-white shadow-[0_12px_28px_rgba(34,197,94,0.24)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(34,197,94,0.3)]"
      >
        <Plus className="h-5 w-5" />
        上传新记录
      </Link>
    </CardShell>
  )
}

function InsightItem({
  icon,
  title,
  text,
  noBorder,
}: {
  icon: React.ReactNode
  title: string
  text: string
  noBorder?: boolean
}) {
  return (
    <div
      className={`flex gap-4 py-4 ${
        noBorder ? '' : 'border-b border-slate-100'
      }`}
    >
      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-green-50 text-green-600">
        {icon}
      </div>

      <div>
        <div className="text-[14px] font-black text-green-700">{title}</div>
        <p className="mt-1 text-[14px] font-semibold leading-6 text-slate-500">
          {text}
        </p>
      </div>
    </div>
  )
}

function QuickUploadCard({
  fileInputRef,
  uploadMealType,
  onMealTypeChange,
  onFileChange,
  uploadButtonText,
  uploadStatus,
}: {
  fileInputRef: React.RefObject<HTMLInputElement | null>
  uploadMealType: MealType
  onMealTypeChange: (value: MealType) => void
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void
  uploadButtonText: string
  uploadStatus: string
}) {
  return (
    <CardShell className="overflow-hidden p-5">
      <CardTitle title="继续记录" icon={null} />

      <div className="mt-5 rounded-2xl bg-gradient-to-br from-green-50 via-white to-lime-50 p-5 text-center">
        <div className="relative mx-auto h-[112px] w-[190px]">
          <div className="absolute left-[32px] top-[44px] h-[58px] w-[126px] rounded-b-[50px] rounded-t-[20px] bg-white shadow-[0_14px_30px_rgba(22,101,52,0.08)]" />
          <div className="absolute left-[48px] top-[24px] h-[62px] w-[94px] rounded-full bg-green-100" />
          <div className="absolute left-[34px] top-[32px] h-10 w-10 rounded-full bg-green-100" />
          <div className="absolute left-[70px] top-[25px] h-10 w-10 rounded-full bg-orange-300" />
          <div className="absolute left-[106px] top-[18px] h-11 w-11 rounded-full bg-lime-400" />
          <div className="absolute right-[32px] top-[35px] h-9 w-9 rounded-full bg-violet-300" />
          <div className="absolute right-[12px] top-[31px] h-10 w-10 rounded-full bg-green-100" />
        </div>

        <p className="mt-4 text-[14px] font-semibold leading-6 text-slate-500">
          轻松上传饮食图片，
          <br />
          让 AI 帮你分析营养与热量。
        </p>

        <div className="mt-4 grid grid-cols-4 gap-2">
          {(['breakfast', 'lunch', 'dinner', 'snack'] as MealType[]).map(
            (item) => (
              <button
                key={item}
                type="button"
                onClick={() => onMealTypeChange(item)}
                className={`h-9 rounded-xl text-[13px] font-black transition ${
                  uploadMealType === item
                    ? 'bg-green-600 text-white shadow-lg shadow-green-600/20'
                    : 'bg-white text-slate-500 hover:bg-green-50 hover:text-green-700'
                }`}
              >
                {mealTitleMap[item]}
              </button>
            ),
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={onFileChange}
        />

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="mt-4 flex h-[50px] w-full items-center justify-center gap-3 rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-[16px] font-black text-white shadow-[0_12px_28px_rgba(34,197,94,0.24)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(34,197,94,0.3)]"
        >
          <UploadCloud className="h-5 w-5" />
          {uploadButtonText}
        </button>

        <div className="mt-3 text-center text-[13px] font-bold text-slate-500">
          支持 JPG、PNG、WEBP，最大 10MB
        </div>

        {uploadStatus ? (
          <div className="mt-3 rounded-xl bg-white px-3 py-2 text-[12px] font-bold leading-5 text-green-700 shadow-sm">
            {uploadStatus}
          </div>
        ) : null}
      </div>
    </CardShell>
  )
}