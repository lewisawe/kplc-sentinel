import sys
import sqlite3
from init_db import init_db
from parser import parse_kplc_sms
from logic import (
    add_purchase, add_reading, predict_blackout,
    set_profile, get_profile, get_all_profile, is_onboarded,
    monthly_summary, yearly_summary, price_trend, check_outages,
    set_budget, check_budget, estimate_days, comparison_insights
)

try:
    init_db()
except sqlite3.Error as e:
    print(f"Database error during startup: {e}")
    sys.exit(1)

ONBOARDING_QUESTIONS = [
    ("occupants", "How many people live in your household?"),
    ("area", "What area/estate do you live in? (e.g. Kilimani, Umoja, Kitengela)"),
    ("appliances", "List your main electric appliances (e.g. fridge, TV, iron, water heater):"),
]

def handle_message(text):
    try:
        return _handle_message(text)
    except sqlite3.Error as e:
        return f"Something went wrong with the database: {e}. Try again shortly."

def _handle_message(text):
    text = text.strip()

    # Auto-detect forwarded KPLC SMS (no prefix needed)
    parsed = parse_kplc_sms(text)
    if parsed["success"]:
        if not add_purchase(parsed["token"], parsed["units"], parsed["amount"], text):
            return f"Oya! Token {parsed['token']} iko already. No duplicate added."
        remaining = predict_blackout()
        days = estimate_days(parsed["units"])
        response = f"Sawa! Token {parsed['token']} for {parsed['units']} units imeingia."
        if days:
            response += f" Hiyo itakudumu roughly {days:.1f} days based on your usage."
        if remaining:
            response += f" Total runway: ~{remaining:.1f} hours."
            response += _household_tip(remaining)
        budget_msg = check_budget()
        if budget_msg and ("⚠️" in budget_msg or "🚨" in budget_msg):
            response += f"\n{budget_msg}"
        return response

    # All other messages require 'stima' prefix (unless mid-onboarding)
    lower = text.lower()
    pending = get_profile("onboarding_step")
    if pending is None and not lower.startswith("stima"):
        return None  # Not for this skill

    # Strip 'stima' prefix
    if lower.startswith("stima"):
        text = text[5:].strip()
        lower = text.lower()

    # --- Onboarding flow ---
    if pending is not None:
        step = int(pending)
        if step < len(ONBOARDING_QUESTIONS):
            key = ONBOARDING_QUESTIONS[step][0]
            set_profile(key, text)
            step += 1
            if step < len(ONBOARDING_QUESTIONS):
                set_profile("onboarding_step", str(step))
                return ONBOARDING_QUESTIONS[step][1]
            else:
                set_profile("onboarding_step", None)
                profile = get_all_profile()
                return (
                    f"Nice! {profile.get('occupants')} people in {profile.get('area', 'your area')}, appliances: {profile.get('appliances')}. "
                    "I'll factor that into your estimates and watch for outages in your area. Now forward me your last KPLC token SMS or type your meter reading."
                )

    # Start onboarding if not done
    if lower in ("start", "setup", "hello", "hi", "hey"):
        if not is_onboarded():
            set_profile("onboarding_step", "0")
            return "Niaje! Welcome to KPLC Sentinel! Let's set up your household.\n" + ONBOARDING_QUESTIONS[0][1]
        return "Uko set up already! Forward a KPLC SMS or type your meter reading."

    # --- Manual reading ---
    try:
        balance = float(text)
        if balance < 0:
            return "Balance can't be negative. Check your meter and try again."
        add_reading(balance, "Manual entry")
        remaining = predict_blackout()
        response = f"Sawa, reading ya {balance} units imesave."
        if remaining:
            response += f" Kwa rate yako, stima itaisha in {remaining:.1f} hours."
            response += _household_tip(remaining)
        return response
    except ValueError:
        pass

    # --- Budget ---
    if lower.startswith("budget"):
        parts = text.split()
        if len(parts) >= 2:
            try:
                amt = float(parts[1].replace(",", ""))
                set_budget(amt)
                return f"Sawa! Monthly budget set to KES {amt:,.0f}. I'll warn you when you're getting close."
            except ValueError:
                pass
        return check_budget() or "Set a budget with: stima budget 3000"

    # --- Insights ---
    if any(w in lower for w in ("insight", "compare", "pattern", "trend")):
        insights = comparison_insights()
        return insights or "Bado hakuna enough data for insights. Keep sending readings!"

    # --- Spending & price queries ---
    if any(w in lower for w in ("monthly", "this month", "month spending")):
        return monthly_summary()
    if any(w in lower for w in ("yearly", "this year", "year spending", "annual")):
        return yearly_summary()
    if any(w in lower for w in ("spending", "spend", "cost", "how much have i")):
        return monthly_summary() + "\n\n" + price_trend()
    if any(w in lower for w in ("price", "tariff", "rate change", "increase", "decrease")):
        return price_trend()

    # --- Outage queries ---
    if any(w in lower for w in ("outage", "interruption", "maintenance", "scheduled", "blackout planned")):
        return check_outages()

    # --- General query ---
    if any(w in lower for w in ("token", "power", "balance", "stima", "units")):
        remaining = predict_blackout()
        if remaining:
            return f"Stima yako iko na roughly {remaining:.1f} hours remaining." + _household_tip(remaining)
        return "Bado sina enough data. Send me a meter reading (press 20# kwa meter) or forward your last KPLC SMS."

    if lower in ("profile", "household", "info"):
        profile = get_all_profile()
        if not profile:
            return "Huna profile bado. Type 'stima setup' to get started."
        budget_msg = check_budget()
        resp = f"Household: {profile.get('occupants', '?')} people in {profile.get('area', '?')}, appliances: {profile.get('appliances', '?')}"
        if budget_msg:
            resp += f"\n{budget_msg}"
        return resp

    return None  # Not handled by this skill


def _household_tip(hours_remaining):
    """Add a contextual tip based on household profile and urgency."""
    occupants = get_profile("occupants")
    appliances = get_profile("appliances")
    if not occupants:
        return ""
    if hours_remaining < 12 and appliances:
        heavy = [a.strip() for a in appliances.split(",") if any(
            h in a.lower() for h in ("heater", "iron", "oven", "geyser")
        )]
        if heavy:
            return f" Tip: avoid running {', '.join(heavy)} to stretch your units."
    return ""


if __name__ == "__main__":
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
    else:
        msg = sys.stdin.read().strip()
    if msg:
        print(handle_message(msg))
