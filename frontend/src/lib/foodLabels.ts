/** 统一 food_items 来源标签展示 */

export type FoodItemLabelInfo = {
  source: string
  estimated?: boolean | null
  confidence?: number | null
}

const SOURCE_MAP: Record<string, string> = {
  vision: "视觉识别",
  "vision+rag": "视觉识别 + 营养检索",
  ocr: "OCR识别",
  fusion: "融合识别",
  rag: "营养检索",
  ai_estimate: "AI估算",
  fallback: "估算兜底",
  manual: "用户确认",
}

export function sourceLabel(source: string): string {
  return SOURCE_MAP[source] || "来源未知"
}

export function estimatedLabel(estimated?: boolean | null): string | null {
  if (estimated === true) return "估算"
  return null
}

export function confidencePercent(confidence?: number | null): string | null {
  if (confidence == null || confidence <= 0) return null
  return `${Math.round(confidence * 100)}%`
}

export function formatFoodItemLabels(item: FoodItemLabelInfo): string {
  const parts: string[] = []
  parts.push(sourceLabel(item.source))
  const est = estimatedLabel(item.estimated)
  if (est) parts.push(est)
  const pct = confidencePercent(item.confidence)
  if (pct) parts.push(pct)
  return parts.join(" · ")
}
