---
name: stats
description: "Show how reviewer findings and improvements are used: acted-on rate per rule, source, vote count, lens, and each improvement (I1–I8). Read-only. Use for /reviewer:stats."
---

# /reviewer:stats

Report how `/reviewer:review` findings are used in the current repo, from its
`.reviewer/log.jsonl`. Read-only: change nothing except appending `acted_on`
records to that log.

1. Mark findings acted on since the last review. Generate a UTC timestamp
   `YYYYMMDDTHHMMSSZ` and run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" acted-on --run-id stats-<UTC timestamp> --repo .
   ```

2. Print the stats. Pass `--last N` if the user asked for a number of runs:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reviewer.py" stats --repo .
   ```

   Show its output unchanged.

3. Then add at most three lines naming rules (from `## Rules`) or improvements
   (from `## Improvements`) with 10 or more shown findings and an acted-on rate
   under 20%, as candidates to rewrite or delete. The tracker exists so that
   what never lands gets removed. If none qualify, add nothing.

Do not edit any other file, rule or setting.
