---
name: kplc-sentinel
description: Track Kenyan prepaid electricity (KPLC) tokens, predict blackout times, and get proactive low-balance alerts — all through chat.
version: 1.3.3
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---

# KPLC Token Sentinel

Track prepaid electricity for Kenyan households. Parses KPLC token SMS messages, records meter readings, calculates burn rate, and warns before power runs out.

## When to use this skill

Activate this skill when the user's message matches ANY of these:

**Auto-detect (no prefix needed):**
- A forwarded SMS containing "Token:" and "Units:" (KPLC SMS format)
- A forwarded SMS that mentions Kenya Power or KPLC

**Requires "stima" prefix:**
All other interactions MUST start with the word "stima". Examples:
- "stima 42.5" → meter reading
- "stima balance" → check remaining power
- "stima spending" → spending dashboard
- "stima outage" → planned outage check
- "stima setup" → household onboarding
- "stima monthly" / "stima yearly" → reports
- "stima profile" → show household info

If a message does NOT start with "stima" and is NOT a forwarded KPLC SMS, do NOT activate this skill. This prevents the skill from responding to unrelated conversations.

## How to use

All commands run in this skill's directory. The database auto-initializes on first run.

**For any user message about KPLC/electricity/tokens/readings:**
```
python3 entrypoint.py "<user message>"
```

The entrypoint handles all routing internally:
- KPLC SMS → parses and stores the token purchase
- Plain number → records as a meter reading
- "monthly"/"yearly"/"spending" → spending dashboards
- "price"/"tariff"/"increase" → price-per-unit trend analysis
- "outage"/"interruption"/"maintenance" → planned outage alerts for user's area
- Keywords (balance, stima, power, units) → returns current estimate
- "setup"/"hi"/"hello" → starts household onboarding
- "profile"/"household"/"info" → shows household profile

**Return the output directly to the user.** If the output is `None`, the message wasn't handled — let the agent respond normally.

**For heartbeat checks (see HEARTBEAT.md):**
```
python3 sentinel.py
```

## Example KPLC SMS formats

- "Accept Token: 1234-5678-9012-3456-7890 Units: 34.5 Amount: 1000.00"
- "Token: 9876-5432-1098 Units: 15.2 Amt: 500.0"

## Future

- OCR support for KPLC SMS screenshots (pending vision API)
