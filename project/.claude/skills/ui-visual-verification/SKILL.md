---
name: ui-visual-verification
description: Verify a FounderOS UI change for truthful data, hierarchy, interaction, motion, responsive behavior, accessibility, and runtime evidence.
argument-hint: "<route, component, or visual change>"
disable-model-invocation: true
---

# FounderOS UI and visual verification

## Truth before aesthetics
Trace every displayed value, status chip, count, label, and fallback to its actual source. Keep runtime events, Console approvals, ledger evidence, and repository state distinct. Use “Source unavailable” or “No observed data” when evidence is unavailable; never manufacture healthy telemetry.

## Review surfaces
- hierarchy and Founder Attention priority;
- readability, typography, spacing, and contrast;
- keyboard flow, focus visibility, semantic structure, screen-reader labels;
- reduced-motion parity and no information conveyed only through motion/color;
- loading, empty, unavailable, error, stale, and partial-data states;
- responsive layouts and overflow;
- hover/active/focus micro-interactions;
- performance and animation stability;
- visual regressions against approved references.

## Evidence
Use the real route and data state when possible. Capture screenshots at representative viewport sizes, inspect console/network errors, and run relevant component/E2E/accessibility checks. A static screenshot alone cannot prove interaction, source truth, or reduced-motion behavior.

## Output
Start with blocking findings. Then give 1–10 scores for clarity, hierarchy, friction, trust, and emotional experience; the main problem; top five fixes; highest-impact recommendation; exact verification performed; and residual uncertainty. Stop after two design-review rounds unless the Founder authorizes more.
