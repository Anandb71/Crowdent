# Demo script (room)

This is the laptop half of the SIH26168 pitch. Rehearse it with the
network physically off.

## Before anyone speaks

1. `uv run stilldot demo` on mains power, sleep off.
2. Browser at `http://127.0.0.1:8000`, fullscreen.
3. Room walk already loaded. Do not start yet.
4. Backup: this same page on a second machine.

## The fifty seconds

1. Point at **GNSS DENIED** and **OFFLINE**.
2. Tap **START** while the story is "standing on the start marker".
3. Watch ZUPT lock, then the cyan track. The grey dashed line is the
   surveyed path. The red dotted line is naive double-integration.
4. Stop talking until the end marker. Read the drift metres out loud,
   then the percentage, then "the bar is ten percent".
5. Offer the phone walk if you have it. If not, say: "same engine,
   laptop fallback, measured number."

## If it misbehaves

1. Track jittery — keep walking, that is the filter.
2. Diverges — stand still, call the ZUPT lock.
3. Page dead — second machine, same build.
4. Both dead — `uv run stilldot run room_walk` and read the number.

Do not apologise. Do not play a video.
