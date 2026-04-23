import sqlite3
import os
import calendar
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "kplc.sqlite")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def add_purchase(token, units, amount, raw_text):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM purchases WHERE token = ?", (token,))
    if cursor.fetchone():
        conn.close()
        return False  # duplicate
    cursor.execute(
        "INSERT INTO purchases (token, units, amount, raw_text) VALUES (?, ?, ?, ?)",
        (token, units, amount, raw_text)
    )
    conn.commit()
    conn.close()
    return True

def add_reading(balance, notes=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO readings (balance, notes) VALUES (?, ?)",
        (balance, notes)
    )
    conn.commit()
    conn.close()

def calculate_burn_rate():
    """Weighted average burn rate across all consecutive reading pairs.
    Recent intervals are weighted exponentially higher (decay factor 0.7)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT timestamp, balance FROM readings ORDER BY timestamp ASC")
    readings = cursor.fetchall()

    if len(readings) < 2:
        conn.close()
        return None

    fmt = "%Y-%m-%d %H:%M:%S"
    rates = []

    for i in range(1, len(readings)):
        old_ts, old_bal = readings[i - 1]
        new_ts, new_bal = readings[i]

        t_old = datetime.strptime(old_ts, fmt)
        t_new = datetime.strptime(new_ts, fmt)
        hours = (t_new - t_old).total_seconds() / 3600.0

        if hours <= 0:
            continue

        # Account for any purchases between these two readings
        cursor.execute(
            "SELECT COALESCE(SUM(units), 0) FROM purchases WHERE timestamp >= ? AND timestamp <= ?",
            (old_ts, new_ts)
        )
        purchased = cursor.fetchone()[0]

        burned = (old_bal + purchased) - new_bal
        if burned < 0:
            continue

        rates.append(burned / hours)

    conn.close()

    if not rates:
        return None

    # Exponential weighting: most recent interval gets weight 1, previous gets 0.7, etc.
    decay = 0.7
    total_weight = 0.0
    weighted_sum = 0.0
    for i, rate in enumerate(rates):
        w = decay ** (len(rates) - 1 - i)
        weighted_sum += rate * w
        total_weight += w

    return weighted_sum / total_weight

def set_profile(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO profile (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value)
    )
    conn.commit()
    conn.close()

def get_profile(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM profile WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_profile():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM profile")
    rows = cursor.fetchall()
    conn.close()
    return dict(rows)

def is_onboarded():
    return get_profile("occupants") is not None

def monthly_summary(year=None, month=None):
    """Spending and consumption summary for a given month."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    start = f"{year}-{month:02d}-01 00:00:00"
    if month == 12:
        end = f"{year + 1}-01-01 00:00:00"
    else:
        end = f"{year}-{month + 1:02d}-01 00:00:00"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT COALESCE(SUM(units),0), COALESCE(SUM(amount),0), COUNT(*) FROM purchases WHERE timestamp >= ? AND timestamp < ?",
        (start, end)
    )
    units, spent, count = c.fetchone()
    cost_per_unit = spent / units if units > 0 else 0
    conn.close()

    month_name = calendar.month_name[month]
    lines = [f"📅 *{month_name} {year} KPLC Summary*", ""]
    lines.append(f"Top-ups: {count}")
    lines.append(f"Units bought: {units:.1f}")
    lines.append(f"Total spent: KES {spent:,.0f}")
    if units > 0:
        lines.append(f"Avg cost/unit: KES {cost_per_unit:.2f}")
    return "\n".join(lines)

def yearly_summary(year=None):
    """Spending and consumption summary for a given year, broken down by month."""
    year = year or datetime.now().year
    start = f"{year}-01-01 00:00:00"
    end = f"{year + 1}-01-01 00:00:00"

    conn = get_db_connection()
    c = conn.cursor()

    # Totals
    c.execute(
        "SELECT COALESCE(SUM(units),0), COALESCE(SUM(amount),0), COUNT(*) FROM purchases WHERE timestamp >= ? AND timestamp < ?",
        (start, end)
    )
    total_units, total_spent, total_count = c.fetchone()

    # Monthly breakdown
    c.execute(
        "SELECT strftime('%m', timestamp) as m, SUM(units), SUM(amount), COUNT(*) "
        "FROM purchases WHERE timestamp >= ? AND timestamp < ? GROUP BY m ORDER BY m",
        (start, end)
    )
    months = c.fetchall()
    conn.close()

    lines = [f"📊 *{year} KPLC Yearly Summary*", ""]
    lines.append(f"Total: {total_count} top-ups, {total_units:.0f} units, KES {total_spent:,.0f}")
    if total_units > 0:
        lines.append(f"Avg cost/unit: KES {total_spent / total_units:.2f}")
    lines.append("")

    for m, units, spent, count in months:
        mn = calendar.month_abbr[int(m)]
        lines.append(f"  {mn}: {units:.0f} units, KES {spent:,.0f} ({count} top-ups)")

    return "\n".join(lines)

