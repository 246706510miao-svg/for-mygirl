# Implementation Plan for Gentle Dual‑User Mobile Web App

This document outlines the concrete steps and technical choices required to implement the UI described in the **UI Motion and Style Specification**.  It is intended for a developer using **React**, **Vite**, **TypeScript** and **Tailwind CSS**.  Animations are powered by **Motion for React**, modal drawers are implemented with **Vaul**, and icons come from **lucide‑react**.  Follow these instructions to build a production‑ready mobile web application while preserving the behaviour defined in the existing feature specification【turn0file0†L1-L20】.

## 1. Project Setup

1. **Create a Vite React project** with TypeScript:

   ```bash
   npm create vite@latest your‑app -- --template react-ts
   cd your‑app
   npm install
   ```

2. **Install dependencies** for styling and interaction:

   ```bash
   # Tailwind for styling
   npm install -D tailwindcss postcss autoprefixer
   npx tailwindcss init -p

   # Motion for animations
   npm install motion

   # Vaul Drawer
   npm install @radix-ui/react-dialog vaul

   # Radix primitives (Toast, Slider, etc.)
   npm install @radix-ui/react-toast @radix-ui/react-slider

   # Icon library
   npm install lucide-react

   # Confetti (optional)
   npm install canvas-confetti

   # Gesture handling (optional)
   npm install @use-gesture/react
   ```

3. **Configure Tailwind** in `tailwind.config.js`:

   - Enable JIT mode and add paths to all source files.
   - Extend the theme with the tokens defined in the style spec.  Example:

     ```js
     module.exports = {
       content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
       theme: {
         extend: {
           colors: {
             "bg-start": "var(--color-bg-start)",
             "bg-end": "var(--color-bg-end)",
             accent: {
               cool: "var(--color-accent-cool)",
               warm: "var(--color-accent-warm)",
             },
             surface: "var(--color-surface)",
             text: {
               primary: "var(--color-text-primary)",
               secondary: "var(--color-text-secondary)",
             },
           },
           borderRadius: {
             card: "var(--radius-large)",
           },
         },
       },
       plugins: [],
     }
     ```

4. **Add a global CSS file** (`src/styles.css`) to define the CSS variables from the spec:

   ```css
   :root {
     --color-bg-start: #0c1424;
     --color-bg-end:   #1d2c40;
     --color-accent-cool: #4fc0d9;
     --color-accent-warm: #b18ace;
     --color-surface: rgba(255, 255, 255, 0.1);
     --color-text-primary: #ffffff;
     --color-text-secondary: #d1d5db;
     --radius-large: 24px;
   }

   body {
     font-family: "Inter", sans-serif;
     background: linear-gradient(135deg, var(--color-bg-start), var(--color-bg-end));
     color: var(--color-text-primary);
   }

   /* Optional noise texture overlay */
   .noise-overlay {
     pointer-events: none;
     background-image: url("/noise.png");
     opacity: 0.05;
     mix-blend-mode: overlay;
   }
   ```

5. **Set up PWA capabilities** by adding a `manifest.webmanifest` and linking it in `index.html`.  Include `apple-mobile-web-app-capable` and `apple-mobile-web-app-status-bar-style` meta tags to run the app as a standalone iOS application【turn0file0†L150-L160】.  Use `100dvh` in your layouts to account for mobile browser UI.

## 2. Core Components

Implement reusable UI primitives first.  Place them in `src/components/ui` or similar.

### 2.1 MobileAppShell

* **File:** `src/components/layout/MobileAppShell.tsx`
* **Purpose:** Top‑level wrapper for all mobile pages.  It constrains the maximum width (~500 px), applies the gradient background, noise overlay and safe‑area padding, and hosts the bottom navigation bar.
* **Implementation details:**
  - Use a `<div>` with `className="relative w-full min-h-[100dvh] max-w-[500px] mx-auto px-4"`.
  - Inside, render `{children}` and the `MobileTabBar` fixed to the bottom.
  - Add `padding-top: env(safe-area-inset-top)` and `padding-bottom: calc(env(safe-area-inset-bottom) + 56px)` (56 px is the height of the tab bar).
  - On iOS, include a `<div className="noise-overlay absolute inset-0" />` for the noise texture.

### 2.2 GlassScreen

* **File:** `src/components/layout/GlassScreen.tsx`
* **Purpose:** Overlay container for secondary pages (e.g. role selection, chat, records).  It uses a translucent background and blur to preserve the home page context【turn0file0†L21-L34】.
* **Implementation details:**
  - Render a `<div>` covering the full viewport with `backdrop-blur-lg` and `bg-surface/50`.
  - Provide optional `onBack` callback to render a back arrow in the header.
  - Use `motion.div` to animate entry: fade in (`opacity: 0 → 1`) and slide up (`translateY: 20px → 0`).  Wrap in `AnimatePresence` when used in routing.

