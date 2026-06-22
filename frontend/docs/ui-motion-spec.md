# UI Motion and Style Specification

This document defines a **gentle, dual‑user mobile web experience**.  It explains how to translate the calm and immersive feel of a native wellness app into a Progressive Web App (PWA) for both **users** and their **bound administrators**.  The guidelines build on the existing feature set described in the front‑end specification【turn0file0†L1-L20】 and preserve the core flows (login, sign‑in, conversation, records, rewards and admin pages).  Use these recommendations when designing layouts, interactions and animations so that the application feels cohesive, inviting and easy to use.

## 1. Global Style

### Colour and background

* **Dark gradient backgrounds:** Use a radial or diagonal gradient from a deep navy (e.g. `#0c1424`) to a slightly lighter tone (`#1d2c40`).  Subtle noise or blurred organic shapes can be overlaid to create depth without distraction.  This evokes the night‑sky feel from the reference app while keeping text legible.
* **Accent palette:**  Choose two gentle accent colours – one cool (soft cyan or mint) and one warm (lavender or blush).  Use the cool accent for primary actions (e.g. sign‑in, send) and the warm accent for success states and highlights.
* **Glass surfaces:** Cards, panels and bottom sheets should use semi‑transparent surfaces with a blur filter (glassmorphism).  A glass card might have a `rgba(255,255,255,0.1)` background and `backdrop-filter: blur(20px)`.  This allows the gradient background to remain visible while still giving content a clear container.
* **Safe area:** Apply `padding-top: env(safe-area-inset-top)` and `padding-bottom: env(safe-area-inset-bottom)` in the top‑level layout so that content never overlaps the iOS status bar or home indicator【turn0file0†L150-L160】.

### Typography

* Use a friendly, humanist sans‑serif typeface (e.g. Inter, Manrope or SF Pro) with large headings and generous line spacing.  Headings should be bold and easily scannable; body text should be medium weight for readability.
* Maintain high contrast between text and backgrounds.  On dark surfaces, text should be white or a very light grey; on glass cards, use a slightly tinted dark colour for secondary text.

### Buttons and interactive elements

* **Pill and round shapes:** Primary actions use pill‑shaped buttons (e.g. 44 px height, full width or sized to content).  Secondary actions can use circular or soft‑rectangle shapes.  All interactive surfaces must be at least 44 px high【turn0file0†L150-L160】.
* **Press feedback:** On touch down, scale elements to `0.96` and slightly change opacity (dark surfaces lighten; light surfaces darken).  On release, animate back to `1.0` with a spring (stiffness ≈500, damping ≈30).  This makes buttons feel tactile without being distracting.
* **States:** Define visual states for default, pressed, loading (spinner overlaid and reduced opacity), disabled (lower opacity and desaturated) and success (replace label with a checkmark or confetti burst).  Never leave the user wondering whether an action was registered.

### Animations and transitions

* **Motion durations:** Use short animations (150–250 ms) for tap feedback and medium durations (200–300 ms) for page transitions.  Longer micro‑interactions (400–600 ms) should be reserved for celebratory moments like confetti when a user successfully signs in or redeems a reward.
* **Easing:** Prefer a spring or cubic‑bezier ease‑out curve to give motions a natural feel.  Avoid linear or abrupt changes.
* **Shared element transitions:** When a card expands to a detail view (e.g. a record expanding into a full‑screen page), animate the position and size of the card using a shared `layoutId` so that the user perceives continuity.  Blur and dim the background simultaneously.
* **Bottom sheet behaviour:** Drawers and sheets should slide up from the bottom.  Provide two positions (half and full screen) and allow users to drag to dismiss.  Use a translucent dimming layer and blur behind the sheet.

## 2. Page‑specific Guidelines

The app contains several pages with distinct roles.  The general capabilities of each page are defined in the feature specification【turn0file0†L1-L20】.  The following describes how to present them with the gentle theme and appropriate motion.

### 2.1 Login Page

The login page handles account entry, password and a local CAPTCHA【turn0file0†L1-L20】.  It should provide a strong first impression while remaining simple.

* **Layout:** Centre the login panel vertically within the `MobileAppShell`.  Use a glass card for the panel itself with rounded corners.  Above the panel, display the app name or logo; below, show optional helper text (e.g. “Welcome back”).
* **Inputs:** Stack the account, password and CAPTCHA fields with 12 px gaps.  Each input uses the glass style with a subtle border.  Show the CAPTCHA image on the right side of the input with a refresh button.
* **Button:** Place the login button beneath the inputs.  It spans most of the card’s width and uses the cool accent colour.  Disable the button while login is in progress.
* **Validation:** When the user submits invalid credentials, shake the entire card (5–10 px horizontal oscillation) and show an error toast at the bottom of the screen【turn0file0†L150-L160】.

