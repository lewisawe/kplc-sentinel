# Heartbeat Schedule

## Every 6 Hours — Power Status Check
- Run `python3 sentinel.py` in the kplc-sentinel skill directory
- If any alerts are returned, send them to the user immediately
- LOW_BALANCE_WARNING alerts are urgent — send right away
- SPOT_CHECK_REQUEST alerts are gentle reminders
- PLANNED_OUTAGE alerts should be sent once when first detected

## Every Monday 8:00 AM — Weekly KPLC Summary
- Run `python3 -c "from sentinel import weekly_summary; s = weekly_summary(); print(s['message'])"` in the kplc-sentinel skill directory
- Send the full summary to the user
