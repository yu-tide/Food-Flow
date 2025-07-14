'use client'

import React, { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowRight,
  BarChart3,
  Eye,
  EyeOff,
  Leaf,
  Lock,
  MessageSquare,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Upload,
  User,
  WandSparkles,
} from 'lucide-react'
import { sendRegisterCode, register } from '@/services/auth'
import { ApiError } from '@/services/api'

type FormState = {
  phone: string
  code: string
  nickname: string
  password: string
  confirmPassword: string
}

type FormInputProps = {
  label: string
  name: keyof FormState
  type?: string
  value: string
  placeholder: string
  icon: React.ReactNode
  rightIcon?: React.ReactNode
  onRightIconClick?: () => void
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  required?: boolean
  maxLength?: number
  inputMode?: 'text' | 'numeric' | 'tel'
}

const PHONE_REGEX = /^1[3-9]\d{9}$/

function LeafLogo() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-10 w-10 text-green-600">
        <Leaf className="absolute left-1 top-2 h-7 w-7 -rotate-[28deg] fill-green-500/15 stroke-[2.6]" />
        <Leaf className="absolute left-4 top-0 h-8 w-8 rotate-[22deg] fill-green-500/15 stroke-[2.6]" />
        <Leaf className="absolute left-[18px] top-[20px] h-5 w-5 rotate-[70deg] fill-green-500/15 stroke-[2.6]" />
      </div>
      <span className="text-[27px] font-black tracking-[-0.04em] text-green-700">FoodFlow</span>
    </div>
  )
}

function FormInput({
  label,
  name,
  type = 'text',
  value,
  placeholder,
  icon,
  rightIcon,
  onRightIconClick,
  onChange,
  required,
  maxLength,
  inputMode,
}: FormInputProps) {
  return (
    <div>
      <label className="mb-2 block text-[15px] font-black text-gray-900">{label}</label>
      <div className="flex h-[58px] items-center rounded-xl border border-gray-200 bg-white px-4 text-gray-400 transition focus-within:border-green-600 focus-within:ring-4 focus-within:ring-green-600/10">
        <span className="mr-3 flex shrink-0 items-center text-gray-400">{icon}</span>
        <input
          name={name}
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          maxLength={maxLength}
          inputMode={inputMode}
          aria-label={label}
          className="h-full min-w-0 flex-1 bg-transparent text-[16px] font-semibold text-gray-900 outline-none placeholder:text-gray-400"
        />
        {rightIcon ? (
          <button
            type="button"
            onClick={onRightIconClick}
            className="ml-3 flex shrink-0 items-center text-gray-400 transition hover:text-gray-600"
            aria-label="切换密码显示状态"
          >
            {rightIcon}
          </button>
        ) : null}
      </div>
    </div>
  )
}

function StepItem({
  icon,
  iconClassName,
  title,
  desc,
}: {
  icon: React.ReactNode
  iconClassName: string
  title: string
  desc: string
}) {
  return (
    <div className="min-w-0 text-center">
      <div className={`mx-auto mb-4 grid h-[70px] w-[70px] place-items-center rounded-full shadow-[0_12px_24px_rgba(17,24,39,0.05)] ${iconClassName}`}>
        {icon}
      </div>
      <div className="mb-1.5 whitespace-nowrap text-[16px] font-black text-gray-900">{title}</div>
      <div className="min-h-[40px] text-[14px] font-medium leading-[21px] text-gray-500">{desc}</div>
    </div>
  )
}

