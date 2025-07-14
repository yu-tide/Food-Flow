"use client";

import { Sparkles } from "lucide-react";

export function AssistantButton({
  onPointerDown,
  onClick,
  dragging,
  isOpen,
}: {
  onPointerDown: (e: React.PointerEvent) => void;
  onClick: () => void;
  dragging: boolean;
  isOpen: boolean;
}) {
  return (
    <button
      type="button"
      onPointerDown={onPointerDown}
      onClick={(e) => {
        if (dragging) return;
        onClick();
      }}
      className={`grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-[0_8px_30px_rgba(34,197,94,0.35)] transition-all hover:shadow-[0_12px_36px_rgba(34,197,94,0.45)] hover:scale-105 active:scale-95 ${
        dragging ? "cursor-grabbing scale-110" : "cursor-grab"
      } ${isOpen ? "scale-0 opacity-0 pointer-events-none" : ""}`}
      aria-label="FoodFlow AI 助手"
    >
      <Sparkles className="h-6 w-6" />
    </button>
  );
}
