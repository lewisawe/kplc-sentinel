# KPLC Sentinel

An OpenClaw skill that tracks prepaid electricity for Kenyan households. Parses KPLC token SMS messages, predicts when you'll run out of power, tracks spending, detects price trends, and warns you about planned outages in your area.

## Requirements

- OpenClaw installed and running (`npm install -g openclaw@latest`)
- A connected messaging channel (WhatsApp, Telegram, etc.)
- Python 3 with `pdfplumber` (`pip install -r requirements.txt`)
- An LLM API key (Anthropic, OpenAI, Google Gemini, etc.)

## Install

```
clawhub install kplc-sentinel
```

Or if you don't have the ClawHub CLI:

```
openclaw skills install kplc-sentinel
```

## Setup

If you don't have OpenClaw running yet:

```bash
# Install OpenClaw
npm install -g openclaw@latest

# Run the setup wizard (configures your LLM API key and daemon)
openclaw onboard

# Connect WhatsApp (scan QR code with your phone)
openclaw channels login --channel whatsapp

# Install the skill
openclaw skills install kplc-sentinel

# Install Python dependencies
pip install -r requirements.txt

# Start the gateway
openclaw gateway
```

Message your OpenClaw agent on WhatsApp and say "stima hi" to start onboarding.

## Usage

All commands use the `stima` prefix to prevent the skill from responding to unrelated conversations. Forwarded KPLC SMS messages are auto-detected without a prefix.

**Onboarding:** Say "stima hi" or "stima setup". The skill asks for your household size, area/estate, and appliances.

**Track a token purchase:** Forward your KPLC SMS to the chat. The skill parses the token, units, and amount automatically, and estimates how many days it will last.

Example SMS formats it recognizes:
```
Accept Token: 1234-5678-9012-3456-7890 Units: 34.5 Amount: 1000.00
Token: 9876-5432-1098 Units: 15.2 Amt: 500.0
```

**Record a meter reading:** Press 20# on your meter and type "stima 42.5".

**Check your balance:** "stima balance" or "stima power".

**Budget:** "stima budget 3000" to set, "stima budget" to check.

**Usage insights:** "stima insights" for week-over-week comparison and day patterns.

**Spending dashboards:** "stima monthly", "stima yearly", or "stima spending".

**Price trends:** "stima price" or "stima tariff".

**Planned outages:** "stima outage" — the skill scrapes KPLC's maintenance schedule PDF and checks for your area.

**Profile:** "stima profile" to see household info and budget status.

## How it works

The skill stores all data in a local SQLite database. Nothing leaves your machine except a single HTTPS request to `kplc.co.ke` to fetch the planned outage PDF.

- **Burn rate:** Weighted average across all meter readings, with exponential decay so recent usage matters more
- **Blackout prediction:** Current balance divided by burn rate
- **Token-to-days:** Estimates how long a new purchase will last based on burn rate
- **Budget tracking:** Set a monthly KES limit, warns at 80% and 100%
- **Usage insights:** Week-over-week comparison and heaviest/lightest day detection
- **Household tips:** When balance is low, suggests turning off heavy appliances from your profile
- **Outage alerts:** Downloads and parses KPLC's two-column maintenance PDF, matches against your area
- **Price trends:** Tracks cost-per-unit across months, shows percentage changes

## Heartbeat (proactive alerts)

The skill checks automatically via OpenClaw's heartbeat system:

- Every 6 hours: warns if you have less than 24 hours of power left, checks for planned outages
- Every 48 hours without a reading: asks for a spot check
- Weekly on Monday: sends a consumption and spending summary

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | Skill metadata and agent routing instructions |
| `SOUL.md` | Agent persona ("Stima") |
| `HEARTBEAT.md` | Scheduled proactive checks |
| `entrypoint.py` | Message handler |
| `sentinel.py` | Heartbeat alerts and weekly summary |
| `logic.py` | Burn rate, predictions, spending, outage parsing |
| `parser.py` | KPLC SMS regex parser |
| `init_db.py` | SQLite schema |
| `requirements.txt` | Python dependencies |
