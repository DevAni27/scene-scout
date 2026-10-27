# SceneScout plan contract — v1

Read `references/pune-waterside.json` for a complete real example. JSON is UTF-8, maximum 2 MB. Sources describe evidence actually read, not invented citations. Fields below are required unless marked optional.

## Top level

`schema_version: 1`, `brief`, `sources`, `candidates` (exactly three distinct candidates).

brief: title (85 chars), city (80), summary (300), origin `[longitude,latitude]`, radius_km (1–200), criteria (1–6 objects). Radius is straight-line, not driving distance. Each criterion has a unique lowercase/hyphen id (35 chars), label (80), priority `must|prefer|avoid`. In assessment, meets always means the candidate fits the user's intention: an avoid criterion is met when the unwanted condition is absent, not present.

sources: 1–30 objects with unique id (lowercase letters/numbers/hyphens, 50 chars), title (140), url (public HTTPS, 1400), accessed (`YYYY-MM-DD`), supports (380). Quote factual support accurately; a coordinate reference does not substantiate access or permission.

## Each candidate

- id: stable unique lowercase/hyphen identifier, 45 chars. Replacement uses a new ID.
- name: 85 chars. Prefer concise place names, not marketing promises.
- coordinates: `[longitude,latitude]`, inside the brief radius, latitudes limited to ±80 degrees in v1.
- coordinate_source_id: an existing source ID; coordinate_precision: `area|site`. An area centre is not an entrance or legal shooting position.
- creative_fit: 300 chars, explicitly an interpretation; tradeoffs: 260 chars.
- facts: 1–4 objects `{text (220 chars), source_ids: [existing IDs]}`.
- checks: 1–5 short concrete on-site checks (140 chars each).
- practical: access, facilities and permission, each `{status: "documented"|"unknown", text (180 chars), source_ids: [...]}`. Documented requires a source; unknown may have no source. Scope the assertion: a general road approach is not confirmed crew access.
- criteria: a mapping from EVERY brief criterion ID to `{status: "meets"|"partial"|"conflicts"|"unknown", reason (160 chars), source_ids: [...]}`. All non-unknown assessments need evidence references, but remain interpretations. No fabricated numeric fit score.
- camera (optional): range (250–3500 metres, default 350), tilt (50–78 degrees, default 75), heading (0–360, default 0), target (optional lon/lat within 2 km of candidate). These are artistic Earth viewpoints, not measured shooting positions. altitudeMode stays relativeToGround.
- photo (optional): `{path: ABSOLUTE_LOCAL_PATH, source_id: ID, credit: AUTHOR_AND_LICENSE (140 chars), usage: RIGHTS_NOTE (200 chars)}`. Local file ≤12 MB and ≤24 megapixels. PNG/JPEG readable by Pillow; helper stores a downscaled RGB copy. No network photo download occurs. Record full source/license information in source.supports and report fields.

Write concise prose. The renderer shrinks text within safe limits and refuses overflow before touching the rig. Long unbroken strings are unsuitable for panel prose. Full URLs belong in sources, not display text.

## Replacement

`{"candidate": {...complete candidate...}, "sources": [...new sources only...]}`. Existing source IDs may be reused by reference. Records with the same ID must be identical; assign a new ID to a revised source. Optional --brief-json supplies the full revised brief. All replacement criterion keys must match that revised brief.

Replacement archives the old candidate/decision/brief and preserves the other slots. Saved targets require explicit --allow-saved. A changed brief resets retained candidates' criteria to unknown and flags them for reassessment; it never silently changes their sourced facts or saved decisions.

Reassessment JSON permits only creative_fit, tradeoffs, criteria and checks. It uses existing evidence and cannot alter coordinates or insert facts/sources.

## Validation versus evidence

Validation checks shape, lengths, finite coordinate ranges, radius, camera limits, IDs and source references. It cannot establish source truth, current conditions, permission, visual resemblance, exact access, or whether a provided URL was actually read. Nara and the contributor remain responsible for that research.
