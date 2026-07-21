# Brag Plan: JobHunter

## What is this app?
A serverless pipeline that fans out ~420 Lambda workers 4x a day to scrape 16,700+ companies across 13 job boards, scores every posting 0-100 against one specific person's resume using an LLM, and serves the matches on a live dashboard — run entirely on free-tier infrastructure, for a company of exactly one employee.

## The angle
Play it as a Series A pitch deck for enterprise-grade recruiting infrastructure — and let the numbers slowly reveal that the entire "customer base" is one Waterloo, Ontario software developer looking for his next role. The bigger and more impressive the scraping numbers sound, the funnier it is when the punchline lands: all this, for one user, for $0/month.

## Hook (first 2-3 seconds)
Full-bleed, dead-serious title card: "Introducing JobHunter." Beat. Then, smaller, underneath: "Enterprise job-market intelligence." (No wink yet — the joke hasn't landed. It's still just a pitch.)

## Key moments (the middle)
- The architecture diagram assembling itself piece by piece — EventBridge → Orchestrator → **~420 Lambda workers** → Supabase → Scoring Lambda → Dashboard — narrated like infrastructure bragging rights.
- A stat sequence, presented completely straight: "16,700+ companies tracked." "13 job sources." "Every posting scored 0-100 by AI." Each stat lands like a real pitch-deck metric.
- The reveal cut: the live job board itself, with the real header copy "Browse 16,187 open positions across Canada," the search bar, category/level/platform filters, and a row of scored results with blue "Apply" buttons and platform badges (Greenhouse, Lever, Ashby, YC...).
- The turn: "Monthly infrastructure cost:" ... "$0." held a beat longer than expected.
- The reveal of scale: "Total customers:" ... "1."

## Outro / punchline
"JobHunter. Enterprise-grade infrastructure for a market of one." Small final line, same deadpan register: "Still looking. Send openings." Cut to black.

## User flow worth showing
Entry → key action → result, using the real board:
1. **Entry:** land on the board, "Browse 16,187 open positions across Canada," last-updated timestamp.
2. **Key action:** type into the search bar (e.g. "AI engineer"), category/level filters visible.
3. **Result:** the filtered table — title, company, location with a green "Remote" pill, source platform badge, blue "Apply" button.

## Tone
- Preset: yc-parody
- Creative direction: fake Series A pitch deck for recruiting infrastructure that turns out to serve one candidate
- Interpretation: everything is delivered as fact, no exclamation points, no self-aware humor in the copy itself — the absurdity comes entirely from the gap between the scale of the infrastructure and the size of the userbase. Hard cuts, minimal crossfades, sentence-case data-point typography.

## Format: landscape — 1920x1080
## Duration: 23s

## Visual identity (from the project)
- Background: `#FFFFFF` (light) / `#030712` (dark) — use light mode, it's the board's default and reads cleaner on camera
- Accent / brand: `#1447E6` (blue), strong variant `#193CB8`
- Text heading: `#111827`; body: `#4B5563`; subtle: `#6B7280`
- Success pill (Remote badge): bg `#ECFDF5`, text `#065F46`, border `#A7F3D0`
- Display/body font: Inter (Google Fonts, `next/font/google`)
- Strongest visual element: the real board UI — clean white cards, blue "Apply" buttons with the subtle inset shadow, platform badges, the "Browse N open positions across Canada" header line

## Share copy (draft)
I built a 420-Lambda scraping pipeline, an LLM scoring engine, and a live dashboard to serve exactly one customer: me, looking for a job. $0/month. 🇨🇦

## Audio direction
- Role: sparse professional accents over a restrained, serious-sounding corporate/pitch-deck music bed
- Music: low-key confident bed, minimal percussion, no build-up drops — the kind of track under a real fundraising deck video
- Music treatment: starts immediately under the hook at moderate volume, stays flat and controlled through the stat sequence (no swell — swelling would undercut the deadpan), a single small dip/duck under the "$0" and "1 customer" beats so those lines land in near-silence, brief tasteful outro tail
- Music cue guidance: no bundled preset; detect cues at composition time (`npx hyperframes beats` or `analyze_music_cues.py`). Target one soft cue near the architecture-diagram reveal (~4s) and one at the board reveal (~9-10s); no cue needed at the punchline beats — let those sit in the dip, not on a hit.
- Audio-reactive treatment: none — restraint is the joke, don't let visuals pulse to music
- SFX posture: sparse. One dry, understated tick per stat line landing (not a cash-register or applause sound — a quiet keyboard/data-point tick), one soft UI sound on the simulated search-bar typing, one very dry, small stinger (not triumphant) on the final logo card
- Audio-coupled moments: the stat sequence ticking in one line at a time; the simulated typing in the search bar; the count reveal of "1" customer
- Restraint rule: no laugh-track energy, no whooshes, no triumphant horns anywhere — if a sound would work in a real Series A pitch video, it's allowed; if it would only work in a comedy sketch, cut it

