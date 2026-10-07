"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Boxes, Search, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Dialog as DialogPrimitive } from "radix-ui";
import { getApi } from "@/lib/api";
import { ALL_NAV_ITEMS } from "@/lib/navigation";
import { RiskBadge } from "@/components/shared/status";

const itemClass =
  "flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-[13px] outline-none data-[selected=true]:bg-accent [&_svg]:size-4 [&_svg]:text-muted-foreground";

/** Global ⌘K search: pages, SKUs, and "ask the Copilot". */
export function CommandSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const term = query.trim();
  const { data: skus } = useQuery({
    queryKey: ["search", "inventory", term],
    queryFn: async () => (await getApi()).getInventory({ search: term, pageSize: 6, sort: "risk" }),
    enabled: open && term.length >= 2,
    staleTime: 60_000,
  });

  const go = (href: string) => {
    setOpen(false);
    setQuery("");
    router.push(href);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex size-8 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground sm:hidden"
        aria-label="Search"
      >
        <Search className="size-4" aria-hidden />
      </button>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden h-9 w-full max-w-md cursor-pointer items-center gap-2 rounded-md border bg-muted/50 px-3 text-[13px] text-muted-foreground transition-colors hover:bg-muted sm:flex"
        aria-label="Search (Ctrl+K)"
      >
        <Search className="size-4" aria-hidden />
        <span className="flex-1 truncate text-left">Search SKUs, pages, or ask AI…</span>
        <kbd className="hidden rounded border bg-card px-1.5 font-mono text-[10px] sm:inline">Ctrl K</kbd>
      </button>
      <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#0a1930]/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
          <DialogPrimitive.Content className="fixed top-[15%] left-1/2 z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border bg-popover shadow-raised outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
            <DialogPrimitive.Title className="sr-only">Search</DialogPrimitive.Title>
            <Command shouldFilter={false} label="Global search">
              <div className="flex items-center gap-2 border-b px-4">
                <Search className="size-4 text-muted-foreground" aria-hidden />
                <Command.Input
                  value={query}
                  onValueChange={setQuery}
                  placeholder="Search SKUs, pages, or ask AI…"
                  className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>
              <Command.List className="max-h-[360px] overflow-y-auto p-2">
                <Command.Empty className="px-3 py-6 text-center text-[13px] text-muted-foreground">No matches. Press Enter to ask the Copilot.</Command.Empty>
                {term && (
                  <Command.Group heading="AI Copilot" className="mb-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
                    <Command.Item value={`ask-${term}`} onSelect={() => go(`/copilot?q=${encodeURIComponent(term)}`)} className={itemClass}>
                      <Sparkles className="!text-ai" /> Ask Copilot: <span className="truncate font-medium">“{term}”</span>
                    </Command.Item>
                  </Command.Group>
                )}
                {!!skus?.items.length && (
                  <Command.Group heading="Products" className="mb-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
                    {skus.items.map((i) => (
                      <Command.Item key={i.sku} value={i.sku} onSelect={() => go(`/inventory?search=${encodeURIComponent(i.sku)}`)} className={itemClass}>
                        <Boxes />
                        <span className="font-mono text-xs">{i.sku}</span>
                        <span className="flex-1 truncate">{i.name}</span>
                        <RiskBadge risk={i.risk} />
                      </Command.Item>
                    ))}
                  </Command.Group>
                )}
                <Command.Group heading="Pages" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
                  {ALL_NAV_ITEMS.filter((i) => !term || i.label.toLowerCase().includes(term.toLowerCase())).map((item) => (
                    <Command.Item key={item.href} value={item.href} onSelect={() => go(item.href)} className={itemClass}>
                      <item.icon />
                      <span>{item.label}</span>
                      <span className="ml-auto truncate text-xs text-muted-foreground">{item.description}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </>
  );
}
