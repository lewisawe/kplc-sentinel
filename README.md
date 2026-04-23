# KPLC Sentinel

An OpenClaw skill that tracks prepaid electricity for Kenyan households. Parses KPLC token SMS messages, predicts when you'll run out of power, tracks spending, detects price trends, and warns you about planned outages in your area.

## Requirements

- OpenClaw installed and running (`npm install -g openclaw@latest`)
- A connected messaging channel (WhatsApp, Telegram, etc.)
- Python 3 with `pdfplumber` (`pip install pdfplumber`)
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

# Install Python dependency for outage PDF parsing
pip install pdfplumber

# Start the gateway
openclaw gateway
```

Message your OpenClaw agent on WhatsApp and say "hi" to start onboarding.

## Usage

**Onboarding:** Say "hi" or "setup". The skill asks for your household size, area/estate, and appliances.

**Track a token purchase:** Forward your KPLC SMS to the chat. The skill parses the token, units, and amount automatically.

Example SMS formats it recognizes:
```
Accept Token: 1234-5678-9012-3456-7890 Units: 34.5 Amount: 1000.00
Token: 9876-5432-1098 Units: 15.2 Amt: 500.0
```

**Record a meter reading:** Press 20# on your meter and type the number (e.g. "42.5").

**Check your balance:** Ask "how much stima?" or "balance" or "power".

**Spending dashboards:** Say "monthly", "yearly", or "spending".

**Price trends:** Ask "price trend" or "tariff increase".

**Planned outages:** Ask "any outages?" — the skill scrapes KPLC's maintenance schedule PDF and checks for your area.

## How it works

The skill stores all data in a local SQLite database. Nothing leaves your machine.

- **Burn rate:** Weighted average across all meter readings, with exponential decay so recent usage matters more
- **Blackout prediction:** Current balance divided by burn rate
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
