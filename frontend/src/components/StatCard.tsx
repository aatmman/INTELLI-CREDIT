import { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | ReactNode;
  subtitle?: string | ReactNode;
  className?: string;
}

export function StatCard({ label, value, subtitle, className = "" }: StatCardProps) {
  return (
    <div className={`stat-card ${className}`}>
      <p className="stat-label">{label}</p>
      <div className="stat-value">{value}</div>
      {subtitle && <div className="mt-1.5 text-xs text-muted-foreground">{subtitle}</div>}
    </div>
  );
}
