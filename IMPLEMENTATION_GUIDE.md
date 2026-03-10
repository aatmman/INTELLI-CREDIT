# Intelli-Credit UI Redesign — Implementation Guide

## Design System: Precision Monochrome

### Aesthetic Direction
**Pure black & white editorial banking** — think Bloomberg Terminal meets Stripe Dashboard meets a luxury financial annual report.

No color noise. Every element earns its place.

---

## Files Delivered

| File | Replaces | Notes |
|------|----------|-------|
| `index.css` | `index.css` | Full design system — typography, tokens, components |
| `DashboardLayout.tsx` | `components/DashboardLayout.tsx` | Complete nav/layout rewrite |
| `LoginPage.tsx` | `pages/LoginPage.tsx` | Ticker bar + editorial split panel |
| `BorrowerDashboard.tsx` | `pages/BorrowerDashboard.tsx` | Clean stats + progress track |
| `RMDashboard.tsx` | `pages/RMDashboard.tsx` | Mono data table + pipeline |
| `AnalysisWorkspace.tsx` | `pages/AnalysisWorkspace.tsx` | 6-tab workspace, all charts in mono palette |
| `FieldVisitForm.tsx` | `pages/FieldVisitForm.tsx` | Surgical form design |
| `PreQualForm.tsx` | `pages/PreQualForm.tsx` | Clean input system |
| `CreditManagerDecision.tsx` | `pages/CreditManagerDecision.tsx` | SHAP bars + policy checklist |
| `SanctioningDecision.tsx` | `pages/SanctioningDecision.tsx` | Final authority decision pack |

---

## Step 1: Install Fonts

In your `index.html` or `_document.tsx`, add:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
```

---

## Step 2: Replace Files

Copy each file to its correct location:

```
src/
├── index.css                          ← replace
├── pages/
│   ├── LoginPage.tsx                  ← replace
│   ├── BorrowerDashboard.tsx          ← replace
│   ├── RMDashboard.tsx                ← replace
│   ├── AnalysisWorkspace.tsx          ← replace
│   ├── FieldVisitForm.tsx             ← replace
│   ├── PreQualForm.tsx                ← replace
│   ├── CreditManagerDecision.tsx      ← replace
│   └── SanctioningDecision.tsx        ← replace
└── components/
    └── DashboardLayout.tsx            ← replace
```

---

## Step 3: Update StatusBadge Component

Your `StatusBadge` component needs to map to the new mono badge classes. Update it like this:

```tsx
// components/StatusBadge.tsx
interface Props {
  variant: "success" | "warning" | "danger" | "info" | "neutral" | "dark";
  children: React.ReactNode;
  dot?: boolean;
}

export function StatusBadge({ variant, children, dot }: Props) {
  const cls = {
    success: "badge-success",
    warning: "badge-warning",
    danger: "badge-danger",
    info: "badge-info",
    neutral: "badge-neutral",
    dark: "badge-dark",
  }[variant] || "badge-neutral";

  return (
    <span className={cls}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5 inline-block" />}
      {children}
    </span>
  );
}
```

---

## Step 4: Update StatCard Component

```tsx
// components/StatCard.tsx
interface Props {
  label: string;
  value: string;
  subtitle?: React.ReactNode;
  className?: string;
}

export function StatCard({ label, value, subtitle, className }: Props) {
  return (
    <div className={`stat-card ${className || ""}`}>
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {subtitle && <div className="mt-1.5">{subtitle}</div>}
    </div>
  );
}
```

---

## Design Tokens Reference

```css
/* Typography */
font-family: 'Syne' (headings, UI)
font-family: 'JetBrains Mono' (labels, codes, badges, numbers)

/* Spacing */
--nav-height: 60px

/* Key Classes */
.font-display     → Syne 800 -0.04em
.font-mono        → JetBrains Mono
.section-label    → 10px mono uppercase tracking-[0.15em] muted
.stat-label       → 10px mono uppercase tracking-[0.15em] muted
.stat-value       → 32px Syne 800 -0.04em

/* Cards */
.glass-card       → white card, rounded-sm, border, p-5
.card-ink         → inverted black card (for emphasis)

/* Badges (all mono font, all uppercase) */
.badge-danger     → BLACK fill (highest severity)
.badge-warning    → muted border (medium)
.badge-success    → subtle bg (positive)
.badge-neutral    → muted bg (default)
.badge-dark       → black fill (same as danger but for labels)
.badge-info       → outline only

/* Buttons */
.btn-primary      → black fill, white text
.btn-ghost        → transparent, border, hover muted

/* Input */
.ic-input         → h-11 border focus:ring-1 focus:ring-foreground

/* Layout */
.top-nav          → sticky, blur, border-b
.tab-bar          → flex border-b
.tab-item         → px-5 py-3 border-b-2 (active = border-foreground)

/* Timeline */
.timeline-line    → vertical 1px line
.timeline-dot-high → filled black circle
.timeline-dot-med  → outlined circle

/* Charts */
All chart colors use hsl(0 0% ...) only:
- Primary bars: hsl(0 0% 4%) = ink black  
- Secondary: hsl(0 0% 60%) = medium gray
- Tertiary: hsl(0 0% 80%) = light gray
```

---

## What Changed vs Original

| Before | After |
|--------|-------|
| Indigo/blue accent color | Pure black & white only |
| Rounded-xl cards with shadows | Sharp rounded-sm, minimal borders |
| Space Grotesk + DM Sans | Syne (display) + JetBrains Mono (data) |
| Colored badge system | Monochrome intensity-based badges |
| Generic button styles | btn-primary (black) / btn-ghost (outline) |
| Light blue sidebar variant | Deep black sidebar |
| Colored progress bars (indigo) | Single-color progress (foreground) |
| Chart colors (primary/accent/success) | Monochrome ink/gray scale |
| Emoji icons in condition buttons | Typographic symbols |
| Generic input fields | Sharp ic-input with focus ring |
| Scattered page headers | Consistent section-label + font-display H1 pattern |
| No ticker/live feed | Black ticker bar on login (editorial) |
| No background texture | Subtle grid overlay on login panel |

---

## Hackathon Demo Tips

1. **Login page ticker** creates instant "live system" impression on judges
2. **Mono palette** looks significantly more "enterprise/production" than colorful dashboards
3. **JetBrains Mono** for numbers/codes reads as technical precision
4. **SHAP waterfall bars** in solid black vs. muted grey shows clear positive/negative distinction
5. **Risk Timeline** with filled/outlined dots instantly conveys severity without color
