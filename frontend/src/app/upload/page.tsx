'use client'

import React, { useRef, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  BarChart3,
  CalendarCheck,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  CloudUpload,
  Coffee,

  FileText,
  Home,
  ImageIcon,
  Leaf,
  Lightbulb,
  Lock,
  Moon,
  RefreshCcw,
  Settings,
  Sparkles,
  Sun,
  Trash2,
  UploadCloud,
  Utensils,
  X,
} from 'lucide-react'
import AccountMenu from '@/components/user/AccountMenu'
import ProfileEntry from '@/components/user/ProfileEntry'
import { useUploadDraft } from '@/stores/uploadDraftStore'

type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'

type MessageState = {
  type: 'success' | 'error'
  text: string
} | null

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
  } catch { /* ignore parse errors */ }
  return { nickname: '', phone: '', avatarText: '' }
}

const user = getUserProfile()

const mealOptions: Array<{
  value: MealType
  label: string
  icon: React.ReactNode
}> = [
  {
    value: 'breakfast',
    label: '早餐',
    icon: <Sun className="h-4 w-4" />,
  },
  {
    value: 'lunch',
    label: '午餐',
    icon: <Sun className="h-4 w-4" />,
  },
  {
    value: 'dinner',
    label: '晚餐',
    icon: <Moon className="h-4 w-4" />,
  },
  {
    value: 'snack',
    label: '加餐',
    icon: <Coffee className="h-4 w-4" />,
  },
]

const uploadTips = [
  {
    title: '光线充足',
    desc: '自然光更有助于清晰、准确地识别。',
    icon: <Lightbulb className="h-5 w-5" />,
    tone: 'text-yellow-500 bg-yellow-50',
  },
  {
    title: '拍全整份餐食',
    desc: '尽量包含所有食物，便于更准确估算热量。',
    icon: <CalendarCheck className="h-5 w-5" />,
    tone: 'text-green-600 bg-green-50',
  },
  {
    title: '标签文字清晰',
    desc: '如果上传营养标签，请确保文字清楚、对焦准确。',
    icon: <FileText className="h-5 w-5" />,
    tone: 'text-green-600 bg-green-50',
  },
  {
    title: '一次上传一张',
    desc: '每次上传一张图片，分析效果更好。',
    icon: <ImageIcon className="h-5 w-5" />,
    tone: 'text-green-600 bg-green-50',
  },
]

