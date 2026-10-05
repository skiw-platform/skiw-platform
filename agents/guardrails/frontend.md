# Guardrails — frontend and accessibility

**Stack:** any web UI. Tool names (e.g. `cn()`, CVA, shadcn/ui) are examples; the rule is the outcome.
If this project lacks a mechanism a rule names, don't silently waive these rules. Before ticking this pack, record
in `PROJECT.md` §9 the alternative mechanism and how each affected rule's outcome is tested; otherwise
leave the pack unticked and write replacement rules in §9.

For any project with a UI. IDs match the `FE-xx` gates in the owner's web-development guidelines,
minus the stack-specific ones, so a finding means the same thing in both. Gaps in the numbering are
intentional: those numbers belong to the dropped stack-specific gates and are never reused.

**Principle:** standardise the engineering, not the client's look. Colours, type, spacing, motion and
imagery belong to the project's design authority. Semantics, layout method, component architecture,
accessibility and code quality are the same everywhere. Code that only *looks* right is not done.

## Semantic structure
- **FE-01** Elements chosen by meaning, not appearance. `<div>` only when nothing more meaningful fits.
- **FE-02** Every `<section>` has an accessible name (heading via `aria-labelledby`, or `aria-label`). A purely visual wrapper is a `<div>`.
- **FE-03** `<article>` for self-contained items (post, product card, testimonial, listing).
- **FE-04** Repeated sibling content is a `<ul>`/`<ol>` (card grids, logo walls, nav sets), styled with Grid/Flex.
- **FE-05 (hard)** Links navigate, buttons act. No click handlers on `div`/`span`; no `<a>` without a valid `href`. Everything clickable is keyboard-operable with visible focus.
- **FE-06** Heading level follows document outline, never font size. One `<h1>` per page. No skipped levels.
- **FE-07** Exactly one `<main>`; `header`/`nav`/`footer` where applicable; multiple `<nav>`s each have a distinct accessible name.

## Layout
- **FE-10** Grid for two-dimensional layout, Flexbox for one axis. No fake grids from flex + percentage widths.
- **FE-11** Absolute positioning only for overlays, decoration, badges, icons inside controls. Never page structure.
- **FE-12** Sibling spacing uses `gap`, not a system of per-child margins.
- **FE-13** Colours, type, spacing, radii and shadows come from named design tokens. A recurring literal is a missing token.
- **FE-14** Mobile-first. No horizontal page overflow at any supported width; wide content scrolls inside its own container.

## Components
- **FE-20** Extract a component on real reuse or shared behaviour, not on resemblance. No component per wrapper.
- **FE-21** No monolithic page components, copy-paste variants, near-duplicates, heavy prop drilling or speculative configurability.
- **FE-22** Content is separated from presentation: typed content modules, collections or CMS data, not copy hardcoded in components.
- **FE-23** Props typed and named for intent. Variants via a class helper (`cn()`, CVA or equivalent); no string-concatenated partial class names.
- **FE-24 (hard)** Components that carry business logic (price, cart, stock, checkout, account, invoice totals…) are owned, typed and tested in the project. Never adopted wholesale from a registry.

## Rendering and data
- **FE-31** Client-side interactivity only where there is a stated interactive need, in the smallest component that owns the state. Static content stays usable without client-side JavaScript; use server rendering where the stack supports it.
- **FE-32** No JavaScript for what HTML, CSS or server rendering already does. Forms, navigation and content visibility work without JS succeeding.
- **FE-34** Fetch at the nearest server boundary that needs the data. Independent reads in parallel (no avoidable waterfalls). Every cache states its lifetime and invalidation trigger. Money, stock and identity data never come from an unstated cache.

## Dependencies and registries
- **FE-40** New packages pass the dependency ladder (`guardrails/universal.md`). No large library for one effect.
- **FE-41 (hard)** Registry components (shadcn/ui and similar) are building blocks, never the design system: dependency tree trimmed, accessibility and responsiveness checked, re-skinned onto project tokens, no competing theme layer, no whole visual framework on top of an approved design.
- **FE-42** Every registry-sourced component recorded in the decisions log: source, version or date, what was changed.

## Code quality
- **FE-50** Typecheck, lint and production build pass before any "done" claim.
- **FE-51** No dead code, magic numbers, or nesting a guard clause would flatten. Clever code a maintainer can't read at a glance is a defect.
- **FE-52** Comments explain why, never what.
- **FE-60** Decision ladder: native HTML/CSS → existing project code → framework feature → approved registry (FE-41) → small custom code → new dependency (FE-40).
- **FE-61** Read and follow the existing codebase before changing architecture. Don't rewrite working code the task doesn't need.

## Accessibility (WCAG 2.2 AA)
- **A11Y-01** Full keyboard operability, visible focus, logical tab order.
- **A11Y-02** Contrast ≥ 4.5:1 body text, ≥ 3:1 large text and UI components. If the design violates this, flag it and ASK; don't silently change or silently ship it.
- **A11Y-03** Form inputs have programmatic labels; errors announced (`aria-live`) and linked with `aria-describedby`.
- **A11Y-04** `prefers-reduced-motion` respected for all animation.
- **A11Y-05** Informative images have alt text; decorative images have empty alt.
- **A11Y-06** Verified with a real browser (keyboard + automated axe-style check), never inferred from markup. A clean automated scan alone is not a pass.

## Verification
- **FE-70** Browser tests cover desktop and mobile widths: no overflow, keyboard navigation, form success/error/failure paths, empty/loading/error states, zero unhandled app errors.
- **FE-71** Tested with real content: longest labels, every locale, missing images, long prices.
