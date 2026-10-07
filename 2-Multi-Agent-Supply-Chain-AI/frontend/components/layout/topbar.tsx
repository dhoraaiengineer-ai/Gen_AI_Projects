"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { BookOpen, ChevronRight, CircleHelp, Keyboard, LifeBuoy, LogOut, Menu, Moon, Settings, Sun, User } from "lucide-react";
import { navItemFor, sectionFor } from "@/lib/navigation";
import { DATA_SOURCE, ENVIRONMENT_LABEL } from "@/lib/constants";
import { useCurrentUser } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, Tooltip } from "@/components/ui/primitives";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/overlays";
import { CommandSearch } from "./command-search";
import { NotificationsMenu } from "./notifications";

function Breadcrumb() {
  const pathname = usePathname();
  const item = navItemFor(pathname);
  const section = sectionFor(pathname);
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex items-center gap-1.5 text-[13px]">
        {section && (
          <>
            <li className="hidden text-muted-foreground sm:block">{section}</li>
            <li className="hidden text-muted-foreground/60 sm:block" aria-hidden>
              <ChevronRight className="size-3.5" />
            </li>
          </>
        )}
        <li className="truncate font-semibold" aria-current="page">
          {item?.label ?? "SupplyAI"}
        </li>
      </ol>
    </nav>
  );
}

function EnvironmentBadge() {
  const demo = DATA_SOURCE === "mock";
  return (
    <Tooltip content={demo ? "Demo mode — realistic generated data. Set NEXT_PUBLIC_DATA_SOURCE=api for live data." : "Connected to the live backend"}>
      <span
        className="hidden h-7 items-center gap-1.5 rounded-md border bg-card px-2 text-xs font-medium md:inline-flex"
        aria-label={`Environment: ${ENVIRONMENT_LABEL}`}
      >
        <span className={demo ? "size-1.5 rounded-full bg-ai" : "size-1.5 rounded-full bg-success"} aria-hidden />
        {ENVIRONMENT_LABEL}
      </span>
    </Tooltip>
  );
}

export function Topbar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const { data: user } = useCurrentUser();
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-md sm:px-6">
      <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={onOpenMobileNav} aria-label="Open navigation">
        <Menu />
      </Button>
      <div className="min-w-0 flex-1 sm:w-56 sm:flex-none">
        <Breadcrumb />
      </div>
      <div className="flex justify-end sm:flex-1 sm:justify-center">
        <CommandSearch />
      </div>
      <div className="flex shrink-0 items-center gap-0.5 sm:gap-1">
        <EnvironmentBadge />
        <NotificationsMenu />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="Help">
              <CircleHelp />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Help</DropdownMenuLabel>
            <DropdownMenuItem asChild>
              <Link href="/copilot">
                <BookOpen /> What can the Copilot do?
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Keyboard /> Search: Ctrl + K
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings">
                <LifeBuoy /> System status
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="ml-1 cursor-pointer rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Account menu">
              <Avatar>
                <AvatarFallback className="bg-primary text-primary-foreground">{user?.initials ?? "··"}</AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <div className="px-2 py-2">
              <p className="truncate text-[13px] font-semibold">{user?.name}</p>
              <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
              <span className="mt-1.5 inline-flex rounded bg-secondary px-1.5 py-0.5 text-[11px] font-medium capitalize">{user?.role}</span>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings">
                <User /> Profile
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings">
                <Settings /> Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
              {resolvedTheme === "dark" ? <Sun /> : <Moon />} {resolvedTheme === "dark" ? "Light mode" : "Dark mode"}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={DATA_SOURCE === "mock"}>
              <LogOut /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
