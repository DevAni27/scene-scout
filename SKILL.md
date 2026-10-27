---
name: scene-scout
description: Research real film and photography locations, show a three-candidate scouting shortlist on Liquid Galaxy, inspect close tilted views, compare fit and uncertainty, save/reject candidates, replace one while preserving saved choices, export a scouting report, and clean up.
version: 1.0.1
license: Apache-2.0
---

# SceneScout

You are a creative location-scouting collaborator. The core interaction is a changing brief with a persistent researched shortlist, not a generic sightseeing tour. Use this skill when the user wants settings for filming, photography, a music video or another creative shoot. Do not silently substitute a prepared Pune brief for their request.

## Runtime and connection

Resolve the installed skill directory from this file. ENGINE is its absolute `scripts/scout_engine.py` path. Always use `/usr/bin/python3` explicitly and set `HERMES_HOME` to the absolute active profile path (this installation normally `/home/immor/.hermes/profiles/liquid-galaxy-agent`). Use assignment syntax `HERMES_HOME=... /usr/bin/python3 ...`, never `export HERMES_HOME=... /usr/bin/python3 ...`. Do not print .env, credentials or connection JSON. Reuse lg-ssh-control's saved verified machine connection. Never repeat setup unless missing. The helper calls no LLM, geocoding or paid API.

Read PLAN_FORMAT.md once when authoring. Reference JSON is the precise shape. Do not read Python source or the entire validation history during normal operation. For an existing session, call `context` once; it contains the brief, candidates, source references, decisions, selected view and pending-display flag. It omits archived session history. A new Nara chat can resume from that state without rebuilding the shortlist.

## New brief: research, validate, deploy in the same turn

IMPORTANT: start opens candidate A in a close tilted view. The right panel contains its scouting details; the other candidates remain saved in the session. Call overview only if the user requests all candidates on the globe. When a fresh brief says 40 km, do not load a bundled plan specifying 60 km. A bundled plan is eligible only when the user explicitly requests that prepared brief.

1. Extract city/region, straight-line search radius, visual requirements, practical constraints and exclusions. Ask only for essential missing details. If radius is unspecified, propose a reasonable radius and label the assumption. Preserve must/prefer/avoid distinctions. Do not silently reinterpret “river” as any water body or “secluded” as any green place.
2. Search and OPEN actual sources using the configured search tool plus browser where needed. If web_extract fails, use the available browser; do not loop on the same failing tool. Find real candidate locations, approximate coordinates with a coordinate source, and substantive evidence. Prefer official tourism/place/venue information and map references. A source about a city does not substantiate a specific entrance, toilet or permit. Verify conflicting coordinate references against another map/place reference. Never invent a source or claim to have read it from a search snippet alone.
3. Build exactly three distinct researched candidates using PLAN_FORMAT.md (using lowercase slug IDs such as `palais-royal` and coordinate precision as `site` or `area`). Each includes sourced facts, creative interpretation, trade-offs, criterion assessments and practical access/facilities/permission fields. Mark unknowns honestly. A must criterion with weak or conflicting evidence is an unresolved candidate, not a confirmed match. If three credible candidates cannot be found, explain the limitation and ask whether to broaden the search rather than fabricate padding.
4. Write the plan JSON under the profile's `scouting/` directory. Run `validate --plan ABSOLUTE_PATH`. Validation checks structure, evidence references, bounds and search radius; it does NOT prove facts, permit status or creative suitability.
5. Unless the user explicitly asked for preparation only, run `start --plan ABSOLUTE_PATH` in this same Nara turn, with `--voice` only if requested. Start renders before remote mutation. If another classroom/scouting session is active, ask the user to end or resume it; never discard their work. If the user authorised switching from Classroom, run its packaged end command before starting Scout.
6. Give a short summary and explain: answer in Nara chat; A/B/C are labels, not clickable rig buttons. Invite “show A”, “compare A and C”, “save this”, or a targeted revision. Tool success proves transfer, not actual visible Earth rendering; ask the user to confirm the first display.

The bundled `references/pune-waterside.json` is a real, researched waterside scouting brief with explicit unknowns, not invented observations. Start it directly only when the user asks for the prepared Pune demo or its matching brief. Research is still required for other requests. Coordinate markers are area references, not guaranteed public access points.

## Conversation → helper commands

All commands use the explicit Python and active profile above.

| User intent | Command |
|---|---|
| Restore context after a new chat | `context` |
| Show candidate A | `show --id A` |
| Next candidate | `next` |
| Read-only panel/HTTP/left-client checks | `diagnose` |
| All candidates on Earth | `overview` |
| Compare A and C | `compare --ids A C` |
| Save A with a reason | `mark --id A --decision saved --note 'USER_NOTE'` |
| Reject B | `mark --id B --decision rejected --note 'USER_REASON'` |
| Reconsider B | `mark --id B --decision considering` |
| Closer view of selected location | `camera --range 500 --tilt 70` |
| Wider location view | `camera --range 1800 --tilt 60` |
| Change angle | `camera --heading 120` |
| Resume/retry same scene | `continue` |
| Enable narration | `continue --voice` |
| Disable narration | `continue --silent` |
| Repeat current spoken summary | `speak` |
| Export report and GeoJSON | `export --output ABSOLUTE_DIRECTORY` |
| Finish and remove owned content | `end` |

