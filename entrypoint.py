import sys
import sqlite3
from init_db import init_db
from parser import parse_kplc_sms
from logic import (
    add_purchase, add_reading, predict_blackout,
    set_profile, get_profile, get_all_profile, is_onboarded,
    monthly_summary, yearly_summary, price_trend, check_outages
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
    lower = text.lower()

    # --- Onboarding flow ---
    pending = get_profile("onboarding_step")
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
            return "Welcome to KPLC Sentinel! Let's set up your household.\n" + ONBOARDING_QUESTIONS[0][1]
        return "You're already set up! Forward a KPLC SMS or type your meter reading."

    # --- KPLC SMS parsing ---
    parsed = parse_kplc_sms(text)
    if parsed["success"]:
        if not add_purchase(parsed["token"], parsed["units"], parsed["amount"], text):
            return f"Token {parsed['token']} was already recorded. No duplicate added."
        remaining = predict_blackout()
        response = f"Got it! Token {parsed['token']} for {parsed['units']} units added."
        if remaining:
            response += f" I estimate you have about {remaining:.1f} hours of power left total."
            response += _household_tip(remaining)
        return response

    # --- Manual reading ---
    try:
        balance = float(text)
        if balance < 0:
            return "Balance can't be negative. Check your meter and try again."
        add_reading(balance, "Manual entry")
        remaining = predict_blackout()
        response = f"Reading of {balance} units saved."
        if remaining:
            response += f" At your current rate, you'll run out in {remaining:.1f} hours."
            response += _household_tip(remaining)
        return response
    except ValueError:
        pass

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
            return f"You have about {remaining:.1f} hours of power left." + _household_tip(remaining)
        return "I don't have enough data yet. Send me a meter reading (press 20#) or your last KPLC token SMS."

    if lower in ("profile", "household", "info"):
        profile = get_all_profile()
        if not profile:
            return "No profile yet. Type 'setup' to get started."
        return f"Household: {profile.get('occupants', '?')} people, appliances: {profile.get('appliances', '?')}"

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
        print(handle_message(msg))
