"use client";

import { useState } from "react";
import { useDraggableAssistant } from "@/hooks/useDraggableAssistant";
import { useAssistantContext } from "@/hooks/useAssistantContext";
import { AssistantButton } from "./AssistantButton";
import { AssistantPanel } from "./AssistantPanel";

export function FloatingAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const { position, dragging, movedRef, onPointerDown } = useDraggableAssistant();
  const { page, buildPageContext, isLoginPage, quickQuestions } = useAssistantContext();

  if (isLoginPage) return null;

  const handleClick = () => {
    if (!movedRef.current) {
      setIsOpen(true);
    }
    movedRef.current = false;
  };

  return (
    <>
      {/* Floating button */}
      <div
        className="fixed z-50 transition-all duration-200"
        style={{ left: position.x, top: position.y }}
      >
        <AssistantButton
          onPointerDown={onPointerDown}
          onClick={handleClick}
          dragging={dragging}
          isOpen={isOpen}
        />
      </div>

      {/* Chat panel */}
      {isOpen && (
        <div className="fixed bottom-4 right-4 z-50 w-[380px] max-w-[calc(100vw-2rem)] md:w-[400px]">
          <AssistantPanel
            page={page}
            buildPageContext={buildPageContext}
            quickQuestions={quickQuestions}
            onClose={() => setIsOpen(false)}
          />
        </div>
      )}
    </>
  );
}