### 2.2 Mobile Home Page

This is the main entry for both users and bound administrators.  It must remain uncluttered.  The central area shows either the daily sign‑in or the current points balance, depending on the user’s role【turn0file0†L1-L20】.

* **Background:** Use the full gradient background with subtle animated particles (slowly moving blurred shapes).  A translucent overlay above the gradient helps set the stage for the central card.
* **Central card:** Use a large, glass card centred on the screen.  For users, display a friendly greeting (“Good evening, Alex”) and the sign‑in call‑to‑action.  The call‑to‑action uses a round button with an emoji (e.g. ✨) and the label “Sign in”.  When pressed, show a gentle pulse and, upon success, trigger a confetti burst.
* **Role context:** If the user is a bound administrator, the card instead shows the bound user’s points and a link to manage rewards.  Display the user’s avatar in the top left corner; tapping it opens the **User/Role** page.
* **Navigation bar:** Place a bottom tab bar with icons only.  Use 4–5 evenly spaced icons representing Home, Chat, Records, Rewards and Settings.  The active tab uses the accent colour and a small indicator dot.

### 2.3 User/Role Page

This screen presents identity information, allows switching between user and bound administrator views, and displays the points and rewards.  It is presented over the home background using a **GlassScreen**【turn0file0†L21-L34】.

* **Identity card:** At the top, show the current user’s avatar, name and role.  Below that, include a segmented control or toggle to switch between `USER` and `BOUND_ADMIN`.  If no bound user exists, visually disable the admin option.
* **Metrics:** Use `MetricLine` components to display the total points.  Numbers should be large and emphasised; units (e.g. “points”) appear underneath in a smaller size.
* **Rewards list:** Use a vertical list of glass reward cards.  Each card shows the reward name, an optional icon, a short description and the points required.  A small pill button indicates whether it can be redeemed.  When tapped, animate the card into a bottom sheet with full details and a “Redeem” button.  In the admin view, cards include edit/delete controls.
* **Role transition:** When the user switches roles, fade out the content, slide in the new role’s content from the right and show a toast (“Switched to admin view”).  Do not refresh the whole page, as the underlying avatar and heading remain the same.

### 2.4 Chat Page

The conversation page supports sending messages, reading AI drafts and confirming record creation【turn0file0†L1-L20】.

* **Header:** Use `ScreenHeader` with a back arrow and the title “Chat”.  Maintain equal padding on left and right so that the title remains centred【turn0file0†L35-L39】.
* **Chat history:** Implement `ChatHistory` as a scrollable column with reversed order (latest at the bottom).  User messages use a right‑aligned glass bubble with the cool accent border; AI/system messages use left‑aligned darker bubbles.  Each message fades in and slightly slides up when added.
* **Draft panel:** When the AI generates a draft, display a card anchored just above the composer.  It contains a title (e.g. “Draft ready”), a preview snippet, a rating indicator and two buttons: “Confirm” (in accent colour) and “Edit” (secondary style).  The panel uses a distinct colour (warm accent) to separate it from chat bubbles.  Confirming triggers a success toast and resets the chat; editing slides the card up into a full‑screen editor.
* **Composer:** The bottom composer stays anchored above the keyboard.  It includes a circular microphone button (for future voice input), a text input and a send button.  The microphone button animates in when tapped but remains disabled until voice input is supported.  The send button uses the accent colour and scales on tap.
* **Keyboard and safe area:** When the keyboard appears, translate the composer up by the keyboard height and shrink the chat history accordingly.  Ensure the bottom nav bar is hidden or overlaid.

### 2.5 User Recent Records Page

Users can view a list of their records, choose which fields are shown and read administrator comments.

* **Field selector:** Implement a horizontal list of pill toggles at the top of the list, letting the user choose which fields to display (e.g. date, content, rating).  At least one field must remain selected【turn0file0†L1-L20】.
* **Record list:** Each record appears as a glass card with the selected fields.  Long text wraps gracefully.  The rating can be represented by a small coloured badge or icon.  Administrator comments appear in a lighter area below the record details.
* **Empty state:** If there are no records, show a friendly illustration and the message “No records yet” using the warm accent.  Use the `EmptyState` component as a base.
* **Transitions:** Tapping a record expands it into a bottom sheet showing full content and any comments.  Use a shared element transition from the card to the sheet.

### 2.6 Admin Points & Rewards Page

Bound administrators manage rewards for their bound users【turn0file0†L1-L20】.