function WeeklyOverviewCard() {
  return (
    <div className="w-[355px] rounded-3xl border border-white/90 bg-white/95 p-6 shadow-[0_24px_55px_rgba(46,70,47,0.16)] backdrop-blur-xl">
      <div className="mb-3 text-[17px] font-black text-gray-900">每周概览</div>
      <svg viewBox="0 0 300 82" fill="none" className="h-[74px] w-full">
        <path d="M8 58 C 35 44, 50 38, 72 43 S 110 48, 132 34 S 165 8, 190 27 S 226 49, 248 39 S 282 28, 294 25" stroke="#16a34a" strokeWidth="3.5" fill="none" strokeLinecap="round" />
        <g fill="#fff" stroke="#16a34a" strokeWidth="3">
          <circle cx="8" cy="58" r="5" /><circle cx="72" cy="43" r="5" /><circle cx="132" cy="34" r="5" />
          <circle cx="190" cy="27" r="5" /><circle cx="248" cy="39" r="5" /><circle cx="294" cy="25" r="5" />
        </g>
      </svg>
      <div className="mb-4 grid grid-cols-7 text-center text-[12px] font-medium text-gray-400">
        {['周一','周二','周三','周四','周五','周六','周日'].map((d) => (<span key={d}>{d}</span>))}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[['热量','1,270','千卡/日均'],['蛋白质','78 g','日均'],['连续记录','12','天']].map(([l,v,u]) => (
          <div key={l} className="rounded-2xl bg-gray-50 px-4 py-4 shadow-[0_8px_18px_rgba(18,36,24,0.035)]">
            <div className="mb-1.5 whitespace-nowrap text-[12px] font-black text-gray-400">{l}</div>
            <div className="whitespace-nowrap text-[21px] font-black leading-tight tracking-[-0.04em] text-gray-950">{v}</div>
            <div className="mt-1 text-[12px] font-semibold leading-snug text-gray-500">{u}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SaladPlaceholder() {
  return (
    <div className="relative h-[230px] w-[430px]">
      <div className="absolute bottom-0 left-0 h-[128px] w-[410px] rounded-[50%] border border-stone-200 bg-stone-50 shadow-[inset_0_-24px_46px_rgba(120,113,108,0.1),0_34px_46px_rgba(50,74,44,0.2)]" />
      <div className="absolute bottom-[92px] left-[52px] h-14 w-14 rounded-full bg-red-500 shadow-[38px_-8px_0_#ef4444,86px_2px_0_#f97316]" />
      <div className="absolute bottom-[121px] left-[82px] h-20 w-[270px] rounded-[50%] bg-lime-500/85 shadow-[32px_-8px_0_#84cc16,78px_5px_0_#65a30d,134px_-5px_0_#a3e635]" />
      <div className="absolute bottom-[102px] left-[178px] h-20 w-24 rounded-[50%] bg-green-200 shadow-[32px_4px_0_#bbf7d0,72px_-2px_0_#dcfce7]" />
      <div className="absolute bottom-[108px] left-[145px] h-[82px] w-[82px] rounded-[50%] bg-[#9bcf71]" />
      <div className="absolute bottom-[125px] left-[174px] h-14 w-[88px] rounded-[50%] bg-[#f7dca8]" />
      <div className="absolute bottom-[108px] left-[252px] grid grid-cols-4 gap-1">
        {Array.from({ length: 24 }).map((_, i) => (<span key={i} className="h-3.5 w-3.5 rounded-full bg-amber-200 shadow-sm" />))}
      </div>
    </div>
  )
}

function IllustrationArea() {
  return (
    <div className="relative mt-10 h-[340px] w-full max-w-[730px]">
      <div className="absolute bottom-[76px] left-[-120px] h-[136px] w-[680px] rounded-[50%] bg-gradient-to-r from-green-200/55 to-green-50/80" />
      <div className="absolute bottom-[24px] left-[-110px] z-20"><SaladPlaceholder /></div>
      <div className="absolute bottom-[58px] left-[285px] z-30"><WeeklyOverviewCard /></div>
      <div className="absolute bottom-[62px] left-[640px] z-10 hidden h-[200px] w-[120px] -rotate-6 opacity-70 xl:block">
        <span className="absolute bottom-0 left-[42px] h-[160px] w-[3px] origin-bottom rotate-[22deg] rounded-full bg-gradient-to-b from-green-300/20 to-green-700/40" />
        <span className="absolute left-[48px] top-1 h-[58px] w-[30px] rotate-[40deg] rounded-[100%_0_100%_0] bg-gradient-to-b from-green-500/90 to-green-200/80" />
        <span className="absolute left-4 top-14 h-[58px] w-[30px] rotate-[67deg] rounded-[100%_0_100%_0] bg-gradient-to-b from-green-500/90 to-green-200/80" />
        <span className="absolute left-[74px] top-[78px] h-[58px] w-[30px] rotate-[23deg] rounded-[100%_0_100%_0] bg-gradient-to-b from-green-500/90 to-green-200/80" />
      </div>
    </div>
  )
}

function LeftPanel() {
  return (
    <section className="relative hidden min-h-[100svh] items-center justify-center overflow-hidden bg-white lg:flex">
      <div className="flex w-full max-w-[760px] flex-col px-10 py-8">
        <LeafLogo />
        <div className="mt-10 inline-flex h-9 w-fit items-center gap-2 rounded-full bg-violet-100 px-5 text-[15px] font-black text-violet-600 shadow-[0_10px_24px_rgba(99,87,255,0.08)]">
          <Sparkles className="h-4 w-4 stroke-[2.8]" /><span>AI 营养助手</span>
        </div>
        <h1 className="mt-7 max-w-[650px] text-[54px] font-black leading-[1.12] tracking-[-0.06em] text-gray-950 xl:text-[60px]">AI 驱动的营养记录，<br />轻松开始</h1>
        <p className="mt-5 max-w-[620px] text-[18px] font-medium leading-8 text-gray-500">上传饮食图片，FoodFlow 会自动分析营养、追踪进度，帮助你实现健康目标。</p>
        <div className="mt-10 grid w-full max-w-[690px] grid-cols-[1fr_58px_1fr_58px_1fr] items-start">
          <StepItem icon={<Upload className="h-8 w-8 stroke-[2.5]" />} iconClassName="bg-green-50 text-green-600" title="1. 上传图片" desc="拍下你的食物" />
          <div className="flex justify-center pt-7 text-gray-400"><ArrowRight className="h-8 w-8 stroke-[1.8]" /></div>
          <StepItem icon={<WandSparkles className="h-8 w-8 stroke-[2.5]" />} iconClassName="bg-violet-100 text-violet-600" title="2. 智能分析" desc="AI 自动识别营养与分量" />
          <div className="flex justify-center pt-7 text-gray-400"><ArrowRight className="h-8 w-8 stroke-[1.8]" /></div>
          <StepItem icon={<BarChart3 className="h-8 w-8 stroke-[2.5]" />} iconClassName="bg-blue-50 text-blue-600" title="3. 查看洞察" desc="追踪趋势并达成目标" />
        </div>
        <IllustrationArea />
        <div className="flex items-center gap-3 text-[15px] font-black text-gray-500">
          <span className="grid h-[36px] w-[36px] place-items-center rounded-full bg-green-50 text-green-600"><ShieldCheck className="h-[19px] w-[19px] stroke-[2.4]" /></span>
          <span>你的数据安全且私密。</span>
        </div>
      </div>
    </section>
  )
}

function AuthTabs({ onLoginClick }: { onLoginClick: () => void }) {
  return (
    <div className="relative mb-10 grid h-[68px] grid-cols-2 overflow-hidden rounded-xl border border-gray-200 bg-gray-50">
      <span className="absolute bottom-0 left-1/2 h-[3px] w-1/2 bg-green-600" />
      <button type="button" onClick={onLoginClick} className="relative z-10 grid place-items-center text-[17px] font-black text-gray-500 transition hover:bg-white hover:text-green-700">登录</button>
      <button type="button" aria-current="page" className="relative z-10 grid cursor-default place-items-center bg-white text-[17px] font-black text-green-700 shadow-[0_8px_18px_rgba(17,24,39,0.05)]">注册</button>
    </div>
  )
}

export default function RegisterPage() {
  const router = useRouter()
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const [form, setForm] = useState<FormState>({
    phone: '',
    code: '',
    nickname: '',
    password: '',
    confirmPassword: '',
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [devCode, setDevCode] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [countdown, setCountdown] = useState(0)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { value, name } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  const validate = (): string | null => {
    if (!PHONE_REGEX.test(form.phone.trim())) return '请输入正确的手机号'
    if (!/^\d{6}$/.test(form.code)) return '请输入6位验证码'
    if (!form.nickname.trim()) return '请输入昵称'
    if (form.password.length < 8) return '密码至少 8 位'
    if (form.password !== form.confirmPassword) return '两次输入的密码不一致'
    return null
  }

  const handleSendCode = async () => {
    const phone = form.phone.trim()
    if (!PHONE_REGEX.test(phone)) {
      setError('请输入正确的手机号')
      return
    }
    setError(null)
    setSending(true)
    try {
      const result = await sendRegisterCode(phone)
      if (result.dev_code) setDevCode(result.dev_code)
      setCountdown(60)
      if (countdownRef.current) clearInterval(countdownRef.current)
      countdownRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            if (countdownRef.current) clearInterval(countdownRef.current)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) setError('手机号已注册')
        else if (err.status === 429) setError('验证码发送太频繁，请稍后再试')
        else setError(err.message)
      } else {
        setError('验证码发送失败')
      }
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError(null)

    const msg = validate()
    if (msg) { setError(msg); return }

    setLoading(true)
    try {
      await register({
        phone: form.phone.trim(),
        code: form.code,
        nickname: form.nickname.trim(),
        password: form.password,
      })
      setDevCode(null)
      router.push('/login?registered=1')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) setError('手机号已注册')
        else if (err.status === 400) setError('验证码错误或已过期')
        else setError(err.message)
      } else {
        setError('注册失败，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-[100svh] overflow-hidden bg-white text-gray-900">
      <div className="grid min-h-[100svh] grid-cols-1 lg:grid-cols-[minmax(680px,1.06fr)_minmax(560px,0.94fr)]">
        <LeftPanel />
        <section className="relative flex min-h-[100svh] items-center justify-center bg-white px-5 py-8 sm:px-8 lg:px-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(22,163,74,0.06),transparent_32%),linear-gradient(180deg,rgba(249,250,251,0.7),rgba(255,255,255,1))]" />
          <div className="relative w-full max-w-[760px] rounded-[24px] border border-gray-200 bg-white/95 p-7 shadow-[0_24px_70px_rgba(22,32,48,0.10)] backdrop-blur-xl sm:p-10 lg:p-12">
            <AuthTabs onLoginClick={() => router.push('/login')} />
            <h2 className="mb-3 text-[34px] font-black leading-tight tracking-[-0.06em] text-gray-950 sm:text-[38px]">创建你的账号</h2>
            <p className="mb-8 text-[16px] font-semibold leading-relaxed text-gray-500">加入 FoodFlow，开启更健康的饮食管理。</p>

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* 手机号 */}
              <FormInput
                label="手机号"
                name="phone"
                value={form.phone}
                onChange={handleChange}
                placeholder="请输入你的手机号"
                icon={<Smartphone className="h-[20px] w-[20px] stroke-[2.2]" />}
                maxLength={11}
                inputMode="tel"
                required
              />

              {/* 验证码 + 获取按钮 */}
              <div>
                <label className="mb-2 block text-[15px] font-black text-gray-900">验证码</label>
                <div className="flex gap-3">
                  <div className="flex h-[58px] flex-1 items-center rounded-xl border border-gray-200 bg-white px-4 text-gray-400 transition focus-within:border-green-600 focus-within:ring-4 focus-within:ring-green-600/10">
                    <span className="mr-3 flex shrink-0 items-center text-gray-400">
                      <MessageSquare className="h-[20px] w-[20px] stroke-[2.2]" />
                    </span>
                    <input
                      name="code"
                      type="text"
                      value={form.code}
                      onChange={handleChange}
                      placeholder="6位验证码"
                      required
                      maxLength={6}
                      inputMode="numeric"
                      aria-label="验证码"
                      className="h-full min-w-0 flex-1 bg-transparent text-[16px] font-semibold text-gray-900 outline-none placeholder:text-gray-400"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleSendCode}
                    disabled={countdown > 0 || sending}
                    className="h-[58px] shrink-0 rounded-xl bg-green-600 px-5 text-[15px] font-black text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {sending ? '发送中...' : countdown > 0 ? `${countdown}秒` : '获取验证码'}
                  </button>
                </div>
                {devCode ? (
                  <div className="mt-2 text-[13px] font-semibold text-violet-600">
                    开发验证码：{devCode}
                  </div>
                ) : null}
              </div>

              <FormInput
                label="昵称"
                name="nickname"
                value={form.nickname}
                onChange={handleChange}
                placeholder="请输入你的昵称"
                icon={<User className="h-[20px] w-[20px] stroke-[2.2]" />}
                required
              />

              <div>
                <FormInput
                  label="密码"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={handleChange}
                  placeholder="设置一个安全密码"
                  icon={<Lock className="h-[20px] w-[20px] stroke-[2.2]" />}
                  rightIcon={showPassword ? <EyeOff className="h-[20px] w-[20px] stroke-[2.2]" /> : <Eye className="h-[20px] w-[20px] stroke-[2.2]" />}
                  onRightIconClick={() => setShowPassword((p) => !p)}
                  required
                />
                <div className="mt-2 text-[13px] font-semibold text-gray-400">密码至少 8 位</div>
              </div>

              <FormInput
                label="确认密码"
                name="confirmPassword"
                type={showConfirmPassword ? 'text' : 'password'}
                value={form.confirmPassword}
                onChange={handleChange}
                placeholder="请再次输入密码"
                icon={<Lock className="h-[20px] w-[20px] stroke-[2.2]" />}
                rightIcon={showConfirmPassword ? <EyeOff className="h-[20px] w-[20px] stroke-[2.2]" /> : <Eye className="h-[20px] w-[20px] stroke-[2.2]" />}
                onRightIconClick={() => setShowConfirmPassword((p) => !p)}
                required
              />

              {error ? (
                <div className="rounded-xl bg-red-50 px-4 py-3 text-[14px] font-semibold text-red-600">{error}</div>
              ) : null}

              <button
                type="submit"
                disabled={loading}
                aria-busy={loading}
                className="h-[58px] w-full rounded-xl bg-gradient-to-b from-green-500 to-green-700 text-[17px] font-black tracking-[0.04em] text-white shadow-[0_12px_28px_rgba(31,157,69,0.26)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(31,157,69,0.31)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? '注册中...' : '创建账号'}
              </button>

              <div className="pt-5 text-center text-[16px] font-extrabold text-gray-500">
                已有账号？{' '}
                <button type="button" onClick={() => router.push('/login')} className="ml-2 font-black text-green-700 transition hover:text-green-600">去登录</button>
              </div>
            </form>
          </div>
        </section>
      </div>
    </main>
  )
}
