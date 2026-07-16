# 009 — DESIGN SYSTEM

*Visual design tokens, components, and patterns.*
*AI agents must use these tokens for all UI generation.*

---

## Color Palette

| Token | Hex | Usage |
|---|---|---|
| --primary | #1A73E8 | Primary buttons, links, active states |
| --primary-dark | #1557B0 | Primary hover, pressed |
| --secondary | #34A853 | Success, confirmed, available |
| --danger | #EA4335 | Error, delete, critical alerts |
| --warning | #FBBC04 | Warning, pending, attention |
| --info | #4285F4 | Information, neutral updates |
| --bg-primary | #FFFFFF | Main background |
| --bg-secondary | #F8F9FA | Card backgrounds, hover areas |
| --bg-tertiary | #E8EAED | Disabled, inactive |
| --text-primary | #202124 | Main text |
| --text-secondary | #5F6368 | Secondary text, labels |
| --text-disabled | #9AA0A6 | Disabled text |
| --border | #DADCE0 | Borders, dividers |
| --shadow | rgba(0,0,0,0.1) | Card shadows, dropdowns |

## Typography

| Token | Size | Weight | Usage |
|---|---|---|---|
| --font-xs | 12px | 400 | Small labels, timestamps |
| --font-sm | 14px | 400 | Body text, descriptions |
| --font-md | 16px | 500 | Card titles, buttons |
| --font-lg | 20px | 600 | Section headers |
| --font-xl | 24px | 700 | Page titles |
| --font-2xl | 32px | 700 | Display headlines |
| --font-family | Inter, system-ui, sans-serif | All text |
| --font-mono | JetBrains Mono, monospace | Code, tokens |

## Spacing

| Token | Value | Usage |
|---|---|---|
| --space-xs | 4px | Tight spacing, compact |
| --space-sm | 8px | Between related elements |
| --space-md | 16px | Default spacing |
| --space-lg | 24px | Section spacing |
| --space-xl | 32px | Page margins |
| --space-2xl | 48px | Large section gaps |

## Border Radius

| Token | Value | Usage |
|---|---|---|
| --radius-sm | 4px | Small badges, tags |
| --radius-md | 8px | Cards, inputs, buttons |
| --radius-lg | 12px | Modals, dialogs |
| --radius-full | 9999px | Pills, avatars |

## Shadows

| Token | Value | Usage |
|---|---|---|
| --shadow-sm | 0 1px 2px rgba(0,0,0,0.1) | Cards |
| --shadow-md | 0 4px 6px rgba(0,0,0,0.1) | Dropdowns, modals |
| --shadow-lg | 0 10px 15px rgba(0,0,0,0.15) | Sidebars, drawers |

## Reusable Components

### Buttons
- Primary: bg=--primary, text=white, radius=--radius-md, padding=12px 24px
- Secondary: bg=transparent, border=--border, text=--text-primary
- Danger: bg=--danger, text=white
- Ghost: no bg, text=--primary, hover bg=--bg-secondary
- Icon: 40x40 square, centered icon

### Cards
- bg=--bg-primary, border=1px solid --border, radius=--radius-md, shadow=--shadow-sm
- Padding: 16px (--space-md)
- Hover: shadow=--shadow-md, translateY=-2px

### Form Inputs
- height: 44px (touch-friendly)
- border: 1px solid --border, radius=--radius-md
- Focus: border-color=--primary, ring=2px rgba(26,115,232,0.2)
- Error: border-color=--danger, ring=2px rgba(234,67,53,0.2)
- Label: font-size=14px, weight=500, margin-bottom=4px

### Modals / Dialogs
- Overlay: bg=rgba(0,0,0,0.5)
- Container: bg=white, radius=--radius-lg, shadow=--shadow-lg
- Max width: 480px (mobile), 640px (desktop)
- Close button: top-right corner

### Tables
- Header: bg=--bg-secondary, font-weight=600
- Row hover: bg=--bg-secondary
- Border: 1px solid --border
- Padding: 12px 16px
- Responsive: horizontal scroll on mobile

### Status Badges
- radius=--radius-full, padding=4px 12px, font-size=12px
- Waiting: bg=#FFF8E1, text=#F57F17
- Called: bg=#E3F2FD, text=#1565C0
- Completed: bg=#E8F5E9, text=#2E7D32
- Skipped: bg=#FBE9E7, text=#D84315
- Critical: bg=#FFEBEE, text=#C62828

### Loading States
- Skeleton: bg=linear-gradient(90deg, --bg-secondary 25%, --bg-tertiary 50%, --bg-secondary 75%)
- Spinner: 20px, border=3px solid --border, border-top=3px solid --primary
- Full-page loader: centered spinner + text

### Toast / Snackbar
- Position: bottom-right (desktop), bottom-center (mobile)
- Duration: auto-dismiss after 4 seconds
- Types: success (--secondary), error (--danger), info (--info), warning (--warning)
- Action button: text link, right-aligned
