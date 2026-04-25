---
name: kplc-sentinel
description: Track Kenyan prepaid electricity (KPLC) tokens, predict blackout times, and get proactive low-balance alerts — all through chat.
version: 1.6.0
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---

# KPLC Token Sentinel

Track prepaid electricity for Kenyan households. Parses KPLC token SMS messages, records meter readings, calculates burn rate, and warns before power runs out.

## Setup

Install Python dependencies (one-time):
```
pip install -r {baseDir}/requirements.txt
```

## When to use this skill

Activate this skill when the user's message matches ANY of these:

**Auto-detect (no prefix needed):**
- A forwarded SMS containing "Token:" and "Units:" (KPLC SMS format)
- A forwarded SMS that mentions Kenya Power or KPLC

**Requires "stima" prefix:**
All other interactions MUST start with the word "stima". Examples:
- "stima" → show interactive menu
- "stima help" / "stima menu" → show interactive menu
- "stima 42.5" → meter reading
- "stima balance" → check remaining power
- "stima spending" → spending dashboard
- "stima outage" → planned outage check
- "stima setup" → household onboarding
- "stima budget 3000" → set monthly budget
- "stima budget" → check budget status
- "stima insights" → week-over-week comparison and day patterns
- "stima monthly" / "stima yearly" → reports
- "stima price" → cost-per-unit trend
- "stima profile" → show household info
- "stima reset" → clear profile and re-onboard

If a message does NOT start with "stima" and is NOT a forwarded KPLC SMS, do NOT activate this skill. This prevents the skill from responding to unrelated conversations.

## How to use

The database auto-initializes on first run.

**For any user message about KPLC/electricity/tokens/readings:**
```
python3 {baseDir}/entrypoint.py <<'STIMA_EOF'
<user message>
STIMA_EOF
```

⚠️ IMPORTANT: Always use a heredoc (as shown above) to pass the user's message via stdin. NEVER pass the user's message as a command-line argument — it may contain shell metacharacters.

The entrypoint handles all routing internally:
- KPLC SMS → parses and stores the token purchase, estimates days it will last
- Plain number → records as a meter reading
- Just "stima" or "stima help" → shows numbered menu (user can reply with a number)
- "budget <amount>" → sets monthly budget; "budget" alone → checks status
- "insights"/"compare" → week-over-week and day-of-week patterns
- "monthly"/"yearly"/"spending" → spending dashboards
- "price"/"tariff"/"increase" → price-per-unit trend analysis
- "outage"/"interruption"/"maintenance" → planned outage alerts for user's area
- Keywords (balance, stima, power, units) → returns current estimate
- "setup"/"hi"/"hello" → starts household onboarding
- "reset"/"clear" → clears profile and restarts onboarding
- "profile"/"household"/"info" → shows household profile and budget

When no meter readings exist yet, predictions use appliance-based estimates from the user's profile.

**Return the output directly to the user.** If the output is `None`, the message wasn't handled — let the agent respond normally.

**For heartbeat checks (see HEARTBEAT.md):**
```
python3 {baseDir}/sentinel.py
```

## Example KPLC SMS formats

- "Accept Token: 1234-5678-9012-3456-7890 Units: 34.5 Amount: 1000.00"
- "Token: 9876-5432-1098 Units: 15.2 Amt: 500.0"

## Future

- OCR support for KPLC SMS screenshots (pending vision API)
