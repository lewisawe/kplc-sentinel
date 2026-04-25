import sys
import logging
import sqlite3
from init_db import init_db, get_db

logger = logging.getLogger(__name__)
from parser import parse_kplc_sms
from logic import (
    add_purchase, add_reading, predict_blackout,
    set_profile, get_profile, get_all_profile, is_onboarded, reset_profile,
    monthly_summary, yearly_summary, price_trend, check_outages,
    set_budget, check_budget, estimate_days, comparison_insights
)

MENU_OPTIONS = [
    ("balance", "Check remaining power"),
    ("budget", "Budget status"),
    ("insights", "Week-over-week usage"),
    ("monthly", "This month's summary"),
    ("yearly", "Yearly summary"),
    ("spending", "Spending + price trend"),
    ("price", "Cost-per-unit trend"),
    ("outage", "Planned outages in your area"),
    ("profile", "Household info"),
    ("setup", "Onboard / re-setup"),
]

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
            (("reset", "clear"), _cmd_reset),
            (("setup", "start", "hello", "hi", "hey"), _cmd_setup),
            (("help", "menu", "?"), lambda t, l: _cmd_menu()),
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
    except sqlite3.Error:
        logger.exception("Database error")
        return "Something went wrong with the database. Try again shortly."


MAX_INPUT_LEN = 5000
MAX_PROFILE_LEN = 200

def _handle_message(text):
    text = text.strip()[:MAX_INPUT_LEN]

    # Auto-detect forwarded KPLC SMS (no prefix needed)
    parsed = parse_kplc_sms(text)
    if parsed["success"]:
        if not add_purchase(parsed["token"], parsed["units"], parsed["amount"], text):
            return f"Oya! Token {parsed['token_display']} iko already. No duplicate added."
        remaining = predict_blackout()
        days = estimate_days(parsed["units"])
        response = f"Sawa! Token {parsed['token_display']} for {parsed['units']} units imeingia."
        if days:
            from logic import calculate_burn_rate
            source = "" if calculate_burn_rate() else " (estimated from your appliances)"
            response += f" Hiyo itakudumu roughly {days:.1f} days{source}."
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

    # --- Empty command = show menu ---
    if not text:
        return _cmd_menu()

    # --- Menu number selection ---
    if lower.isdigit() and get_profile("menu_pending"):
        choice = int(lower)
        if 1 <= choice <= len(MENU_OPTIONS):
            set_profile("menu_pending", None)
            cmd = MENU_OPTIONS[choice - 1][0]
            return _handle_message(f"stima {cmd}")
        set_profile("menu_pending", None)

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

def _cmd_menu():
    set_profile("menu_pending", "1")
    lines = ["⚡ *KPLC Sentinel*", "", "Reply with a number or type a command:", ""]
    for i, (_, label) in enumerate(MENU_OPTIONS, 1):
        lines.append(f"  {i}. {label}")
    lines.append("")
    lines.append("You can also forward a KPLC SMS or type *stima <reading>*.")
    return "\n".join(lines)

def _handle_onboarding(pending, text):
    try:
        step = int(pending)
    except (ValueError, TypeError):
        set_profile("onboarding_step", None)
        return "Something went wrong with setup. Type 'stima setup' to start again."
    if step < 0 or step >= len(ONBOARDING_QUESTIONS):
        set_profile("onboarding_step", None)
        return "Something went wrong with setup. Type 'stima setup' to start again."
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
            f"Nice! {_sanitize(profile.get('occupants'))} people in {_sanitize(profile.get('area', 'your area'))}, "
            f"appliances: {_sanitize(profile.get('appliances'))}. "
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


def _cmd_reset(text, lower):
    reset_profile()
    set_profile("onboarding_step", "0")
    return "Profile cleared! Let's set up fresh.\n" + ONBOARDING_QUESTIONS[0][1]


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
        from logic import calculate_burn_rate
        source = "" if calculate_burn_rate() else " (estimated from your appliances)"
        return f"Stima yako iko na roughly {remaining:.1f} hours remaining{source}." + _household_tip(remaining)
    return "Bado sina enough data. Send me a meter reading (press 20# kwa meter) or forward your last KPLC SMS."


def _cmd_profile(text, lower):
    profile = get_all_profile()
    if not profile:
        return "Huna profile bado. Type 'stima setup' to get started."
    budget_msg = check_budget()
    resp = f"Household: {_sanitize(profile.get('occupants', '?'))} people in {_sanitize(profile.get('area', '?'))}, appliances: {_sanitize(profile.get('appliances', '?'))}"
    if budget_msg:
        resp += f"\n{budget_msg}"
    return resp


# ── helpers ──────────────────────────────────────────────────────────────

_HEAVY_APPLIANCES = {"heater", "iron", "oven", "geyser", "water heater", "boiler"}


def _sanitize(text):
    """Strip markdown/HTML formatting to prevent injection via chat channels."""
    if not text:
        return text
    import re
    text = re.sub(r'[*_~`<>\[\]()]', '', text)
    # Strip control chars except newline
    return ''.join(c for c in text if c == '\n' or (c.isprintable() and ord(c) >= 32))

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
