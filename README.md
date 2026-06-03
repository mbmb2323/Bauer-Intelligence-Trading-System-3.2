# Bauer-Intelligence-Trading-System-3.2

This repository now includes a local feature aggregation tool that can scan
multiple local Git repositories and produce a combined, daily-use wealth
management program blueprint.

## Generate the final program

```bash
python /tmp/workspace/mbmb2323/Bauer-Intelligence-Trading-System-3.2/wealth_management_program.py \
  --scan-root /tmp/workspace/mbmb2323 \
  --repo-name-contains Bauer \
  --repo-name-contains Raynman \
  --output /tmp/workspace/mbmb2323/Bauer-Intelligence-Trading-System-3.2/final_wealth_management_program.md
```

This creates a Markdown report with:
- per-repository extracted features
- consolidated feature list
- a daily routine layout (pre-market, market hours, and post-market)