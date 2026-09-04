import { cn } from "@/lib/utils"

export const StatContainer = ({ children, className }: { children: React.ReactNode, className?: string }) => {
    ////// Neoffice — padding tightened, p-2 to py-1 px-2 (1f2847e). The balance strip sits under
    ////// the desk navbar in the embedded shell, where upstream's spacing pushed the figures below
    ////// the fold on a laptop screen. Purely visual.
    return <div className={cn("flex flex-col gap-0.5 py-1 px-2", className)}>{children}</div>
}

export const StatLabel = ({ children, className }: { children: React.ReactNode, className?: string }) => {
    ////// Neoffice — text-xs to text-[11px] + leading-tight (1f2847e), same density pass.
    return <span className={cn("uppercase text-[11px] leading-tight font-medium text-secondary-foreground/80", className)}>{children}</span>
}

export const StatValue = ({ children, className }: { children: React.ReactNode, className?: string }) => {
    ////// Neoffice — text-2xl to text-xl (1f2847e), same density pass.
    return <span className={cn("text-xl font-semibold tabular-nums", className)}>{children}</span>
}