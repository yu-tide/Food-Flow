import { apiGet } from './api'

// --- Backend response types ---

export type FoodItemRaw = {
  id: string
  food_name: string
  weight: string
  calories: number
  protein: number
  carbohydrate: number
  fat: number
  category?: string | null
  confidence?: number | null
  source?: string | null
  estimated?: boolean | null
  image_url?: string | null
  dish_family?: string | null
  alternatives?: Array<{ name: string; confidence?: number | null }> | null
  user_correction?: string | null
  components?: Array<{
    name: string
    confidence?: number | null
    estimated_weight_g?: number | null
    calories?: number | null
    protein?: number | null
    carbs?: number | null
    fat?: number | null
    role?: string | null
    include_in_total?: boolean | null
  }> | null
}

export type FoodRecordRaw = {
  id: string
  status?: string | null
  status_label: string
  confirmed_at?: string | null
  total_calories: number
  protein: number
  carbohydrate: number
  fat: number
  target_calories: number
  image_url?: string | null
  created_at?: string | null
  summary?: string | null
  ocr_text?: string | null
  is_food_detected?: boolean | null
  non_food_reason?: string | null
  analysis_mode?: string | null
}

export type AiLogRaw = {
  prompt_version?: string | null
  latency?: string | null
  cache_hit: boolean
}

export type MacroTargetsRaw = {
  protein: number
  carbs: number
  fat: number
}

export type MacroPercentagesRaw = {
  protein: number
  carbs: number
  fat: number
}

export type FoodDetailRaw = {
  record: FoodRecordRaw
  food_items: FoodItemRaw[]
  ai_log: AiLogRaw
  macro_targets: MacroTargetsRaw
  macro_percentages: MacroPercentagesRaw
}

export type FoodDetailResponseRaw = {
  data: FoodDetailRaw
}

// --- Frontend page types ---

export type MacroInfo = {
  key: 'protein' | 'carbs' | 'fat'
  label: string
  value: number
  target: number
  unit: string
  percent: number
}

export type FoodItem = {
  id: string
  name: string
  weight: string
  calories: number
  protein: number
  carbs: number
  fat: number
  category: string
  confidence: number
  source: string
  estimated: boolean
  imageUrl: string
  includeInTotal?: boolean
  dishFamily?: string | null
  alternatives?: Array<{ name: string; confidence?: number | null }> | null
  userCorrection?: string | null
  components?: Array<{
    name: string
    confidence?: number | null
    estimatedWeightG?: number | null
    calories?: number | null
    protein?: number | null
    carbs?: number | null
    fat?: number | null
    role?: string | null
    includeInTotal?: boolean | null
  }> | null
}

export type AnalyzeResult = {
  id: string
  status: string
  statusLabel: string
  analysisMode: string
  totalCalories: number
  remainingCalories: number
  targetCalories: number
  imageUrl: string
  createdAt: string
  macros: MacroInfo[]
  foodItems: FoodItem[]
  aiSummary: string[]
  technical: {
    ocrText: string
    promptVersion: string
    aiLatency: string
    cacheHit: boolean
  }
}

// --- Adapter ---

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function resolveImageUrl(value?: string | null): string {
  if (!value) return ''
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''
  if (value.startsWith('http://') || value.startsWith('https://')) return value
  if (value.startsWith('/') && API_BASE) return `${API_BASE}${value}`
  return value
}

function splitSummary(raw?: string | null): string[] {
  if (!raw) return []
  return raw
    .split(/\n/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export function adaptFoodDetail(data: FoodDetailRaw): AnalyzeResult {
  const r = data.record
  const macros: MacroInfo[] = [
    {
      key: 'protein', label: '蛋白质', value: r.protein,
      target: data.macro_targets.protein ?? 120, unit: 'g',
      percent: clampPercent(data.macro_percentages?.protein ?? 0),
    },
    {
      key: 'carbs', label: '碳水', value: r.carbohydrate,
      target: data.macro_targets.carbs ?? 250, unit: 'g',
      percent: clampPercent(data.macro_percentages?.carbs ?? 0),
    },
    {
      key: 'fat', label: '脂肪', value: r.fat,
      target: data.macro_targets.fat ?? 70, unit: 'g',
      percent: clampPercent(data.macro_percentages?.fat ?? 0),
    },
  ]

  const totalCalories = r.total_calories ?? 0
  const targetCalories = r.target_calories ?? 2000

  return {
    id: r.id,
    status: r.status ?? 'draft',
    statusLabel: r.status_label ?? '分析完成',
    analysisMode: r.analysis_mode ?? 'dish_with_components',
    totalCalories,
    remainingCalories: Math.max(targetCalories - totalCalories, 0),
    targetCalories,
    imageUrl: resolveImageUrl(r.image_url),
    createdAt: r.created_at ?? '',
    macros,
    foodItems: data.food_items.map((item) => ({
      id: item.id,
      name: item.food_name,
      weight: item.weight,
      calories: item.calories,
      protein: item.protein,
      carbs: item.carbohydrate,
      fat: item.fat,
      category: item.category ?? 'unknown',
      confidence: item.confidence ?? 0,
      source: item.source || 'unknown',
      estimated: item.estimated ?? false,
      imageUrl: resolveImageUrl(item.image_url),
      dishFamily: item.dish_family ?? null,
      alternatives: item.alternatives?.map((a: Record<string, unknown>) => ({ name: String(a.name || ""), confidence: Number(a.confidence) || null })) ?? null,
      userCorrection: item.user_correction ?? null,
      components: item.components?.map(c => ({
        name: c.name, confidence: c.confidence, estimatedWeightG: c.estimated_weight_g,
        calories: c.calories, protein: c.protein, carbs: c.carbs, fat: c.fat,
        role: c.role, includeInTotal: c.include_in_total,
      })) ?? null,
    })),
    aiSummary: splitSummary(r.summary),
    technical: {
      ocrText: r.ocr_text ?? '',
      promptVersion: data.ai_log.prompt_version ?? '',
      aiLatency: data.ai_log.latency ?? '',
      cacheHit: data.ai_log.cache_hit ?? false,
    },
  }
}

export async function getFoodRecord(id: string): Promise<AnalyzeResult> {
  const res = await apiGet<FoodDetailResponseRaw>(`/api/foods/${id}`)
  return adaptFoodDetail(res.data)
}
