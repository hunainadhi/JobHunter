---
target: landing page (board/app/page.tsx)
total_score: 21
max_score: 28
na_heuristics: 5,7,10
p0_count: 1
p1_count: 2
timestamp: 2026-08-05T19-28-35Z
slug: board-app-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Live stats are a real strength, but `fetchLandingStats` has no loading fallback — a slow Supabase cold-start (you've hit this before) blocks the whole hero with nothing shown |
| 2 | Match System / Real World | 3 | "vector embedding"/pgvector language dropped with no visual anchor for a first-timer |
| 3 | User Control and Freedom | 3 | Single-destination page, appropriate for a landing page |
| 4 | Consistency and Standards | 3 | Three CTA buttons (nav, hero, final) each hand-roll their own inline `boxShadow` — the hero button has an extra inset highlight the other two don't |
| 5 | Error Prevention | n/a | No forms/inputs on this page |
| 6 | Recognition Rather Than Recall | 4 | Everything needed is on-screen, no memory burden |
| 7 | Flexibility and Efficiency | n/a | Persuade-mode landing page, no power-user path to skip |
| 8 | Aesthetic and Minimalist Design | 3 | Step 3's copy crams 3 distinct product claims into one 30-word sentence |
| 9 | Error Recovery | 2 | `totalJobs=0` is never special-cased — CTA would read "Browse 0 open positions" |
| 10 | Help and Documentation | n/a | Correctly out of scope for a landing page |
| **Total** | | **21/28** | **Good (75%)** |

## Design Specificity Verdict

**LLM assessment**: This is a generic SaaS template with job-search nouns substituted in — hero → 3-icon "how it works" cards → logo-pill row → repeat-CTA is the exact skeleton of a thousand integration/API-product landing pages. The copy is honest and technically literate (real platform names, "pgvector," specific mechanism), which is where specificity shows up — but the *structure* carrying that copy is completely interchangeable. The sharpest gap: a page whose entire pitch is "semantic search across scraped postings" never lets a visitor type a query or see a match.

**Deterministic scan**: `detect.mjs` ran clean (exit 0, zero findings) across `page.tsx`, `site-nav.tsx`, and `globals.css` — no automated slop-pattern hits.

**Visual evidence** (Playwright screenshots at 1280px and 390px, captured directly): both confirmed real layout issues the source-only review couldn't see precisely — the hero headline breaks into 3 lines on desktop and 4 on mobile, isolating "keywords." alone on its own line both times; the 12-platform badge grid wraps into independently-centered rows of uneven length (7+5 desktop, 3+2+4+3 mobile) that don't align into a real grid, reading as ragged rather than intentional. A small black "N" badge appears fixed at the far-left edge in both screenshots, overlapping content — likely a browser-tooling/extension artifact from the capture environment, not page markup (worth a quick visual double-check in a real browser, but not treated as a page defect here).

## Overall Impression

Technically honest, visually generic. The copy respects the reader's intelligence and never oversells, but the page structure gives you no reason to believe the "search by meaning" claim beyond taking it on faith — and the one interactive proof point (an actual search) is one click away behind a CTA, never on the page itself.

## What's Working

1. **The live stat strip** — `{totalJobs} live postings · {PLATFORMS.length} ATS sources · Last scraped {formatLastScrape}` is a real, computed freshness signal, not marketing copy. `formatLastScrape`'s tiered relative-time formatting is a genuinely useful detail.
2. **Step 3's copy** — "automatically expired once a listing goes quiet — so the board stays a list of jobs you can actually apply to" names a real, specific pain competitors don't solve. Sharpest sentence on the page.
3. **The platform pill list** — uses the real `PLATFORMS` constant (verifiable, not "integrates with everything" vagueness).

## Priority Issues

**[P0] No live demonstration of the core differentiator**
Why it matters: The entire pitch is semantic search, but there's no search input anywhere on the page — not in the hero, not even in the section that literally says "Try a search that wouldn't work anywhere else." A visitor has to click through to `/jobs` and type into an empty box before they experience the thing being sold.
Fix: Embed a real search input in the hero or final section — either submit straight to `/jobs?q=...`, or show 2-3 clickable example-query chips that deep-link with a query pre-filled.
Suggested command: `/impeccable shape` (this is a structural addition, not a polish pass)

**[P1] Zero hover/focus states on every interactive element**
Why it matters: Confirmed directly — no `:hover`, `:active`, or `:focus-visible` anywhere in `page.tsx`, `site-nav.tsx`, or `globals.css`. All three CTA buttons and the nav link are static inline styles. Keyboard users tabbing through get no visible focus ring (nothing restores one after any browser reset), and mouse users get zero feedback on interactive elements.
Fix: Add a shared button treatment with hover (darken `--bg-brand`), active (reduce shadow/translateY), and `:focus-visible` outline using `--border-brand`.
Suggested command: `/impeccable polish`

**[P1] Unhandled empty/zero state for `totalJobs`**
Why it matters: If the DB is empty, mid-migration, or a query fails silently, the hero CTA reads "Browse 0 open positions" and the stat strip reads "0 live postings" directly under a headline promising "Every ATS" — undermines trust at the exact moment a visitor decides whether to click through.
Fix: Guard with a fallback ("Browse open positions" when `totalJobs` is 0) and hide or alter the stat strip below a sane threshold.
Suggested command: `/impeccable harden`

**[P2] Hero headline wraps awkwardly at every width**
Why it matters: Confirmed via screenshot — breaks into 3 lines on desktop (1280px) and 4 on mobile (390px), with "keywords." stranded alone on its own line both times. Reads as an authoring accident, not a deliberate line break.
Fix: Rebalance the headline copy/length or add explicit responsive line-break control so it never orphans a single word.
Suggested command: `/impeccable typeset`

**[P2] Platform badge grid doesn't actually form a grid**
Why it matters: Confirmed via screenshot — 12 pills wrap into independently center-justified rows of uneven length (7+5 desktop, 3+2+4+3 mobile), so rows don't align to any shared edge. Reads as ragged rather than intentional, undercutting the "comprehensive, systematic coverage" message the section is making.
Fix: Switch to a real grid (fixed columns, left-aligned) or a deliberately justified flex-wrap so edges align.
Suggested command: `/impeccable layout`

## Persona Red Flags

**Jordan (first-timer)**: Reads "vector embedding"/pgvector-adjacent language with zero visual aid — no diagram, no before/after example. Has to take the semantic-search claim on faith because there's no search box to try (P0). Also hits three visually near-identical blue buttons (nav, hero, final CTA) with no signal about why they'd click the second or third over the first.

**Riley (stress-tester)**: Immediately breaks the "Browse 0 open positions" case (P1) and would notice the freshness claim ("fetched every day") can self-contradict if `formatLastScrape` ever shows several days — a real risk for a solo-maintained pipeline with no alerting.

**Casey (mobile)**: The nav's "Browse jobs" button is roughly 32-34px tall — under the 44px minimum touch target. 80px of top hero padding eats a large share of a short mobile viewport before any content appears.

## Minor Observations

- Icon-in-40x40-rounded-square pattern (RefreshCw/Search/Filter) is a stock Stripe/Linear/Vercel "how it works" treatment — fine as a system, but adds to the generic-template read.
- "Every ATS" is restated three times by the middle of the page (hero, step 1, sources heading) with no new information added each time.
- Freshness claim risk: "fetched every day" copy can be visibly contradicted by `formatLastScrape` if a scrape gap ever occurs — worth capping the claim's specificity or adding alerting.
- Button text ("Browse {totalJobs.toLocaleString()} open positions") has no tested behavior at 6-digit job counts or narrow viewports.
- Dark-mode CSS variables are fully built out in `globals.css` but untested against this page's actual markup.
- A small black "N" badge appears in both captured screenshots, likely a browser-tooling/extension artifact from the capture environment rather than real page content — flagging so it isn't mistaken for a layout bug, but worth a quick sanity check in an incognito window.

## Questions to Consider

1. If the whole pitch is "search by meaning, not keywords," what would break if the hero itself *was* the search box, instead of a CTA to an empty one?
2. This is a solo engineer scraping 12 ATS platforms daily — a genuinely impressive, specific fact. Why does the page read like a 10-person marketing team wrote it instead of leaning into that personal credibility?
3. The "How it works" section explains the full mechanism before a visitor has seen one actual job. Would showing one compelling real result *first* be more persuasive than explaining pgvector to someone who hasn't decided to care yet?
