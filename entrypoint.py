import sys
import sqlite3
from init_db import init_db, get_db
from parser import parse_kplc_sms
from logic import (
    add_purchase, add_reading, predict_blackout,
    set_profile, get_profile, get_all_profile, is_onboarded,
    monthly_summary, yearly_summary, price_trend, check_outages,
    set_budget, check_budget, estimate_days, comparison_insights
)

ONBOARDING_QUESTIONS = [
    ("occupants", "How many people live in your household?"),
    ("area", "What area/estate do you live in? (e.g. Kilimani, Umoja, Kitengela)"),
    ("appliances", "List your main electric appliances (e.g. fridge, TV, iron, water heater):"),
]

# Command routing: prefix → handler.  Checked with startswith() so order matters
# (longer/more-specific prefixes first where needed).
_COMMANDS = None

def _get_commands():
    global _COMMANDS
    if _COMMANDS is None:
        _COMMANDS = [
            (("setup", "start", "hello", "hi", "hey"), _cmd_setup),
            (("budget",), _cmd_budget),
            (("insight", "compare", "pattern"), _cmd_insights),
            (("monthly", "this month"), _cmd_monthly),
            (("yearly", "this year", "annual"), _cmd_yearly),
            (("spending", "spend"), _cmd_spending),
            (("price", "tariff"), _cmd_price),
            (("outage", "interruption", "maintenance"), _cmd_outage),
            (("balance", "power", "units"), _cmd_balance),
            (("profile", "household", "info"), _cmd_profile),
        ]
    return _COMMANDS


def handle_message(text):
    try:
        return _handle_message(text)
    except sqlite3.Error as e:
        return f"Something went wrong with the database: {e}. Try again shortly."


MAX_INPUT_LEN = 5000
MAX_PROFILE_LEN = 200

def _handle_message(text):
    text = text.strip()[:MAX_INPUT_LEN]

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
        return _handle_onboarding(pending, text)

    # --- Manual reading (plain number) ---
    try:
        balance = float(text)
        return _cmd_reading(balance)
    except ValueError:
        pass

    # --- Command routing: match first word(s) against known prefixes ---
    for prefixes, handler in _get_commands():
        if any(lower == p or lower.startswith(p + " ") for p in prefixes):
            return handler(text, lower)

    return None  # Not handled by this skill


# ── command handlers ─────────────────────────────────────────────────────

def _handle_onboarding(pending, text):
    step = int(pending)
    if step < len(ONBOARDING_QUESTIONS):
        key = ONBOARDING_QUESTIONS[step][0]
        set_profile(key, text[:MAX_PROFILE_LEN])
        step += 1
        if step < len(ONBOARDING_QUESTIONS):
            set_profile("onboarding_step", str(step))
            return ONBOARDING_QUESTIONS[step][1]
        else:
            set_profile("onboarding_step", None)
            profile = get_all_profile()
            return (
                f"Nice! {profile.get('occupants')} people in {profile.get('area', 'your area')}, "
                f"appliances: {profile.get('appliances')}. "
                "I'll factor that into your estimates and watch for outages in your area. "
                "Now forward me your last KPLC token SMS or type your meter reading."
            )


def _cmd_reading(balance):
    if balance < 0:
        return "Balance can't be negative. Check your meter and try again."
    try:
        add_reading(balance, "Manual entry")
    except ValueError as e:
        return str(e)
    remaining = predict_blackout()
    response = f"Sawa, reading ya {balance} units imesave."
    if remaining:
        response += f" Kwa rate yako, stima itaisha in {remaining:.1f} hours."
        response += _household_tip(remaining)
    return response


def _cmd_setup(text, lower):
    if not is_onboarded():
        set_profile("onboarding_step", "0")
        return "Niaje! Welcome to KPLC Sentinel! Let's set up your household.\n" + ONBOARDING_QUESTIONS[0][1]
    return "Uko set up already! Forward a KPLC SMS or type your meter reading."


def _cmd_budget(text, lower):
    parts = text.split()
    if len(parts) >= 2:
        try:
            amt = float(parts[1].replace(",", ""))
            set_budget(amt)
            return f"Sawa! Monthly budget set to KES {amt:,.0f}. I'll warn you when you're getting close."
        except ValueError:
            pass
    return check_budget() or "Set a budget with: stima budget 3000"


def _cmd_insights(text, lower):
    return comparison_insights() or "Bado hakuna enough data for insights. Keep sending readings!"


def _cmd_monthly(text, lower):
    return monthly_summary()


def _cmd_yearly(text, lower):
    return yearly_summary()


def _cmd_spending(text, lower):
    return monthly_summary() + "\n\n" + price_trend()


def _cmd_price(text, lower):
    return price_trend()


def _cmd_outage(text, lower):
    return check_outages()


def _cmd_balance(text, lower):
    remaining = predict_blackout()
    if remaining:
        return f"Stima yako iko na roughly {remaining:.1f} hours remaining." + _household_tip(remaining)
    return "Bado sina enough data. Send me a meter reading (press 20# kwa meter) or forward your last KPLC SMS."


def _cmd_profile(text, lower):
    profile = get_all_profile()
    if not profile:
        return "Huna profile bado. Type 'stima setup' to get started."
    budget_msg = check_budget()
    resp = f"Household: {profile.get('occupants', '?')} people in {profile.get('area', '?')}, appliances: {profile.get('appliances', '?')}"
    if budget_msg:
        resp += f"\n{budget_msg}"
    return resp


# ── helpers ──────────────────────────────────────────────────────────────

_HEAVY_APPLIANCES = {"heater", "iron", "oven", "geyser", "water heater", "boiler"}

def _household_tip(hours_remaining):
    """Add a contextual tip based on household profile and urgency."""
    if hours_remaining >= 12:
        return ""
    appliances = get_profile("appliances")
    if not appliances:
        return ""
    # Normalize: split on commas, slashes, "and", or multiple spaces
    import re
    items = [a.strip().lower() for a in re.split(r'[,/]|\band\b', appliances) if a.strip()]
    heavy = [a for a in items if any(h in a for h in _HEAVY_APPLIANCES)]
    if heavy:
        return f" Tip: avoid running {', '.join(heavy)} to stretch your units."
    return ""


if __name__ == "__main__":
    init_db()
    msg = sys.stdin.read().strip()
    if msg:
        result = handle_message(msg)
        if result:
            print(result)
