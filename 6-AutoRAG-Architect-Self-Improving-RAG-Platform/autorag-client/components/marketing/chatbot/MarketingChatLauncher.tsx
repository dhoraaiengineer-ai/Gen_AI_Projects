"use client";

import { AutoRagIcon } from "./AutoRagIcon";

interface MarketingChatLauncherProps {
  onClick: () => void;
}

export function MarketingChatLauncher({ onClick }: MarketingChatLauncherProps) {
  return (
    <button onClick={onClick} aria-label="Try AutoRAG marketing chat" className="fixed bottom-6 right-6 z-40 cursor-pointer">
      <AutoRagIcon size={56} showNotificationBadge showGreeting />
    </button>
  );
}
