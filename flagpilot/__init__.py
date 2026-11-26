"""FlagPilot — a small CLI agent that turns a plain-English experiment idea
into a live Flagsmith experiment (Toggle Wars, Track 02).

The agent never writes anything to Flagsmith before the human approves the
plan, and every write step asks again. See README.md and the build spec in
~/workspace/research_notes/toggle-wars-build-spec.md.
"""

__version__ = "0.1.0"
