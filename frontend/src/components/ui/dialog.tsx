"use client"

import * as React from "react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { XIcon } from "lucide-react"

import { cn } from "@/lib/utils"

function Dialog({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        //// Neoffice — z-50 raised to z-[1050] (e582a55): the dialog overlay rendered behind the
        //// Frappe desk chrome that wraps the embedded SPA.
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-[1050] bg-black/50",
        className
      )}
      {...props}
    />
  )
}

function DialogContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  //// Neoffice — added guard (89e7929). Radix marks everything outside its portal aria-hidden
  //// with pointer-events:none; that also killed the Nora Learn tutorial popup, which lives
  //// outside the React tree, so a user in a guided tour could not click anything once a modal
  //// was open. The interval strips those attributes back off the Learn nodes. No upstream
  //// equivalent: upstream ships no in-app tutorial.
  // Protect Nora Learn popup from being blocked by Radix hideOthers()
  // Radix sets aria-hidden + pointer-events:none on all elements outside the portal
  // We counter this by continuously stripping those attributes from Learn elements
  const noraGuardRef = React.useRef<ReturnType<typeof setInterval> | null>(null)
  React.useEffect(() => {
    noraGuardRef.current = setInterval(() => {
      document.querySelectorAll('.nora-lp, #nora-step-popover').forEach(el => {
        if (el.getAttribute('aria-hidden') === 'true') {
          el.removeAttribute('aria-hidden')
        }
        if ((el as HTMLElement).hasAttribute('inert')) {
          (el as HTMLElement).removeAttribute('inert')
        }
        ;(el as HTMLElement).style.setProperty('pointer-events', 'auto', 'important')
        ;(el as HTMLElement).style.setProperty('z-index', '2147483647', 'important')
        el.querySelectorAll('*').forEach(child => {
          ;(child as HTMLElement).style.setProperty('pointer-events', 'auto', 'important')
        })
      })
    }, 50)
    return () => {
      if (noraGuardRef.current) clearInterval(noraGuardRef.current)
    }
  }, [])

  return (
    <DialogPortal data-slot="dialog-portal">
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          //// Neoffice — same z-50 to z-[1050] bump (e582a55).
          "bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-[1050] grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg border p-6 shadow-lg duration-200 sm:max-w-lg max-h-[90vh] overflow-y-auto",
          className
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close className="ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4">
          <XIcon />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-2 text-center sm:text-left", className)}
      {...props}
    />
  )
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        //// Neoffice — footer made sticky (e582a55). Our modals are much taller (VAT preview, split
        //// lines), so with upstream's static footer the action buttons scrolled out of reach.
        // Sticky so action buttons stay visible when modal content overflows
        // vertically (DialogContent has max-h-[90vh] + overflow-y-auto).
        "sticky bottom-0 z-10 -mx-6 -mb-6 mt-2 flex flex-col-reverse gap-2 border-t bg-background px-6 pb-6 pt-3 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    />
  )
}

function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-lg leading-none font-semibold", className)}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
