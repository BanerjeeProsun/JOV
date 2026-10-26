# JOV.si UI Audit — Phase 0

## 1. Stack & Architecture
- **Framework**: Vite 8.3.4 (Single Page Application)
- **React Version**: React 19.3.1 (`react` & `react-dom`)
- **Router**: Client-side state router in `web/src/App.tsx` (`activeTab` state: `'overview' | 'jobs' | 'queue' | 'tracker' | 'profile' | 'settings' | 'diagnostics'` plus drill-down `reviewAppId` for Application Review).
- **Styling System**: Tailwind CSS 3.4.19 with PostCSS + `web/src/index.css`.
- **Package Manager**: `npm` (`web/package-lock.json`).

## 2. Animation Packages
- **`motion`**: Installed (`^14.6.0`). Imported from `motion/react`.
- **`framer-motion`**: Not installed (clean).
- Single animation library requirement is satisfied (`motion/react`).

## 3. Icon Libraries
- **Icon Library**: Exclusively `lucide-react` (`^1.61.0`).
- No secondary icon libraries (no `@heroicons`, `react-icons`, or `font-awesome`).

## 4. Theme Colors & Hard-Coded Values (Bugs Causing White Cards in Dark Mode)
- `web/tailwind.config.ts`: Hardcoded light hex codes for `canvas` (`#f5f5f7`), `surface` (`#ffffff`), `ash` (`#e8e8ed`), `apple-canvas`, `surface-subtle`, `surface-hover`.
- `web/src/index.css`: Hardcoded hex tokens in `:root` and `:root[data-theme='dark']` (`--color-apple-ink`, `--color-pure-white`, `--color-fog-canvas`, etc.), plus `!important` utility overrides that collide with dark theme rendering.
- `web/index.html`: Hardcoded `class="dark"` and `bg-void-black text-pure-white font-sans antialiased min-h-screen selection:bg-coral-pulse/20`.
- Component & screen files with hard-coded colors / `bg-white` / `text-black` / `border-[#d6d6d6]` / hex/rgb values:
  - `web/src/components/BrandLogo.tsx`: Hardcoded `#ffffff` and `#1d1d1f`.
  - `web/src/components/Button.tsx`: Hardcoded `#0071e3`, `#e8e8ed`, `#ffffff`, `#1d1d1f`.
  - `web/src/components/Card.tsx`: Hardcoded `bg-white` / `bg-surface`.
  - `web/src/components/AutonomyBanner.tsx`: Hardcoded hex alert styles.
  - `web/src/screens/OverviewScreen.tsx`: Hardcoded `border-white`, `border-[#d6d6d6]`, `bg-white`, `bg-ash`.
  - `web/src/screens/JobDiscoveryScreen.tsx`: Hardcoded badge colors and borders.
  - `web/src/screens/ApplicationQueueScreen.tsx`: Hardcoded card colors and badges.
  - `web/src/screens/ApplicationTrackerScreen.tsx`: Hardcoded timeline borders and row backgrounds.
  - `web/src/screens/CandidateProfileScreen.tsx`: Hardcoded input backgrounds, badges, and JSON blocks.
  - `web/src/screens/SettingsScreen.tsx`: Hardcoded section backgrounds.
  - `web/src/screens/DiagnosticsScreen.tsx`: Hardcoded pre/code block styling.
  - `web/src/screens/ApplicationReviewScreen.tsx`: Hardcoded document preview borders and modal styles.

## 5. Sandbox / Mock Banners
- `web/src/components/AutonomyBanner.tsx`: Defines `AutonomyBanner` (previously rendered dry-run banner).
- `web/src/App.tsx`: Passed `autonomyLevel="L0_DRY_RUN"` to `Navbar.tsx`.
- `web/src/screens/OverviewScreen.tsx`: Contained sandbox / safety text.
- E2E tests specifically look for `"Release 1 Safety Sandbox Active"` and `"Command Center"`.

## 6. What Codex Added vs. What Was Claimed
- **Logo Component**: Only a simplistic inline SVG monogram `BrandLogo.tsx` with hardcoded `#1d1d1f`/`#ffffff`. Missing geometric 64x64 J mark with signal dot, wordmark with tuned spacing, lockup variants, and `layoutId="brand-j"` handoff.
- **Favicon**: Default/static SVG, missing dark/light theme awareness and complete favicon set (32px PNG, apple-touch-icon).
- **Theme Provider**: Barebones `ThemeProvider.tsx` using `jovsi-theme` key (not `jov-theme`), missing `try/catch`, missing pre-paint blocking script in `<head>`, causing severe FOUC (flash of unstyled content/wrong theme).
- **Motion Usage Count**: 43 references across `web/src`. Lacks formal motion token design system (`src/design/motion.ts`), spring physics tokens, and signature choreography.
- **Glass Tokens**: Generic CSS blur classes (`.glass-nav`, `.glass-dialog`), not adhering to strict allowed surfaces or pearl lighting.
- **Video Assets**: `ls public src/assets | grep -i -E "mp4|webm|poster"` returns **zero** files. Neither `onboarding-loop.mp4`, `onboarding-loop.webm`, nor `onboarding-poster.jpg` existed on disk.

## 7. The 8 Screens Mapping
1. **Overview / Welcome**:
   - Tab ID: `'overview'`
   - File: `web/src/screens/OverviewScreen.tsx`
2. **Jobs**:
   - Tab ID: `'jobs'`
   - File: `web/src/screens/JobDiscoveryScreen.tsx`
3. **Application Queue**:
   - Tab ID: `'queue'`
   - File: `web/src/screens/ApplicationQueueScreen.tsx`
4. **Tracker**:
   - Tab ID: `'tracker'`
   - File: `web/src/screens/ApplicationTrackerScreen.tsx`
5. **Candidate Profile**:
   - Tab ID: `'profile'`
   - File: `web/src/screens/CandidateProfileScreen.tsx`
6. **Settings**:
   - Tab ID: `'settings'`
   - File: `web/src/screens/SettingsScreen.tsx`
7. **Diagnostics**:
   - Tab ID: `'diagnostics'`
   - File: `web/src/screens/DiagnosticsScreen.tsx`
8. **Application Review**:
   - Activated via: `setReviewAppId(appId)` (from Queue or Jobs)
   - File: `web/src/screens/ApplicationReviewScreen.tsx`