### 2.3 Pressable

* **File:** `src/components/ui/Pressable.tsx`
* **Purpose:** Standardised interaction wrapper for all tappable elements.  It applies scale/opacity changes on press.
* **Implementation details:**
  - Wrap children in a `motion.button` or `motion.div` and accept class names via props.
  - Use Motion’s `whileTap={{ scale: 0.96 }}` and optionally `whileHover` for non‑touch devices.
  - Allow forwarding of additional props such as `onClick` or `disabled`.

### 2.4 PageTransition

* **File:** `src/components/motion/PageTransition.tsx`
* **Purpose:** Wrap route pages to animate them when navigating.
* **Implementation details:**
  - Create a component that wraps children in `<AnimatePresence>` and `<motion.div>`.
  - Set initial properties `opacity: 0`, `x: 12` (for forward navigation) or `y: 12` (for modal screens).  Animate to `opacity: 1`, `x: 0` and exit to `opacity: 0`, `scale: 0.98`.
  - Accept `direction` prop to choose sliding direction.

### 2.5 BottomSheet

* **File:** `src/components/ui/BottomSheet.tsx`
* **Purpose:** Implement drawers for rewards, record details and forms using Vaul.
* **Implementation details:**
  - Wrap Vaul’s `Drawer.Root` and provide `open`, `onOpenChange` props.
  - Define two detents: `0.7` (70 %) and `1` (100 %).
  - Use a custom overlay with `bg-black/50 backdrop-blur-sm` and animate underlying content scaling down to `0.98` when the drawer is open.
  - Provide a `title` slot and optional `actions` slot for buttons.

### 2.6 Toast System

* **Files:** `src/components/ui/Toast.tsx`, `src/components/ui/useToast.ts`
* **Purpose:** Provide success, error and info notifications.  Use Radix Toast as the foundation.
* **Implementation details:**
  - Wrap `ToastProvider`, `ToastRoot`, `ToastTitle`, and `ToastDescription` into a hook (`useToast`) that exposes `toast.success()`, `toast.error()`, etc.
  - Style toasts with accent colours (cool for success, warm for errors) and animate them sliding up from the bottom.

### 2.7 Other Primitives

Implement the following additional components as needed:

| Component | File | Purpose | Notes |
|---|---|---|---|
| `ScreenHeader` | `src/components/layout/ScreenHeader.tsx` | Back arrow and title bar | Use `Pressable` for back; centre the title; optional right‑slot for actions. |
| `MetricLine` | `src/components/ui/MetricLine.tsx` | Displays a number and label | Large number, small label; optional icon. |
| `RewardCard` | `src/components/rewards/RewardCard.tsx` | Shows reward details and redemption button | Accept `reward` props; use `Pressable` for the card; open `BottomSheet` on tap. |
| `RecordCard` | `src/components/records/RecordCard.tsx` | Shows record fields and comments | Support selection of visible fields; long press reveals admin actions (when in admin view). |
| `ChatBubble` | `src/components/chat/ChatBubble.tsx` | Displays user/AI/system messages | Accept `type` prop to change alignment and style; animate on mount. |
| `DraftPanel` | `src/components/chat/DraftPanel.tsx` | Shows AI‑generated draft with rating and actions | Use warm accent for background; includes “Confirm” and “Edit”. |
| `Composer` | `src/components/chat/Composer.tsx` | Input area with voice and send buttons | Handles keyboard focus; uses `Pressable` around the send button. |
| `FieldSelector` | `src/components/records/FieldSelector.tsx` | Selects which fields are shown in record lists | Horizontal scrollable list of `Pressable` pills; ensures at least one selected. |
| `InlineCommentForm` | `src/components/admin/InlineCommentForm.tsx` | Comment and score input for admin records | Uses Radix Slider for score; shows validation messages. |
| `OpsTable` / `JsonPanel` | `src/ops/…` | Desktop‑only components | Use a separate layout; not styled like mobile. |

## 3. Page Implementation

This section maps each page to the components defined above.  Place pages in `src/pages` and define routes accordingly (using React Router or your preferred router).

### 3.1 Login Page (`LoginScreen.tsx`)

1. Wrap the content in `MobileAppShell`.
2. Create a glass card for the login form.  Use `motion.div` to animate the card in on mount (fade and slide up).
3. Use `<input>` elements styled with Tailwind for account, password and CAPTCHA.  Add a refresh button for the CAPTCHA on the right (a `Pressable` containing a refresh icon from `lucide-react`).
4. Use a `Pressable` for the submit button.  Disable it while awaiting the login response.  On error, call `toast.error()` and apply a horizontal shake animation to the card.

### 3.2 Home Page (`HomeScreen.tsx`)