* **Points metric:** Display the user’s current points using a `MetricLine` with large type.  Pair it with a subtitle (e.g. “Total points”) and a subtle icon.
* **Add reward form:** Summon a bottom sheet when the admin taps “Add reward”.  The sheet contains two inputs (name and points required) using glass fields and a “Save” button.  Validate both fields; if invalid, shake the sheet and show inline error messages.
* **Rewards list:** Similar to the user’s rewards list but includes an indicator of whether the reward is redeemed, available or out of stock.  Admin controls (edit/delete) slide in from the right on long press.
* **Success feedback:** When a reward is added, trigger a confetti burst and a success toast.  When a reward is redeemed, animate the card sliding left and grey it out.

### 2.7 Admin Recent Records Page

This page allows administrators to read user records, add comments and assign scores【turn0file0†L1-L20】.

* **Record cards:** Each card includes the record’s date, content and current score.  Below, provide a comment input (multi‑line) and a numeric slider or input for the score (0–100).  Show validation errors inline if the comment is empty or the score is outside the range.
* **Save button:** A small pill button on each card triggers saving the comment and score.  While saving, disable the button and show a spinner.  On success, briefly highlight the card and scroll it out of view.

### 2.8 Ops Backend Page

The Ops page is a desktop‑only interface for administrators and should not follow the mobile styling【turn0file0†L150-L160】.  Use a separate layout with a fixed sidebar, dense tables and modals.  Colours should be neutral and functional.  This document focuses on the mobile app; design the Ops interface separately.

## 3. Interaction Details

The following guidelines apply across pages and components.

### Pressable component

All tappable elements (buttons, cards, list items) must use a **Pressable** abstraction that applies the tap animation described in section 1.  On tap start, set `scale=0.96` and adjust opacity; on release, return to normal.  Use Motion’s `whileTap` for implementation.

### Page transitions

Wrap route changes in an `AnimatePresence` component.  New pages slide in from the right or bottom (for modal sheets) while fading in, and old pages scale down to `0.98` and fade out.  Keep the duration around 220 ms.

### Bottom sheet behaviour

Use **Vaul Drawer** or a similar component to implement sheets.  Provide two detents: 70 % height (partial) and 100 % height (full).  Use a translucent dimming layer with `rgba(0,0,0,0.5)` and apply a blur to the page behind.  When the sheet appears, scale the underlying content down slightly (e.g. 0.98) so the sheet feels connected.  Dismissing the sheet reverses the animation.

### Success animations

Celebrate important actions (sign‑in, record saved, reward redeemed) with a burst of confetti.  Use a lightweight library (e.g. `canvas-confetti`) to create particles for 400–500 ms.  Combine this with a toast (“Signed in successfully!”) and a subtle vibration if supported (not available on all mobile browsers).  Keep confetti behind the navigation bar.

### Scroll and drag gestures

Lists should smoothly decelerate when scrolled.  Use `@use-gesture` or Motion’s built‑in drag handling for interactive drags (e.g. swiping a card to reveal admin actions).  Provide visual feedback for drag direction (e.g. colour change or icon appearing).  Never require complex gestures to perform core tasks【turn0file0†L150-L160】.

### Error handling

Always provide immediate feedback when something goes wrong (e.g. invalid input, network error).  Use the `Toast` component to show errors at the bottom of the screen with a clear message.  Inputs with errors should highlight their borders and display inline helper text.

## 4. Theme Variables and Tokens

To ensure consistency, define a set of design tokens and expose them via Tailwind’s configuration or CSS variables:

| Token | Purpose | Example |
|---|---|---|
| `--color-bg-start` | Start colour of the gradient background | `#0c1424` |
| `--color-bg-end` | End colour of the gradient background | `#1d2c40` |
| `--color-accent-cool` | Primary accent colour | `#4fc0d9` |
| `--color-accent-warm` | Secondary accent colour | `#b18ace` |
| `--color-surface` | Base colour for glass surfaces | `rgba(255,255,255,0.1)` |
| `--color-text-primary` | Main text colour | `#ffffff` |
| `--color-text-secondary` | Secondary text colour | `#d1d5db` |
| `--spacing-base` | Base spacing unit | `4px` |
| `--radius-large` | Border radius for cards | `24px` |

Use these tokens in your components so that the theme can be easily adjusted later.

## 5. Rationale and Alignment with Existing Specification

The gentle design proposed here aligns with the functional requirements in the existing front‑end specification.  It does **not** remove or change any core capabilities such as login, record creation, reward management or admin operations【turn0file0†L1-L20】.  Instead, it layers a cohesive visual style, clear motion guidelines and accessible interactions over those flows.  By abstracting common components like `MobileAppShell`, `GlassScreen`, `ScreenHeader` and `Toast`, designers and developers can optimise the user experience without impacting the underlying API contracts【turn0file0†L21-L34】.  Adhering to these guidelines will create a polished, calming application that feels at home on modern mobile devices while remaining fully functional for both users and administrators.