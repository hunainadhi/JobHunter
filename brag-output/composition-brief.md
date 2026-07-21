# Hyperframes Composition Brief: JobHunter

## Objective
Create a short launch-style brag video for JobHunter, a personal job-discovery pipeline.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: ~23 seconds

## Source Material
- Project root: `/Users/hunainadhikari/JobHunter`
- Primary files read: `README.md`, `board/app/page.tsx`, `board/app/globals.css`, `board/app/layout.tsx`, `board/components/job-board-table.tsx`, `board/components/search-filters.tsx`, `board/package.json`
- Product name: JobHunter
- Tagline / strongest claim: "Runs entirely on free-tier infrastructure at $0/month." / "16,700+ companies tracked."
- Key UI or visual moment to recreate: the live job board — header "Browse 16,187 open positions across Canada," the search/filter row (search input, date range, sort toggle, category/level/platform selects), and the results table (Apply button in brand blue, company/location/Remote pill, platform badge, posted date)
- Copy that must appear verbatim:
  - "Introducing JobHunter."
  - "Enterprise job-market intelligence."
  - "16,700+ companies tracked."
  - "13 job sources."
  - "Every posting scored 0-100 by AI."
  - "Browse 16,187 open positions across Canada" (board header, real copy pattern — count may render as a live-feeling number)
  - "Monthly infrastructure cost:" / "$0."
  - "Total customers:" / "1."
  - "JobHunter."
  - "Enterprise-grade infrastructure for a market of one."
  - "Still looking. Send openings."

## Creative Direction
- Tone preset: yc-parody
- Creative direction: fake Series A pitch deck for recruiting infrastructure that turns out to serve one candidate
- Interpretation: everything delivered as flat fact, no exclamation points, no winking — the absurdity is entirely in the gap between the scale of the infrastructure and the size of the userbase (one person). Hard cuts, minimal crossfades, sentence-case data-point typography, heavy-to-medium weight type, no decoration.
- Angle: play it as enterprise recruiting infrastructure bragging about its scale (~420 Lambda workers, 16,700+ companies, AI scoring) right up until the reveal that the total customer count is 1 and the monthly cost is $0 — a solo developer's job search dressed up as a funded startup.
- Hook: full-bleed "Introducing JobHunter." then smaller "Enterprise job-market intelligence." — dead serious, no joke yet.
- Outro / punchline: "JobHunter. Enterprise-grade infrastructure for a market of one." then smaller "Still looking. Send openings."
- Avoid:
  - Generic SaaS language ("streamline," "unlock," "empower")
  - Abstract filler visuals (no stock-photo style motion graphics)
  - Redesigning the board UI — recreate it faithfully to the real component (white cards, `#1447E6` blue Apply button, platform badges, green Remote pill)
  - Any triumphant/comedic sting — the "joke" sound design must stay as dry and restrained as the copy

## Visual Identity
- Background: `#FFFFFF` (light mode only — do not use the dark-mode palette)
- Text heading: `#111827`; body: `#4B5563`; subtle: `#6B7280`
- Accent / brand: `#1447E6` (buttons, links, active states), strong variant `#193CB8`
- Success/Remote pill: bg `#ECFDF5`, text `#065F46`, border `#A7F3D0`
- Card/border: `#E5E7EB`, subtle shadow `0 1px 2px 0 rgb(0 0 0 / 0.05)`
- Display font: Inter (Google Fonts) — fall back to a clean geometric sans if unavailable
- Body font: Inter
- Visual references from the project: the board's white card table with rounded 8px corners and hairline borders; the blue Apply button with its layered inset+drop shadow; the small pill badges for Remote and platform name; the plain sentence-case header line "Browse N open positions across Canada."

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract (7 scenes, ~23s total).

Scene summary:
1. Hook — 2.5s — "Introducing JobHunter." then "Enterprise job-market intelligence."
2. Architecture reveal — 3.5s — pipeline diagram assembles left to right: EventBridge → Orchestrator → ~420 Lambda workers → Supabase → Scoring Lambda (MiniMax-M3) → Dashboard
3. The numbers — 4s — 3 sequential stat lines: "16,700+ companies tracked." / "13 job sources." / "Every posting scored 0-100 by AI."
4. The board (real UI) — 4s — recreate the actual board: header, search bar with simulated typing ("AI engineer"), filter row, results table with Apply/Remote pill/platform badge
5. The turn — 3s — "Monthly infrastructure cost:" → "$0."
6. The punchline — 3s — "Total customers:" → "1."
7. Outro — 3s — "JobHunter." / "Enterprise-grade infrastructure for a market of one." / "Still looking. Send openings."

