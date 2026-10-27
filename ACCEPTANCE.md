# One real-rig acceptance sequence

Boot the LG VMs. The saved connection is reused; if the master IP changed, resolve the actual connection through lg-ssh-control. End Classroom through its own packaged command before starting Scout. Install with /usr/bin/python3; do not repeat model/provider setup.

Paste in Nara:

```text
Use scene-scout. Read its installed instructions and start the bundled
references/pune-waterside.json. Reuse saved connection and setup.
Use /usr/bin/python3 with HERMES_HOME=/home/immor/.hermes/profiles/liquid-galaxy-agent.
Display the shortlist and wait. Do not generate a different plan or inspect Python source.
```

Then use these messages, one at a time:

1. `Show A.` Earth should fly close to Khadakwasla's referenced area with tilt, not remain in the overview. The panel should name A and distinguish creative fit from documented evidence and unknowns. Confirm actual Earth visibility; transfer success alone is insufficient.
2. `Move closer, using a 500 metre range and 70 degree tilt.` Camera changes only. If local terrain or imagery is unclear, request a wider view or another heading. No generated detail is substituted for imagery.
3. `Save A with the note: Keep the water and infrastructure setting.` The left saved count and candidate decision update.
4. `Compare A and C.` A qualitative criteria comparison appears; the Earth overview includes those two candidates. No fictional score or road route.
5. `Replace B using the bundled references/replace-pashan.json; keep the brief, A and C unchanged.` Varasgaon occupies B's slot; A stays saved with its note, C is unchanged. This is a researched replacement of a real place, not an invented placeholder.
6. `Show the shortlist, then export the scouting report into my profile's scouting/exports/demo folder.` Verify the actual output directory. Open scouting-report.html in the computer's browser; it includes decisions, unknown permission, source dates and visit checks. The report is local, not remotely published.
7. `End scouting.` Central markers and SceneScout panels should disappear. Other applications' links/content must not be wiped. Repeat end once if desired; it should be safe.

Optional changed-brief check: use the same replacement with references/greener-brief.json in a fresh session. Retained candidates become FIT NEEDS REVIEW; saved choices remain saved. Nara may reassess them using existing source evidence. The helper must not silently declare that older candidates satisfy a new condition.

## Quick diagnostics without another LLM request

In Ubuntu:

```bash
export HERMES_HOME="$HOME/.hermes/profiles/liquid-galaxy-agent"
ENGINE="$HERMES_HOME/skills/liquid-galaxy/scene-scout/scripts/scout_engine.py"
/usr/bin/python3 "$ENGINE" context
/usr/bin/python3 "$ENGINE" continue
```

context reads local session state; continue retries its intended display. Neither researches a new place or calls a model API. If end was completed, start a new session instead. If another app controls the panels, avoid interleaving them.

LG prerequisites remain the working port-81 HTTP service, master Document id="master", matching single-slash master URLs and the rig's existing sync update mechanism. A rig loading-list failure cannot be repaired by changing candidate JSON. Do not overwrite master/myplaces files or clear every app's KML as a workaround. Diagnose through lg-ssh-control using read-only checks first.

## Short recording segment

Introduce SceneScout, show the brief and three real candidates, inspect one close tilted view, save A, replace B, show saved A retained, then export/end. Identify cuts if trimming network/research waits. Use face overlay and readable rig views. Do not call an offline panel preview a live rig run.
