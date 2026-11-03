"use client"

import { CheckCircle2, AlertTriangle, XCircle, Info } from "lucide-react"

import { useToast } from "@/hooks/use-toast"
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast"

const VARIANT_ICON = {
  default: Info,
  success: CheckCircle2,
  destructive: XCircle,
  warning: AlertTriangle,
} as const

const VARIANT_ICON_CLASS = {
  default: "text-blue-400",
  success: "text-emerald-400",
  destructive: "text-rose-400",
  warning: "text-amber-400",
} as const

export function Toaster() {
  const { toasts } = useToast()

  return (
    <ToastProvider swipeDirection="right">
      {toasts.map(({ id, title, description, action, variant = "default", ...props }) => {
        const Icon = VARIANT_ICON[variant as keyof typeof VARIANT_ICON] ?? Info
        return (
          <Toast key={id} variant={variant} {...props}>
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${VARIANT_ICON_CLASS[variant as keyof typeof VARIANT_ICON_CLASS]}`} aria-hidden="true" />
            <div className="flex-1 min-w-0">
              {title && <ToastTitle>{title}</ToastTitle>}
              {description && <ToastDescription>{description}</ToastDescription>}
            </div>
            {action}
            <ToastClose />
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
