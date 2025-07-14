"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "foodflow_assistant_position";

type Position = { x: number; y: number };

function loadPosition(): Position | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as Position;
  } catch { /* ignore */ }
  return null;
}

function savePosition(pos: Position) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pos));
  } catch { /* ignore */ }
}

export function useDraggableAssistant() {
  const [position, setPosition] = useState<Position>(() => {
    if (typeof window === "undefined") return { x: 0, y: 0 };
    const saved = loadPosition();
    if (saved) return saved;
    return { x: window.innerWidth - 72, y: window.innerHeight - 72 };
  });

  // Recalculate position on first client render
  useEffect(() => {
    if (position.x === 0 && position.y === 0) {
      const saved = loadPosition();
      setPosition(saved ?? { x: window.innerWidth - 72, y: window.innerHeight - 72 });
    }
  }, []);

  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; posX: number; posY: number } | null>(null);
  const movedRef = useRef(false);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startY: e.clientY, posX: position.x, posY: position.y };
    setDragging(true);
    movedRef.current = false;
  }, [position]);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: PointerEvent) => {
      if (!dragRef.current) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) movedRef.current = true;
      setPosition({
        x: Math.max(0, Math.min(window.innerWidth - 56, dragRef.current.posX + dx)),
        y: Math.max(0, Math.min(window.innerHeight - 56, dragRef.current.posY + dy)),
      });
    };
    const onUp = () => {
      setDragging(false);
      dragRef.current = null;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [dragging]);

  useEffect(() => {
    if (!dragging && movedRef.current) {
      savePosition(position);
    }
  }, [dragging, position]);

  return { position, dragging, movedRef, onPointerDown };
}
