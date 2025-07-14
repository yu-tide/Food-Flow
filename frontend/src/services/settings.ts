import { apiGet, apiPatch, apiPost } from './api'

// --- Types (snake_case to match API) ---

export type UserSettings = {
  gender: string | null
  age: number | null
  height_cm: number | null
  weight_kg: number | null
  activity_level: string | null
  target_weight_kg: number | null
  target_calories: number
  target_protein: number | null
  target_carbs: number | null
  target_fat: number | null
  goal_type: string
  nutrition_goal_mode: string
  diet_style: string | null
  taste_preference: string | null
  avoid_foods: string | null
  allergens: string | null
  cuisines: string[] | null
  ai_recognition_mode: string
  ai_estimate_mode: string
  ai_low_confidence_confirm: boolean
  ai_show_components: boolean
  ai_show_summary: boolean
  ai_confirm_similar_dish: boolean
  breakfast_reminder_enabled: boolean
  breakfast_reminder_time: string | null
  lunch_reminder_enabled: boolean
  lunch_reminder_time: string | null
  dinner_reminder_enabled: boolean
  dinner_reminder_time: string | null
  daily_summary_enabled: boolean
  daily_summary_time: string | null
  weekly_report_enabled: boolean
  weekly_report_day: number | null
  weekly_report_time: string | null
  inactivity_reminder_enabled: boolean
  image_retention_policy: string
  allow_anonymous_ai_training: boolean
}

export type RecommendTargetsRequest = {
  gender: string
  age: number
  height_cm: number
  weight_kg: number
  activity_level: string
  goal_type: string
}

export type RecommendTargetsResponse = {
  calories: number
  protein: number
  carbs: number
  fat: number
  bmr: number
  tdee: number
  activity_factor: number
  goal_adjustment: number
  explanation: string
}

// --- API functions ---

export async function getUserSettings(): Promise<UserSettings> {
  return apiGet<UserSettings>('/api/users/me/settings')
}

export async function updateUserSettings(patch: Partial<UserSettings>): Promise<UserSettings> {
  return apiPatch<UserSettings>('/api/users/me/settings', patch)
}

export async function recommendTargets(body: RecommendTargetsRequest): Promise<RecommendTargetsResponse> {
  return apiPost<RecommendTargetsResponse>('/api/users/me/settings/recommend-targets', body)
}