## Audio
- Audio role: sparse professional accents over a restrained, confident pitch-deck music bed
- Audio arc: flat and controlled through the hook, architecture, and stats scenes; continues under the board scene; ducks quietly under the two punchline lines ("$0.", "1.") so they land in near-silence; small dry stinger under the final logo card, then fades out
- Music: `assets/music/happy-beats-business-moves-vol-11-by-ende-dot-app.mp3` (warm, business-y, 114.84 BPM, already copied into `composition/assets/music/`)
- Music treatment: start at low-moderate volume (~0.25-0.3) under the hook, hold flat through scenes 2-4, duck to ~0.10-0.12 under scenes 5-6 (the two punchline beats), return briefly for the outro stinger, then fade out over the last ~1s
- Music cue guidance: bundled preset at `assets/music/cues/happy-beats-business-moves-vol-11-by-ende-dot-app.music-cues.json` (also `.md` summary alongside it). Strong cues available in-window: 1.60s, 3.70s, 5.80s, 6.34s, 8.96s, 9.50s, 12.65s, 17.91s, 22.65s. Suggested (optional, not mandatory) locks: the architecture-diagram reveal near 3.70s or 5.80s, and the board-UI cut near 8.96s or 9.50s — pick whichever falls closest to the actual scene-2/scene-4 transition once implemented. Do not force the punchline lines onto a strong cue — those should sit in the music dip, not on a hit.
- Audio-reactive treatment: none — this is a deadpan/yc-parody restraint piece; do not add RMS/frequency-reactive motion, it would undercut the flatness of the delivery
- Audio-coupled moments:
  - Scene 2 (architecture) — soft tick per pipeline box arriving, roughly beat-grid spaced if it lines up naturally, but prioritize legibility of the sequence over exact beat-snap
  - Scene 3 (stats) — one dry tick per stat line landing
  - Scene 4 (board) — soft keystroke ticks during the simulated "AI engineer" typing; one soft UI-settle sound when filtered results land
  - Scene 5 & 6 (turn/punchline) — music dip is the primary "sound design," no additional SFX needed on the numbers themselves
  - Scene 7 (outro) — one small, dry stinger under "JobHunter." landing — not triumphant, not a bell/fanfare, something closer to a soft confirm tone
- SFX selection guidance: choose 3-4 total SFX max across the whole video, favoring `interface/` or `ui/` click/drop families for the stat and pipeline ticks, `keyboard/keypress-*` (randomized) for the typing moment, and a restrained `interface/` or soft `impact/impactSoft_medium_*` (not `impactBell`) for the outro stinger — avoid anything that reads as celebratory or comedic
- SFX analysis guidance: consult `sfx-analysis.md` (bundled alongside the SFX library) and prefer low/medium high-frequency-risk files since this video repeats a similar tick sound multiple times
- Exact SFX choice: Hyperframes should choose exact filenames, timestamps, density, and volume based on the implemented animation
- Audio files: music and cue JSON/MD already copied into `brag-output/composition/assets/music/`; Hyperframes should copy any chosen SFX into `brag-output/composition/assets/sfx/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). `/brag` is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (the board UI in Scene 4 satisfies this — recreate it faithfully, not a generic mockup).
- Keep all text readable in the final render — respect the reading-time floors from `/brag`'s planning guidance (short label ~0.8s settled, full sentence ~0.3s/word).
- Keep the video within 15-25 seconds (target ~23s per the storyboard).
- Include the planned music/SFX layer — audio was not disabled and silence is not the creative choice here.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints; ignore cues that hurt readability, scene pacing, or the story. Use at most 1-3 strong cue locks in this 23s video.
- Use SFX to support motion/interaction, staying sparse per the yc-parody guidance (2-3 restrained cues is the target density, we've allowed up to 4 given the typing moment).
- Honor the planned music ducking under the two punchline lines and the fade at the very end.
- Do not add audio-reactive visuals for this tone — skip that step deliberately.
- Use local assets already copied into `composition/assets/`.
- Run `hyperframes check` before render — it is brag's single gate.
