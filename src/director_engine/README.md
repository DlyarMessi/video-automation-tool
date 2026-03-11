# Director Engine

This module represents the "director layer" of the video automation system.

Responsibilities:
- Apply editorial decisions to an existing timeline
- Enforce pacing, repetition, transition and ending rules
- Ensure stylistic consistency across videos

Non-responsibilities:
- No media picking
- No subtitle or audio generation
- No rendering logic
- No business or creative writing

Director Engine operates on:
- A normalized timeline (shots)
- A selected Director Profile

Output:
- A modified timeline with editorial decisions applied