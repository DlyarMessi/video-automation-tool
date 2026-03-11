# Creative Layer

The Creative layer exists to bridge human creativity and machine execution.

Goals:
- Allow humans and AI to write scripts that are easy to read and review
- Decouple creative intent from technical execution
- Provide a stable input format for the Director Engine and video pipeline

This layer does NOT:
- Control editing rules
- Control pacing or transitions
- Perform rendering

Flow:
Creative Script (human / AI)
→ Compiler
→ Production Script (machine)