def price_trend():
    """Detect price-per-unit trend across purchases."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT strftime('%Y-%m', timestamp) as m, SUM(amount), SUM(units) "
        "FROM purchases WHERE units > 0 AND amount > 0 GROUP BY m ORDER BY m"
    )
    rows = c.fetchall()
    conn.close()

    if len(rows) < 1:
        return "Not enough purchase data to detect price trends yet."

    lines = ["💰 *KPLC Price Trend (cost per unit)*", ""]
    prev_cpu = None
    for m, amount, units in rows:
        cpu = amount / units
        indicator = ""
        if prev_cpu is not None:
            diff = cpu - prev_cpu
            pct = (diff / prev_cpu) * 100
            if abs(pct) < 1:
                indicator = " →"
            elif diff > 0:
                indicator = f" ↑ +{pct:.1f}%"
            else:
                indicator = f" ↓ {pct:.1f}%"
        lines.append(f"  {m}: KES {cpu:.2f}/unit{indicator}")
        prev_cpu = cpu

    # Overall trend
    if len(rows) >= 2:
        first_cpu = rows[0][1] / rows[0][2]
        last_cpu = rows[-1][1] / rows[-1][2]
        overall = ((last_cpu - first_cpu) / first_cpu) * 100
        lines.append("")
        if abs(overall) < 1:
            lines.append("Overall: prices stable")
        elif overall > 0:
            lines.append(f"Overall: prices UP {overall:.1f}% since {rows[0][0]}")
        else:
            lines.append(f"Overall: prices DOWN {abs(overall):.1f}% since {rows[0][0]}")

    return "\n".join(lines)

KPLC_SCHEDULE_URL = "https://www.kplc.co.ke/storage/01KPWN6FYWZ5Q9MKXJDHW7EG1A.pdf"

def _fetch_outage_schedule():
    """Download and parse the KPLC Power Maintenance Notice PDF."""
    import urllib.request, tempfile, re
    try:
        import pdfplumber
    except ImportError:
        return []

    try:
        pdf_path = os.path.join(tempfile.gettempdir(), "kplc_schedule.pdf")
        urllib.request.urlretrieve(KPLC_SCHEDULE_URL, pdf_path)

        # Extract text from each column separately (PDF is two-column)
        chunks = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                w = page.width
                for crop in [(0, 0, w / 2, page.height), (w / 2, 0, w, page.height)]:
                    text = page.crop(crop).extract_text() or ""
                    chunks.append(text)

        full_text = "\n".join(chunks)

        # Parse AREA / DATE / TIME blocks (case-insensitive DATE for inconsistent PDFs)
        pattern = r'AREA:\s*(.+?)\s*\n[Dd][Aa][Tt][Ee]:\s*(\w+ \d{2}\.\d{2}\.\d{4})\s*TIME:\s*(.+?)[\n\r]'
        raw = re.findall(pattern, full_text)

        results = []
        for area_raw, date_raw, time_raw in raw:
            area = area_raw.strip().title()
            # Strip "Part Of" prefix for matching but keep for display
            area_clean = re.sub(r'^Part Of\s+', '', area)

            # Format date
            day_name, date_str = date_raw.split(" ", 1)
            parts = date_str.split(".")
            day = int(parts[0])
            month_num = int(parts[1])
            month_name = calendar.month_name[month_num]
            suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
            date_fmt = f"{day_name} {day}{suffix} {month_name}"

            # Format time
            time_clean = re.sub(r'(\d+)\.(\d+)', r'\1:\2', time_raw.strip())
            time_clean = time_clean.replace("A.M.", "AM").replace("P.M.", "PM")
            time_clean = time_clean.replace("A.M", "AM").replace("P.M", "PM")

            results.append({"area": area, "area_clean": area_clean, "date": date_fmt, "time": time_clean})
        return results
    except Exception:
        return []

def check_outages(area=None):
    """Check for planned outages in the user's area."""
    area = area or get_profile("area")
    if not area:
        return "I don't know your area yet. Type 'setup' to set your location so I can check for outages."

    scheduled = _fetch_outage_schedule()
    if not scheduled:
        return "Couldn't fetch the KPLC maintenance schedule right now. Try again later."

    area_lower = area.lower()
    area_words = area_lower.split()
    matches = [s for s in scheduled
               if area_lower in s["area_clean"].lower()
               or s["area_clean"].lower() in area_lower
               or any(w in s["area_clean"].lower() for w in area_words if len(w) > 3)]

    if not matches:
        return f"No planned outages for {area} this week. You're clear!"

    lines = [f"⚠️ *Planned outages near {area}:*", ""]
    for m in matches:
        lines.append(f"📅 {m['date']}, {m['time']}")
        lines.append("")
    lines.append("Charge your devices and plan accordingly.")
    return "\n".join(lines)

