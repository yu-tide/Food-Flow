"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

type DatePopoverProps = { selected: Date; onSelect: (date: Date) => void; onClose: () => void };

export default function DatePopover({ selected, onSelect, onClose }: DatePopoverProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [viewYear, setViewYear] = useState(selected.getFullYear());
  const [viewMonth, setViewMonth] = useState(selected.getMonth());

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(viewYear - 1); setViewMonth(11); }
    else setViewMonth(viewMonth - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(viewYear + 1); setViewMonth(0); }
    else setViewMonth(viewMonth + 1);
  };

  const today = new Date();
  const isToday = (d: Date) => d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate();
  const isSel = (d: Date) => d.getFullYear() === selected.getFullYear() && d.getMonth() === selected.getMonth() && d.getDate() === selected.getDate();

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDay = new Date(viewYear, viewMonth, 1).getDay() || 7;
  const days: (Date | null)[] = [];
  for (let i = 1; i < firstDay; i++) days.push(null);
  for (let d = 1; d <= daysInMonth; d++) days.push(new Date(viewYear, viewMonth, d));

  return (
    <div ref={ref} className="absolute right-0 top-full z-50 mt-2 w-[288px] rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_18px_45px_rgba(15,23,42,0.14)]">
      <div className="mb-3 flex items-center justify-between">
        <button onClick={prevMonth} className="grid h-8 w-8 place-items-center rounded-full hover:bg-slate-100"><ChevronLeft className="h-4 w-4 text-slate-500" /></button>
        <span className="text-sm font-bold text-slate-700">{viewYear}年{viewMonth + 1}月</span>
        <button onClick={nextMonth} className="grid h-8 w-8 place-items-center rounded-full hover:bg-slate-100"><ChevronRight className="h-4 w-4 text-slate-500" /></button>
      </div>
      <div className="mb-1 grid grid-cols-7 text-center text-[11px] font-bold text-slate-400">{WEEKDAYS.map(d => <span key={d}>{d}</span>)}</div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d, i) => (
          <button key={i} disabled={!d} onClick={() => { if (d) { onSelect(d); onClose(); } }}
            className={`grid h-9 w-9 place-items-center rounded-lg text-[13px] font-bold transition ${
              !d ? "" : isSel(d) ? "bg-green-600 text-white" : isToday(d) ? "bg-green-50 text-green-700 ring-1 ring-green-300" : "text-slate-700 hover:bg-green-50"
            }`}
          >{d ? d.getDate() : ""}</button>
        ))}
      </div>
      <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3">
        <button onClick={() => { onSelect(new Date()); onClose(); }} className="flex-1 rounded-lg bg-green-50 py-2 text-[13px] font-bold text-green-700 hover:bg-green-100">今天</button>
        <button onClick={onClose} className="flex-1 rounded-lg bg-slate-50 py-2 text-[13px] font-bold text-slate-500 hover:bg-slate-100">关闭</button>
      </div>
    </div>
  );
}
