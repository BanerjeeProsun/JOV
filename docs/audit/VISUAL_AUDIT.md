# JOV.si Visual and Responsive Audit

## Evidence and limitation

The repository does not contain the referenced `DESIGN.md`; only README/documentation references exist. Visual conclusions therefore use actual CSS/assets and the checked-in QA screenshots under `docs/qa/`, not an unavailable design file. The current build and existing Playwright UI test were executed; no source/UI changes were made.

## Findings

| ID | Severity | Evidence | Finding/status | Correction |
|---|---|---|---|---|
| VIS-001 | P1 | `README.md:36-43` specifies `#040506`, Coral `#ff6363`, Inter/Geist Mono; `web/src/design/tokens.css:3-65` defines a light Apple-like `#fbfbfd`/black accent system and Geist Sans/Instrument Serif | Design reference and implementation tokens disagree; **PF** | Restore/commit the authoritative design spec or explicitly revise the product token contract; remove compatibility aliases after migration |
| VIS-002 | P1 | `docs/qa/overview-light-390.png`, `settings-dark-390.png`, `jobs-light-1440.png` | Screens render and are polished, but mobile overview is visually dense/blurred around the hero/video and bottom nav overlays content; settings uses a large dark surface hierarchy unlike the light screenshot family; **PF** | Re-run a deliberate 390/768/1024/1440 matrix with overlay/overflow assertions and adjust safe-area/padding |
| VIS-003 | P1 | `SettingsScreen.tsx:243-268,513-543` | Settings uses an internal sticky rail and six tabs, but the “Sources & Connectors” health cards present green/amber statuses based largely on HTTP status and are not tied to a persisted source selection; **PF** | Use explicit `verified`, `unconfigured`, `unavailable`, and `not-tested` visual states |
| VIS-004 | P2 | `tokens.css:68-118`, `ThemeProvider` and `theme-init.ts` | Theme initialization exists and reduced-motion CSS exists; runtime motion still performs state updates in effects and lint reports many `set-state-in-effect` warnings. **IU** | Test first paint, system-theme changes, and reduced-motion with browser assertions; simplify effect-driven state |
| VIS-005 | P2 | `HeroVideo.tsx:61-133`; ffprobe: dark MP4 1920x1080/20.25s, light MP4 1280x720/3.8s, WebM dark exists but is not loaded | The hero uses real assets with radial masks/posters, but only MP4 is selected; dark/light composition and duration/aspect differ, and the WebM source is unused. Root `herovid*.mp4` assets are also unused. **PF/DC** | Add `<source>` fallback order, verify composition at all widths, remove/relocate unused root assets only after reference search |
| VIS-006 | P2 | `web/src/components/brand/JLogo.tsx:26-90` | J mark is a reusable inline SVG component, so branding is not a hard-coded text character; **FV** | Add SVG snapshot/contrast and accessible-name tests |
| VIS-007 | P2 | `web/src/index.css:117-130`, mobile QA screenshots | Reduced motion disables CSS transitions, while `MotionConfig reducedMotion="user"` exists; hero still loads/posters and effect timers are not all canceled. **PF** | Ensure timers/video playback/intro sequence stop under reduced motion |
| VIS-008 | P2 | lint output, `ApplicationTrackerScreen.tsx:401-409`, `DiagnosticsScreen.tsx:201` | `Date`/`Date.now` are called during render; lint also flags React effect patterns, missing deps, and impure render paths. **IU** | Derive timestamps once at load and remove impure render calls |
| VIS-009 | P3 | `web/src/App.tsx:24-62`, screenshot navigation | Floating header/bottom nav is visually consistent, but tab changes do not update the browser URL; refresh loses context. **PF** | Implement route-aware navigation and focus restoration |
| VIS-010 | P3 | `web/src/screens/JobDiscoveryScreen.tsx:111-123` | Import dialog is visually complete but opens with demo content, producing a fake job in ordinary UI use. This is a data-integrity/visual empty-state defect, not merely styling. **MO** | Empty form with examples as placeholders only |

## Accessibility observations

Positive evidence: global `:focus-visible` ring (`index.css:34-38`), skip link (`AppShell.tsx:21-27`), labels on most forms, `aria-current` navigation, and reduced-motion support exist. Gaps: several clickable `<div>` elements in tracker/dropdowns, icon-only controls rely on titles or absent labels, tab rails lack `aria-selected`/tablist semantics, and clipboard/download behavior has no keyboard-specific regression test.

## Asset inventory

Loaded hero assets are in `web/public/media/`: `hero-video.mp4`, `hero-video-light.mp4`, `hero-video.webm`, posters, and onboarding media. The root `herovid.mp4` and `herovidlight.mp4` are not referenced by `web/src`; classify as DC until a dynamic/config reference is ruled out.
