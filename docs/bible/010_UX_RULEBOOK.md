# 010 — UX RULEBOOK

*User experience principles and interaction rules.*
*AI agents must follow these rules for all UI generation.*

---

## Core Principles

1. **Mobile-First** — Every screen designed for 375px width first
2. **Three-Click Rule** — Patient data never more than 3 taps away
3. **One-Hand Operation** — All primary actions in thumb zone (bottom 60% of screen)
4. **Minimize Typing** — Prefer selection, search, scan over text input
5. **Never Ask Same Data Twice** — Auto-fill from patient record
6. **Immediate Feedback** — Every action shows result within 200ms or show loader
7. **Error Prevention** — Confirm destructive actions, validate before submit
8. **Offline Graceful** — Show cached data when offline, queue actions for retry

## Navigation Patterns

- **Bottom Tab Bar** (mobile): 4-5 primary sections
- **Sidebar** (desktop): collapsible, shows user role + active section
- **Breadcrumb**: Show current location for multi-step flows
- **Back Button**: Always accessible (hardware back on Android)
- **Search**: Always available at top, search by name/phone/token/ID

## Queue Screen UX Rules

- Current token displayed as large number (60px+) — visible from across room
- Next 3 tokens shown below with estimated time
- Call button = primary action (large, green, 56px height)
- Skip/Complete = secondary actions (ghost buttons)
- Sound + vibration on new token call
- Auto-refresh every 5 seconds (or WebSocket push)
- Waiting patients shown as list with token, name, wait time, status badge

## Doctor Screen UX Rules

- Patient list sorted by token number
- Each patient card shows: token, name, age, gender, complaint, wait time
- Tap patient -> opens consultation view (not a new page)
- Consultation view: vitals top, complaints, examination, prescription, lab orders
- Submit/Complete button bottom-right (thumb zone)
- Typing minimized: use templates, presets, auto-suggest

## Registration UX Rules

- Single screen, not multi-step wizard
- Auto-detect duplicate by phone number as user types
- Show matching patients below the phone input
- Required fields: name, phone. Everything else optional.
- QR code scan for quick registration (returning patients)
- Register button always visible and accessible

## Billing UX Rules

- Items list with checkboxes (select billable items)
- Total auto-calculated with GST
- Payment methods as large icon buttons (Cash, Card, UPI, Insurance)
- Split payment allowed (tap multiple payment methods)
- Receipt as printable view, not just PDF download
- Outstanding balance shown in red if any

## Patient Portal UX Rules

- View-only: token status, reports, bills, appointments
- Large readable text (16px minimum)
- High contrast for elderly patients
- Hindi/English toggle (language selector)
- Call clinic button (tap to call)
- Share report as WhatsApp message (native share sheet)

## Accessibility Requirements

- All interactive elements: min 44x44px touch target
- Color contrast: 4.5:1 for normal text, 3:1 for large text
- Focus indicators visible on all interactive elements
- Error messages: text + icon (not color alone)
- Loading states: skeleton + text (not just spinner)
- Screen reader labels on all icons