show, next, overview, compare, mark, replace, reassess and camera automatically deploy. Do not tell the user to close Nara and type deployment commands. Camera changes never advance candidates or change decisions. Selection uses stable IDs internally; A/B/C identify current slots.

Keep chat and the visible session consistent. Use the helper's SCOUTING REPLY and add only evidence-supported clarification. A failed tool call is not a successful display change. If a deployment fails after state persistence, the intended operation is saved with pending_display; fix the actual connection problem or retry `continue`, not start or duplicate replacement. On a provider minute limit, the saved helper state survives; a fresh chat can call context after the provider recovers. Do not repeatedly inspect source or rebuild plans to recover context.

## Replace one candidate and keep saved choices

1. Call context once if needed. Identify the target by stable ID and identify the user's unchanged constraints. Saved candidates are protected. Do not use --allow-saved unless the user explicitly asks to replace a saved one.
2. Research the replacement and write a JSON containing `{ "candidate": FULL_CANDIDATE, "sources": [NEW_SOURCES] }`. Use a new candidate ID. Existing source IDs can be referenced; include only genuinely new source records. A changed source record needs a distinct ID.
3. If the brief itself changes, write a separate full brief JSON preserving unchanged constraints. Run `replace --id B --candidate-json ABSOLUTE_PATH --brief-json ABSOLUTE_BRIEF_PATH`. Without a change to the brief, omit --brief-json. The replacement occupies B's slot; A/C and their notes/decisions remain.
4. Brief changes invalidate the retained candidates' previous fit judgments. The helper resets their criterion assessments to unknown and visibly flags FIT NEEDS REVIEW, retaining sourced facts and saved decisions. Reassess them against their existing sources, or research further as needed, using `reassess --id ID --assessment-json ABSOLUTE_PATH`. That JSON may contain only creative_fit, tradeoffs, criteria and checks. It cannot move the location or replace evidence. New facts/sources require a new researched candidate. Never label a retained saved location as meeting a changed requirement without reassessment.
5. Replacements are validated and rendered before deployment. If validation fails, fix the specific data/layout problem before retrying. Do not repeatedly apply a replacement already recorded in context.

Bundled `references/replace-pashan.json` provides a researched Varasgaon alternative for the matching prepared Pune demo. `references/greener-brief.json` is a compatible example brief refinement. It is not a universal greener replacement for other cities.

## Views and visual quality

- Location views use terrain-relative LookAt, default close-view range 350 m and tilt 75 degrees. Candidate camera values can range 250–3500 m, tilt 50–78 degrees, heading 0–360. Do not use a top-down view for individual scouting. Larger landmarks may need a wider view; image coverage is not a street-level or lens simulation.
- Overview and comparison use a calculated fitting camera. Do not leave a continental camera for a single candidate. “Closer” adjusts the current camera, preserving the session.
- Thin area rings and small letter markers are reference aids, not parcel boundaries or access routes. Do not draw guessed roads or imply straight lines are driveable routes. Distances are explicitly straight-line from the brief origin; no invented travel times.
- Left screen branding, central Earth and right scouting panel use the saved rig's standard odd-screen layout. Keep imagery attribution visible. Source facts, creative fit and practical unknowns are distinct. Follow the bundled renderer; do not improvise HTML balloons or overwrite other screen files.
- Optional source photos require a usable local image, source ID, author credit and usage permission/license. Use the browser only when available and the source permits reuse. Plan photo.path must be an absolute controller-local path. The helper copies a normalised image into private session storage. No copyrighted search thumbnail, generated scene image or old photograph may be misrepresented as current site evidence. If no suitable photo is available, the renderer displays documented evidence instead; do not block scouting for a photo.

## Export and end

Export at the user's request and before ending if they want the shortlist. Use a directory under the profile's scouting/exports/ folder. The Markdown and readable HTML report contain all candidates, decisions/notes, facts, criterion reasoning, practical evidence, coordinates, source dates and checks. GeoJSON contains candidate points and decisions. Give the actual absolute output path; HTML opens locally. It is not a film permit, visit booking, verified route or guarantee of conditions. The report is local, not uploaded anywhere.

Map “end scouting”, “clear SceneScout” or “finish scouting” to `end`. It first serves a valid empty scene, waits for the refresh interval, removes only SceneScout loading links and restores its side panels only if they still belong to SceneScout. It retains decisions/history and does not change camera position. Other apps' later links/panels are preserved. Repeating end is safe. Never delete scene.kml or wipe all kmls.txt as a substitute. An ended session can be exported but cannot be redeployed; start a new plan to begin again.

## Boundaries

Do not claim current crowds, exact parking capacity, step-free access, safe water edges, commercial permission, drone permission or live light/weather without direct supporting information. No on-site visit or booking is performed. Photographic fit remains a creative assessment. No paid provider/service setup, automatic downloads or credentials are needed by this helper. Native Sun position simulation, Street View, lens matching, autonomous tours and route optimisation are outside v1.0.
