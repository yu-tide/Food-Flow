"use client";

import { useEffect, useState } from "react";

export type UploadDraft = {
  file: File | null;
  previewUrl: string | null;
  fileName: string;
  fileSize: number;
  mimeType: string;
  source: "camera" | "file" | "unknown";
  selectedAt: number | null;
};

const EMPTY: UploadDraft = {
  file: null,
  previewUrl: null,
  fileName: "",
  fileSize: 0,
  mimeType: "",
  source: "unknown",
  selectedAt: null,
};

let draft: UploadDraft = { ...EMPTY };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((fn) => fn());
}

export function getDraft(): UploadDraft {
  return draft;
}

export function setDraft(file: File, source: UploadDraft["source"] = "unknown") {
  if (draft.previewUrl) {
    URL.revokeObjectURL(draft.previewUrl);
  }
  draft = {
    file,
    previewUrl: URL.createObjectURL(file),
    fileName: file.name,
    fileSize: file.size,
    mimeType: file.type,
    source,
    selectedAt: Date.now(),
  };
  emit();
}

export function clearDraft() {
  if (draft.previewUrl) {
    URL.revokeObjectURL(draft.previewUrl);
  }
  draft = { ...EMPTY };
  emit();
}

export function useUploadDraft() {
  const [snapshot, setSnapshot] = useState<UploadDraft>(getDraft);

  useEffect(() => {
    const cb = () => setSnapshot(getDraft());
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
    };
  }, []);

  return {
    draft: snapshot,
    setDraft,
    clearDraft,
    hasDraft: snapshot.file !== null,
  } as const;
}
