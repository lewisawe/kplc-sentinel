from init_db import init_db
from logic import calculate_burn_rate, predict_blackout, get_db_connection, check_outages
from datetime import datetime, timedelta

init_db()

def check_status():
    remaining = predict_blackout()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, timestamp FROM readings ORDER BY timestamp DESC LIMIT 1")
    last_reading = cursor.fetchone()
    conn.close()

    alerts = []

    if remaining is not None:
        if remaining < 24:
            alerts.append({
                "type": "LOW_BALANCE_WARNING",
                "message": f"Niaje! You only have {remaining:.1f} hours of power left based on your current usage. You'll likely run out by { (datetime.now() + timedelta(hours=remaining)).strftime('%I:%M %p') }. Top up soon!"
            })
    
    # If no reading in 48 hours, ask for a spot check
    if last_reading:
        fmt = "%Y-%m-%d %H:%M:%S"
        last_time = datetime.strptime(last_reading[1], fmt)
        if (datetime.now() - last_time).total_seconds() > 48 * 3600:
            alerts.append({
                "type": "SPOT_CHECK_REQUEST",
                "message": "Niaje! I haven't had a meter reading in a while. Can you press 20# and tell me what the units say? It helps me stay accurate."
            })

    # Check for planned outages in user's area
    outage_msg = check_outages()
    if outage_msg and "No planned outages" not in outage_msg:
        alerts.append({
            "type": "PLANNED_OUTAGE",
            "message": outage_msg
        })
            
    return alerts

def weekly_summary():
    """Generate a weekly consumption and spend summary."""
    conn = get_db_connection()
    cursor = conn.cursor()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    # Purchases this week
    cursor.execute(
        "SELECT COALESCE(SUM(units),0), COALESCE(SUM(amount),0), COUNT(*) FROM purchases WHERE timestamp >= ?",
        (week_ago,)
    )
    units_bought, amount_spent, purchase_count = cursor.fetchone()

    # Readings this week for consumption estimate
    cursor.execute(
        "SELECT timestamp, balance FROM readings WHERE timestamp >= ? ORDER BY timestamp ASC",
        (week_ago,)
    )
    readings = cursor.fetchall()
    conn.close()

    # Estimate units consumed this week from first and last reading
    units_consumed = None
    if len(readings) >= 2:
        first_bal = readings[0][1]
        last_bal = readings[-1][1]
        units_consumed = (first_bal + units_bought) - last_bal

    burn_rate = calculate_burn_rate()

    # Build summary
    lines = ["📊 *Weekly KPLC Summary*", ""]
    lines.append(f"Top-ups: {purchase_count} purchases, {units_bought:.1f} units (KES {amount_spent:,.0f})")

    if units_consumed is not None and units_consumed > 0:
        lines.append(f"Consumed: ~{units_consumed:.1f} units this week")
        projected_monthly = units_consumed * (30 / 7)
        monthly_cost = (amount_spent / units_bought * projected_monthly) if units_bought > 0 else 0
        lines.append(f"Projected monthly: ~{projected_monthly:.0f} units (~KES {monthly_cost:,.0f})")
    elif burn_rate:
        weekly_units = burn_rate * 24 * 7
        lines.append(f"Est. weekly consumption: ~{weekly_units:.1f} units (from burn rate)")

    remaining = predict_blackout()
    if remaining:
        lines.append(f"Current runway: ~{remaining:.0f} hours")

    return {
        "type": "WEEKLY_SUMMARY",
        "message": "\n".join(lines)
    }


if __name__ == "__main__":
    for alert in check_status():
        print(f"[{alert['type']}] {alert['message']}")
    summary = weekly_summary()
    print(f"\n[{summary['type']}]\n{summary['message']}")
