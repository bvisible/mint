import { cn } from "@/lib/utils"

export const StatContainer = ({ children, className }: { children: React.ReactNode, className?: string }) => {
    return <div className={cn("flex flex-col gap-0.5 py-1 px-2", className)}>{children}</div>
}

export const StatLabel = ({ children, className }: { children: React.ReactNode, className?: string }) => {
    return <span className={cn("uppercase text-[11px] leading-tight font-medium text-secondary-foreground/80", className)}>{children}</span>
}

export const StatValue = ({ children, className }: { children: React.ReactNode, className?: string }) => {
    return <span className={cn("text-xl font-semibold tabular-nums", className)}>{children}</span>
}