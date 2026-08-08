---
name: general-analytics
description: General Analytics
---

You are analyzing a dataset. Follow general analyst best practices:
- Always clarify the grain of the data before aggregating (one row per what?)
- Use COUNT(DISTINCT x) for unique entities, COUNT(*) for rows
- Guard division with NULLIF to avoid divide-by-zero
- For time series, use DATE_TRUNC and always ORDER BY time
- Prefer GROUP BY over window functions unless a running/rolling value is needed
- Never invent numbers — compute everything from the returned rows