1. Wrap in `MobileAppShell` and use the gradient background.
2. Display the user’s avatar as a small round `Pressable` in the top left.  On press, navigate to the `RoleScreen`.
3. If the user is not bound to an admin, show the sign‑in call‑to‑action inside a large glass card.  Use a round `Pressable` with an emoji or icon.  After the user signs in successfully, fire `confetti()` and show a success toast.
4. If the user is a bound admin, display the points metric and a button that navigates to the rewards management page.
5. Add `MobileTabBar` at the bottom to switch between Home, Chat and Records.  Use `Pressable` for each tab; the active tab is highlighted with the cool accent and an indicator dot.

### 3.3 Role Page (`RoleScreen.tsx`)

1. Present this page inside `GlassScreen` so that the home background remains visible【turn0file0†L21-L34】.
2. Display the identity card with avatar, name and role.  Use a segmented control to switch roles.  When switching, show a mini transition: fade the current content out and slide the new content in.
3. Use `MetricLine` to display the current points.  For users, display `RewardCard` components in a scrollable list.  For bound admins, include edit/delete controls on each card (revealed by a long press gesture using `@use‑gesture`).
4. Add a “Back” button using `ScreenHeader`.

### 3.4 Chat Page (`ChatScreen.tsx`)

1. Use `GlassScreen` with a `ScreenHeader` titled “Chat”.
2. Render `ChatHistory` inside a `<div className="flex flex-col space-y-2 overflow-y-auto">`.  Each `ChatBubble` animates on mount (fade and slide).
3. When a draft is available, render `DraftPanel` above the `Composer`.  Use a `motion.div` with `layout` to animate between hidden and visible states.
4. Place `Composer` at the bottom.  Use CSS to adjust its position when the keyboard is visible (e.g. using `window.visualViewport.height` in a custom hook).  The send button triggers the message dispatch; disable it when the input is empty.
5. Use the `Toast` system to show success or error messages after sending.

### 3.5 User Recent Records Page (`RecordsScreen.tsx`)

1. Wrap the page in `GlassScreen` and use `ScreenHeader` titled “Records”.
2. Render `FieldSelector` at the top so users can toggle fields.  Use a horizontal scroll container; ensure at least one pill remains selected.
3. Map over the records array and render a `RecordCard` for each.  When pressed, open a `BottomSheet` with full record details and comments.  Use `layoutId` on the card and sheet to animate between states.
4. If there are no records, render `EmptyState` with a friendly illustration and message.

### 3.6 Admin Points & Rewards Page (`AdminRewardsScreen.tsx`)

1. Use `GlassScreen` and a `ScreenHeader` titled “Rewards”.
2. Show the points metric using `MetricLine`.  Place it at the top of the page.
3. Add a “Add reward” button (a `Pressable` in the header or as a floating action button).  Clicking it opens a `BottomSheet` containing two `<input>` fields and a save button.  Validate inputs; show inline errors; call `toast.success()` on success and reset the form.
4. Render each reward with `RewardCard`.  Use `@use‑gesture` to detect long press and slide in edit/delete controls.  When an admin action is performed, update the list accordingly.

### 3.7 Admin Recent Records Page (`AdminRecordsScreen.tsx`)

1. Use `GlassScreen` and `ScreenHeader` titled “Admin Records”.
2. For each record, render a `RecordCard` extended with an `InlineCommentForm`.  Use a multi‑line `<textarea>` for comments and a `Slider` (Radix) for the score.  Keep the save button disabled until both fields are valid.
3. On save, call the API, disable the inputs and show a loading spinner in the button.  When the request resolves, update the record list and trigger a success toast.  Scroll the saved record out of view or highlight it.

## 4. Additional Notes

* **Routing:** Use React Router or a similar library.  Wrap page components in `PageTransition` to achieve animated route changes.  Pass a `direction` prop when navigating to control slide direction (e.g. right for forward navigation, left for back).
* **Global state:** Use React Context or Zustand to manage the current user, points, records and drafts.  This separates UI concerns from business logic.
* **Data fetching:** Keep API calls in `shared/api` as per the existing codebase.  Use `Toast` to indicate loading, success and error states.  Do not change API signatures【turn0file0†L150-L160】.
* **Accessibility:** Add `aria-labels` to buttons and inputs.  Ensure that colours meet contrast requirements.  Use semantic HTML elements whenever possible.
* **Testing:** Write unit tests for each component using React Testing Library.  Test interactions (press feedback, transitions, form validation) and ensure that they produce the correct UI changes.

By following this implementation plan, developers can convert the high‑level design specification into a maintainable codebase.  Each component and page is clearly mapped to a file and a set of responsibilities.  The choice of Motion, Vaul and Tailwind ensures that interactions are smooth and accessible, while the underlying data flows remain unchanged from the original specification【turn0file0†L1-L20】.