def predict_blackout():
    burn_rate = calculate_burn_rate()
    if not burn_rate or burn_rate == 0:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM readings ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row or row[0] is None:
        return None

    return row[0] / burn_rate


def estimate_days(units):
    """Estimate how many days a token purchase will last based on burn rate."""
    burn_rate = calculate_burn_rate()
    if not burn_rate or burn_rate == 0:
        return None
    return units / (burn_rate * 24)


def set_budget(amount):
    """Set monthly electricity budget in KES."""
    set_profile("budget", str(amount))


def check_budget():
    """Check spending against monthly budget. Returns alert string or None."""
    budget_str = get_profile("budget")
    if not budget_str:
        return None
    budget = float(budget_str)
    now = datetime.now()
    start = f"{now.year}-{now.month:02d}-01 00:00:00"
    if now.month == 12:
        end = f"{now.year + 1}-01-01 00:00:00"
    else:
        end = f"{now.year}-{now.month + 1:02d}-01 00:00:00"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) FROM purchases WHERE timestamp >= ? AND timestamp < ?", (start, end))
    spent = c.fetchone()[0]
    conn.close()

    pct = (spent / budget) * 100 if budget > 0 else 0
    if pct >= 100:
        return f"🚨 Umepita budget! KES {spent:,.0f}/{budget:,.0f} ({pct:.0f}%) this month."
    elif pct >= 80:
        return f"⚠️ Budget almost done — KES {spent:,.0f}/{budget:,.0f} ({pct:.0f}%) used this month."
    return f"💰 Budget: KES {spent:,.0f}/{budget:,.0f} ({pct:.0f}%) used this month."


def comparison_insights():
    """Week-over-week and day-of-week usage patterns."""
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    two_weeks_ago = (now - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")

    # This week vs last week spending
    c.execute("SELECT COALESCE(SUM(amount),0), COALESCE(SUM(units),0) FROM purchases WHERE timestamp >= ?", (week_ago,))
    this_spent, this_units = c.fetchone()
    c.execute("SELECT COALESCE(SUM(amount),0), COALESCE(SUM(units),0) FROM purchases WHERE timestamp >= ? AND timestamp < ?", (two_weeks_ago, week_ago))
    last_spent, last_units = c.fetchone()

    # Day-of-week consumption from readings
    c.execute("SELECT strftime('%w', timestamp), balance FROM readings ORDER BY timestamp ASC")
    readings = c.fetchall()
    conn.close()

    lines = ["📈 *Usage Insights*", ""]

    # Week-over-week
    if last_units > 0 and this_units > 0:
        diff = ((this_units - last_units) / last_units) * 100
        if diff > 5:
            lines.append(f"⬆️ You used {diff:.0f}% more units this week than last week.")
        elif diff < -5:
            lines.append(f"⬇️ You used {abs(diff):.0f}% fewer units this week. Poa!")
        else:
            lines.append("↔️ Usage ni sawa sawa with last week.")
    elif this_units > 0:
        lines.append(f"This week: {this_units:.0f} units (KES {this_spent:,.0f}). No last week data to compare.")

    # Day patterns from readings
    if len(readings) >= 7:
        day_usage = {}
        for i in range(1, len(readings)):
            dow = int(readings[i][0])
            burned = readings[i-1][1] - readings[i][1]
            if burned > 0:
                day_usage.setdefault(dow, []).append(burned)
        if day_usage:
            day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            avgs = {d: sum(v)/len(v) for d, v in day_usage.items()}
            if avgs:
                peak = max(avgs, key=avgs.get)
                low = min(avgs, key=avgs.get)
                lines.append(f"📅 Heaviest day: {day_names[peak]} ({avgs[peak]:.1f} units avg)")
                lines.append(f"📅 Lightest day: {day_names[low]} ({avgs[low]:.1f} units avg)")

    return "\n".join(lines) if len(lines) > 2 else None