## Storyboard

### Scene 1 — Hook — 2.5s
Full-bleed white background. "Introducing JobHunter." slams in center, heavy weight, `#111827` on white. Beat (~0.5s). Then smaller line fades in below: "Enterprise job-market intelligence." in `#4B5563`.
Sequential/interaction: none
Audio intent: confident, serious open — no comedic sting yet
Audio-coupled idea: none
Music: bed starts flat under the title
Transition mood: hard cut → Scene 2

### Scene 2 — Architecture reveal — 3.5s
The pipeline diagram assembles left to right: EventBridge → Orchestrator → "~420 Lambda workers" (this box emphasized, maybe pulses in slightly larger) → Supabase → Scoring Lambda (MiniMax-M3) → Dashboard. Boxes and arrows draw in sequentially, sentence-case data-point labels, `#1447E6` accent lines.
Sequential/interaction: yes — each box in the pipeline appears in order left to right, ~0.5-0.6s apart, holding fully assembled for the last ~1.5s
Audio intent: mechanical, precise, "look how much infrastructure this is"
Audio-coupled idea: soft tick per box arriving
Music: same flat bed, soft cue near this scene's midpoint
Transition mood: hard cut → Scene 3

### Scene 3 — The numbers — 4s
Three stat lines land one at a time, full-bleed, large sentence-case type on white: "16,700+ companies tracked." → "13 job sources." → "Every posting scored 0-100 by AI." Each holds ~1.2s before the next appears (previous line either persists smaller or clears — keep only one full-size claim on screen at a time to protect legibility).
Sequential/interaction: yes — 3 stat lines, sequential, ~1.2-1.3s hold each
Audio intent: matter-of-fact metric recitation, deadpan pride
Audio-coupled idea: one dry tick per stat landing
Music: flat bed continues, no swell
Transition mood: hard cut → Scene 4

### Scene 4 — The board (real UI) — 4s
Cut to the actual JobHunter board recreated faithfully: white card UI, header "Browse 16,187 open positions across Canada," last-updated line, the search filter row. A cursor types "AI engineer" into the search input (simulated typing, character by character). Filtered results settle into the table below: title/company/location rows with a green "Remote" pill on one row, platform badges (Greenhouse, YC, Ashby), and blue "Apply" buttons.
Sequential/interaction: yes — simulated typing into the search bar, then the result rows settle in (2-3 rows appearing together as the "filtered" result, not one by one — this is a filter action, not a list reveal)
Audio intent: grounding — "this is a real, working product," calmer register than the stat scenes
Audio-coupled idea: soft keystroke ticks during the simulated typing; one soft UI settle sound when results land
Music: flat bed, soft cue near this scene's start
Transition mood: hard cut → Scene 5

### Scene 5 — The turn — 3s
White background. "Monthly infrastructure cost:" in body-weight `#4B5563`, then a beat, then "$0." slams in large, `#1447E6`, held slightly longer than the earlier stat beats.
Sequential/interaction: yes — the label appears first, then "$0." lands after a distinct pause
Audio intent: the first moment of comic timing — music ducks slightly so the line lands in near-quiet
Audio-coupled idea: brief music dip under "$0."
Music: dip/duck here
Transition mood: hard cut → Scene 6

### Scene 6 — The punchline — 3s
"Total customers:" then a beat, then "1." lands, same treatment as Scene 5 — large, deadpan, centered.
Sequential/interaction: yes — label, pause, number
Audio intent: the joke fully lands here — same restrained dip as Scene 5, no triumphant hit
Audio-coupled idea: brief music dip under "1."
Music: dip continues/repeats
Transition mood: hard cut → Scene 7

### Scene 7 — Outro — 3s
"JobHunter." large, centered, `#111827`. Below it, smaller: "Enterprise-grade infrastructure for a market of one." Beat. Then smaller still, `#6B7280`: "Still looking. Send openings." Hold on this final card.
Sequential/interaction: yes — three lines arrive in sequence, largest first, each smaller and later than the last, all remaining on screen together at the end
Audio intent: calm, dry landing — one small, restrained stinger, not triumphant
Audio-coupled idea: one dry stinger under "JobHunter." arriving
Music: bed resolves/fades out under the final hold
Transition mood: fade to black (end)

**Music mood for this video:** deadpan / parody — restrained corporate-pitch-deck bed, no swells, dips under the two punchline beats
**Audio summary:** A flat, confident, understated music bed runs under the entire pitch, ticking softly with each stat and UI beat, then ducks quietly under the two punchline reveals ("$0.", "1.") so the joke lands in near-silence rather than on a music hit, resolving to a small dry stinger at the very end.
