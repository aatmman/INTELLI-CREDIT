import { cn } from "@/lib/utils";

type BadgeVariant = "success" | "warning" | "danger" | "info" | "neutral" | "dark";

interface StatusBadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: "badge-success",
  warning: "badge-warning",
  danger: "badge-danger",
  info: "badge-info",
  neutral: "badge-neutral",
  dark: "badge-dark",
};

export function StatusBadge({ variant, children, className, dot }: StatusBadgeProps) {
  return (
    <span className={cn(variantClasses[variant], className)}>
      {dot && (
        <span
          className={cn("w-1.5 h-1.5 rounded-full mr-1.5 inline-block", {
            "bg-[hsl(var(--success))]": variant === "success",
            "bg-[hsl(var(--warning))]": variant === "warning",
            "bg-[hsl(var(--destructive))]": variant === "danger",
            "bg-[hsl(var(--info))]": variant === "info",
          })}
        />
      )}
      {children}
    </span>
  );
}
