"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MAX_CHARS = 4000;

export function Composer({
  onSubmit,
  onStop,
  running,
  autoFocus,
  className,
  placeholder = "Ask anything about your supply chain…",
}: {
  onSubmit: (text: string) => void;
  onStop?: () => void;
  running?: boolean;
  autoFocus?: boolean;
  className?: string;
  placeholder?: string;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);

  const send = () => {
    const text = value.trim();
    if (!text || running) return;
    onSubmit(text);
    setValue("");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className={cn(
        "relative flex items-end gap-2 rounded-xl border bg-card p-2 pl-4 shadow-card transition-[border-color,box-shadow] focus-within:border-ai/50 focus-within:shadow-[0_0_0_4px_color-mix(in_oklab,var(--ai)_10%,transparent)]",
        className,
      )}
    >
      <label htmlFor="copilot-input" className="sr-only">
        Ask the AI Copilot
      </label>
      <textarea
        id="copilot-input"
        ref={ref}
        rows={1}
        autoFocus={autoFocus}
        value={value}
        maxLength={MAX_CHARS}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
        className="max-h-44 min-h-9 flex-1 resize-none bg-transparent py-2 text-[14px] leading-relaxed outline-none placeholder:text-muted-foreground"
      />
      {running ? (
        <Button type="button" size="icon" variant="outline" onClick={onStop} aria-label="Stop generating">
          <Square className="!size-3 fill-current" />
        </Button>
      ) : (
        <Button type="submit" size="icon" variant="ai" disabled={!value.trim()} aria-label="Send">
          <ArrowUp />
        </Button>
      )}
    </form>
  );
}