export default function UploadPage() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const { draft, setDraft, clearDraft } = useUploadDraft()
  const file = draft.file
  const previewUrl = draft.previewUrl
  const [mealType, setMealType] = useState<MealType>('lunch')
  const [remark, setRemark] = useState('')
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [message, setMessage] = useState<MessageState>(null)

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })

    window.setTimeout(() => {
      setMessage(null)
    }, 2600)
  }

  const validateFile = (selected: File) => {
    if (!selected.type.startsWith('image/')) {
      showMessage('error', '请选择 JPG 或 PNG 图片文件')
      return false
    }

    if (selected.size > 10 * 1024 * 1024) {
      showMessage('error', '图片不能超过 10MB')
      return false
    }

    return true
  }

  const applySelectedFile = (selected: File) => {
    if (!validateFile(selected)) return
    setDraft(selected, 'file')
    setMessage(null)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (!selected) return

    applySelectedFile(selected)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault()
    setDragging(false)

    const selected = e.dataTransfer.files?.[0]
    if (!selected) return

    applySelectedFile(selected)
  }

  const handleDelete = () => {
    clearDraft()
  }

  const handleUpload = async () => {
    if (!file) {
      showMessage('error', '请先选择一张食物图片')
      return
    }

    setUploading(true)

    try {
      const formData = new FormData()
      formData.append('image', file)
      formData.append('meal_type', mealType)
      formData.append('remark', remark)

      const token =
        typeof window !== 'undefined' ? localStorage.getItem('token') : null

      const res = await fetch(`${API_BASE}/api/foods/upload`, {
        method: 'POST',
        body: formData,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })

      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          router.push('/login')
          return
        }
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || data.message || '上传失败，请重试')
      }

      const data = await res.json()
      const taskId = data.task_id ?? data.taskId ?? data.id

      if (!taskId) {
        throw new Error('后端未返回 task_id')
      }

      clearDraft()
      showMessage('success', '上传成功，正在进入分析流程')
      router.push(`/analyze/${taskId}`)
    } catch (err: unknown) {
      showMessage('error', err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#f8faf8] text-slate-950 lg:h-screen lg:overflow-hidden">
      <div className="grid min-h-screen grid-cols-1 lg:h-screen lg:grid-cols-[220px_minmax(0,1fr)]">
        <Sidebar user={user} />

        <section className="min-w-0 bg-white lg:h-screen lg:overflow-hidden">
          <div className="mx-auto flex h-full w-full max-w-[1480px] flex-col px-5 py-4 sm:px-6 lg:px-7">
            <TopHeader user={user} />

            <div className="mt-4 grid min-h-0 flex-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
              <div className="min-w-0">
                <section className="flex h-full min-h-0 flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_14px_34px_rgba(15,23,42,0.055)]">
                  <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(390px,1fr)_400px]">
                    <UploadDropZone
                      dragging={dragging}
                      onDragEnter={() => setDragging(true)}
                      onDragLeave={() => setDragging(false)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={handleDrop}
                      onChoose={() => fileInputRef.current?.click()}
                    />

                    <PreviewCard
                      file={file}
                      previewUrl={previewUrl}
                      onChoose={() => fileInputRef.current?.click()}
                      onDelete={handleDelete}
                    />
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/webp"
                    className="hidden"
                    onChange={handleFileChange}
                  />

                  <div className="mt-5 shrink-0">
                    <div className="mb-2 flex items-center gap-2">
                      <Utensils className="h-4 w-4 text-green-600" />
                      <h2 className="text-[15px] font-black text-slate-900">
                        餐别
                      </h2>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      {mealOptions.map((item) => {
                        const active = item.value === mealType

                        return (
                          <button
                            key={item.value}
                            type="button"
                            onClick={() => setMealType(item.value)}
                            className={`flex h-[48px] items-center justify-center gap-2 rounded-xl border text-[15px] font-black transition ${
                              active
                                ? 'border-green-500 bg-green-50 text-green-700 shadow-[0_8px_20px_rgba(34,197,94,0.11)]'
                                : 'border-slate-200 bg-white text-slate-700 hover:border-green-200 hover:bg-green-50/60 hover:text-green-700'
                            }`}
                          >
                            <span
                              className={
                                active ? 'text-green-600' : 'text-slate-500'
                              }
                            >
                              {item.icon}
                            </span>
                            {item.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div className="mt-4 shrink-0">
                    <div className="mb-2 flex items-center gap-2">
                      <FileText className="h-4 w-4 text-green-600" />
                      <h2 className="text-[15px] font-black text-slate-900">
                        备注
                      </h2>
                      <span className="text-[13px] font-bold text-slate-400">
                        （可选）
                      </span>
                    </div>

                    <div className="relative">
                      <textarea
                        value={remark}
                        maxLength={300}
                        onChange={(e) => setRemark(e.target.value)}
                        placeholder="可补充食材、分量等信息，帮助 AI 更准确分析..."
                        className="h-[82px] w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-[15px] font-semibold leading-6 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-green-500 focus:ring-4 focus:ring-green-500/10"
                      />

                      <div className="absolute bottom-3 right-4 text-[12px] font-bold text-slate-400">
                        {remark.length}/300
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleUpload}
                    disabled={uploading}
                    className="mt-4 flex h-[56px] shrink-0 items-center justify-center gap-3 rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-[20px] font-black text-white shadow-[0_14px_30px_rgba(34,197,94,0.25)] transition hover:-translate-y-0.5 hover:shadow-[0_18px_38px_rgba(34,197,94,0.3)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                  >
                    {uploading ? (
                      <>
                        <RefreshCcw className="h-5 w-5 animate-spin" />
                        上传中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-6 w-6" />
                        开始分析
                      </>
                    )}
                  </button>

                  <div className="mt-3 flex shrink-0 items-center justify-center gap-2 text-[13px] font-bold text-slate-500">
                    <Lock className="h-4 w-4" />
                    你的数据安全且私密
                  </div>

                  {message ? (
                    <div
                      className={`mt-3 shrink-0 rounded-xl px-4 py-3 text-center text-[14px] font-black ${
                        message.type === 'success'
                          ? 'bg-green-50 text-green-700'
                          : 'bg-red-50 text-red-600'
                      }`}
                    >
                      {message.text}
                    </div>
                  ) : null}
                </section>
              </div>

              <aside className="hidden min-h-0 space-y-4 xl:block">
                <UploadTipsCard />
                <RecentUploadCard file={file} previewUrl={previewUrl} />
              </aside>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}

function Sidebar({ user }: { user: UserProfile }) {
  const pathname = usePathname()

  return (
    <aside className="hidden h-screen overflow-hidden border-r border-slate-200 bg-white px-4 py-5 lg:flex lg:flex-col">
      <AppLogo />

      <nav className="mt-7 space-y-2">
        <SidebarItem
          href="/dashboard"
          pathname={pathname}
          icon={<Home className="h-5 w-5" />}
          label="首页"
        />

        <SidebarItem
          href="/upload"
          pathname={pathname}
          icon={<CloudUpload className="h-5 w-5" />}
          label="上传"
        />

        <SidebarItem
          href="/records"
          pathname={pathname}
          icon={<ClipboardList className="h-5 w-5" />}
          label="记录"
        />

        <SidebarItem
          href="/statistics/weekly"
          pathname={pathname}
          icon={<BarChart3 className="h-5 w-5" />}
          label="每周统计"
        />

        <SidebarItem
          href="/settings"
          pathname={pathname}
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
  pathname,
}: {
  href: string
  icon: React.ReactNode
  label: string
  pathname: string
}) {
  const active =
    href === '/dashboard'
      ? pathname === '/dashboard' || pathname === '/'
      : pathname === href || pathname.startsWith(`${href}/`)

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

function TopHeader({ user }: { user: UserProfile }) {
  return (
    <header className="flex shrink-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="flex items-start gap-4">
        <div className="grid h-[64px] w-[64px] shrink-0 place-items-center rounded-2xl border border-slate-200 bg-white text-green-600 shadow-[0_14px_30px_rgba(15,23,42,0.07)]">
          <CloudUpload className="h-8 w-8" />
        </div>

        <div>
          <h1 className="text-[32px] font-black leading-tight tracking-[-0.06em] text-slate-950 sm:text-[36px]">
            上传食物图片
          </h1>

          <p className="mt-1.5 text-[16px] font-semibold text-slate-500">
            上传食物照片、外卖截图或营养标签，让 AI 为你分析。
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4 lg:pt-1">
        <div className="text-right">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-50 px-3.5 py-1.5 text-[14px] font-black text-green-700">
            <CheckCircle2 className="h-4 w-4" />
            状态良好
          </div>

          <div className="text-[14px] font-semibold text-slate-500">
            你今天还差{' '}
            <span className="font-black text-slate-700">230</span> kcal 达标
          </div>
        </div>

        <ProfileEntry user={user || undefined} statusText="状态良好" detailText="点击进入个人中心" />
      </div>
    </header>
  )
}

function UploadDropZone({
  dragging,
  onChoose,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
}: {
  dragging: boolean
  onChoose: () => void
  onDragEnter: () => void
  onDragLeave: () => void
  onDragOver: (e: React.DragEvent<HTMLLabelElement>) => void
  onDrop: (e: React.DragEvent<HTMLLabelElement>) => void
}) {
  return (
    <label
      onClick={onChoose}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`flex min-h-[258px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-5 text-center transition ${
        dragging
          ? 'border-green-500 bg-green-50'
          : 'border-green-400 bg-green-50/20 hover:bg-green-50/60'
      }`}
    >
      <div className="grid h-[86px] w-[86px] place-items-center rounded-full bg-green-100 text-green-700 shadow-[0_14px_30px_rgba(34,197,94,0.12)]">
        <UploadCloud className="h-11 w-11" />
      </div>

      <div className="mt-5 text-[20px] font-black text-slate-900">
        拖拽文件到这里，或点击上传
      </div>

      <div className="mt-2 text-[15px] font-bold text-slate-500">
        支持 JPG、PNG，最大 10MB
      </div>

      <div className="mt-4 text-[16px] font-black text-green-700 underline underline-offset-4">
        选择文件
      </div>
    </label>
  )
}

function PreviewCard({
  file,
  previewUrl,
  onChoose,
  onDelete,
}: {
  file: File | null
  previewUrl: string | null
  onChoose: () => void
  onDelete: () => void
}) {
  if (!file || !previewUrl) {
    return (
      <div className="flex min-h-[258px] flex-col items-center justify-center rounded-2xl border border-slate-200 bg-slate-50/70 p-5 text-center">
        <div className="grid h-16 w-16 place-items-center rounded-full bg-white text-slate-300 shadow-sm">
          <ImageIcon className="h-8 w-8" />
        </div>

        <div className="mt-4 text-[17px] font-black text-slate-700">
          图片预览区
        </div>

        <p className="mt-1.5 max-w-[260px] text-[14px] font-semibold leading-6 text-slate-500">
          选择图片后，会在这里显示预览、上传进度与文件信息。
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-[258px] flex-col rounded-2xl border border-slate-200 bg-white p-3 shadow-[0_14px_30px_rgba(15,23,42,0.07)]">
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-100 bg-[radial-gradient(circle_at_center,#f8fafc_0,#f1f5f9_55%,#eef2f7_100%)]">
        <img
          src={previewUrl}
          alt={file.name}
          className="h-full w-full object-contain p-3"
        />

        <div className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-white/95 px-3 py-1.5 text-[13px] font-black text-green-700 shadow-lg shadow-slate-900/5 backdrop-blur">
          <Check className="h-4 w-4 stroke-[3]" />
          已选择
        </div>

        <button
          type="button"
          onClick={onDelete}
          className="absolute right-3 top-3 grid h-9 w-9 place-items-center rounded-full bg-white/95 text-slate-500 shadow-lg shadow-slate-900/5 backdrop-blur transition hover:bg-red-50 hover:text-red-500"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="mt-3 shrink-0 rounded-xl border border-slate-100 bg-white px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-[17px] font-black tracking-[-0.03em] text-slate-950">
              {file.name}
            </div>

            <div className="mt-1 text-[13px] font-bold text-slate-500">
              {(file.size / 1024 / 1024).toFixed(1)} MB ·{' '}
              {file.type.includes('png') ? 'PNG' : 'JPG'}
            </div>
          </div>

          <span className="shrink-0 rounded-full bg-green-50 px-2.5 py-1 text-[12px] font-black text-green-700">
            100%
          </span>
        </div>

        <div className="mt-3 flex items-center gap-3">
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full w-full rounded-full bg-green-600" />
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={onChoose}
            className="flex h-10 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white text-[14px] font-black text-slate-700 transition hover:bg-slate-50"
          >
            <RefreshCcw className="h-4 w-4" />
            替换
          </button>

          <button
            type="button"
            onClick={onDelete}
            className="flex h-10 items-center justify-center gap-2 rounded-xl bg-red-50 text-[14px] font-black text-red-500 transition hover:bg-red-100"
          >
            <Trash2 className="h-4 w-4" />
            删除
          </button>
        </div>
      </div>
    </div>
  )
}

function UploadTipsCard() {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_14px_34px_rgba(15,23,42,0.055)]">
      <div className="mb-3 flex items-center gap-3">
        <Lightbulb className="h-7 w-7 text-yellow-500" />
        <h2 className="text-[22px] font-black tracking-[-0.04em] text-green-700">
          上传提示
        </h2>
      </div>

      <div>
        {uploadTips.map((item, index) => (
          <div
            key={item.title}
            className={`flex gap-4 py-3 ${
              index === uploadTips.length - 1
                ? ''
                : 'border-b border-slate-100'
            }`}
          >
            <div
              className={`grid h-[50px] w-[50px] shrink-0 place-items-center rounded-full ${item.tone}`}
            >
              {item.icon}
            </div>

            <div className="min-w-0">
              <div className="text-[17px] font-black tracking-[-0.04em] text-slate-950">
                {item.title}
              </div>

              <p className="mt-1 text-[13px] font-semibold leading-5 text-slate-500">
                {item.desc}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function RecentUploadCard({
  file,
  previewUrl,
}: {
  file: File | null
  previewUrl: string | null
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_14px_34px_rgba(15,23,42,0.055)]">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[20px] font-black tracking-[-0.04em] text-slate-950">
          最近上传
        </h2>

        <Link
          href="/records"
          className="text-[14px] font-black text-green-700 transition hover:text-green-600"
        >
          查看全部
        </Link>
      </div>

      {file && previewUrl ? (
        <div className="flex gap-3">
          <img
            src={previewUrl}
            alt={file.name}
            className="h-[76px] w-[76px] shrink-0 rounded-xl object-cover"
          />

          <div className="min-w-0 flex-1">
            <div className="truncate text-[16px] font-black text-slate-900">
              {file.name}
            </div>

            <div className="mt-1.5 flex items-center gap-2 text-[14px] font-black text-orange-500">
              <ClockIcon />
              等待分析
            </div>

            <div className="mt-1 text-[13px] font-semibold text-slate-500">
              刚刚上传
            </div>

            <div className="mt-2 inline-flex rounded-lg bg-orange-100 px-3 py-1.5 text-[13px] font-black text-orange-500">
              队列中
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl bg-slate-50 px-4 py-6 text-center">
          <ImageIcon className="mx-auto h-8 w-8 text-slate-300" />

          <div className="mt-2 text-[15px] font-black text-slate-700">
            暂无上传记录
          </div>

          <p className="mt-1 text-[13px] font-semibold text-slate-500">
            选择图片后会显示在这里。
          </p>
        </div>
      )}
    </section>
  )
}

function ClockIcon() {
  return (
    <span className="grid h-4 w-4 place-items-center rounded-full border-2 border-orange-400">
      <span className="h-1 w-1 rounded-full bg-orange-400" />
    </span>
  )
}