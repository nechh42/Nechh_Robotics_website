# Saat başı dolandırıcılık uyarısı
def scam_warning():
    return (
        "🚨 SCAM WARNING 🚨\n\n"
        "• Admins will NEVER DM you\n"
        "• No investment offers\n"
        "• No wallet requests\n"
        "• No paid signals\n\n"
        "📌 Any private message is a scam."
    )
# --- TELEGRAM COMMUNICATION POLICY & MESSAGE TYPE TEMPLATES ---

def communication_policy():
    return (
        "📋 NECHH — TELEGRAM COMMUNICATION POLICY\n"
        "🏛️ Philosophy\n\n"
        "Less messages. More insight. Right timing.\n\n"
        "This channel:\n"
        "- Does not provide trade instructions\n"
        "- Does not make decisions on behalf of users\n"
        "- Shares algorithmic and scenario-based analysis outputs\n"
    )

def analysis_alert_template():
    return (
        "📊 {symbol} — Algorithmic Analysis\n\n"
        "Trend: {trend}\n"
        "Volatility: {volatility}\n"
        "Momentum: {momentum}\n"
        "Algorithmic Probability: {probability}%\n\n"
        "Status: {status}\n\n"
        "⏱ Time: {time} UTC\n\n"
        "⚠️ This is not financial advice.\n"
        "⚠️ All decisions and risks remain with the user."
    )

def market_status_update_template():
    return (
        "📊 MARKET STATUS — {hour}:00 UTC\n\n"
        "BTC: ${btc_price} ({btc_change})\n"
        "ETH: ${eth_price} ({eth_change})\n"
        "Total Market Cap: {market_cap}\n"
        "Volatility: {volatility}\n"
        "Sentiment: {sentiment}\n\n"
        "System Status:\n"
        "• Active analysis: {active_pairs} pairs\n"
        "• Trade conditions: {trade_conditions}\n\n"
        "Next evaluation: {next_eval} UTC"
    )

def daily_system_report_template():
    return (
        "📅 DAILY SYSTEM REPORT — {date}\n\n"
        "SUMMARY:\n"
        "• Total analyses: {total_analyses}\n"
        "• Signal-condition events: {signal_events}\n"
        "• Active positions: {active_positions}\n\n"
        "MODEL BEHAVIOR:\n"
        "• Trend: {trend}\n"
        "• Volatility: {volatility}\n"
        "• Risk appetite: {risk_appetite}\n\n"
        "Note:\n"
        "This report summarizes model behavior.\n"
        "It does not represent real trading results.\n\n"
        "⚠️ Past performance does not guarantee future results."
    )

def risk_alert_template():
    return (
        "🚨 RISK ALERT\n\n"
        "{event_description}\n\n"
        "Recommended approach:\n"
        "• Avoid opening new positions\n"
        "• Review existing exposure\n"
        "• Remain calm\n\n"
        "🛡 System Status: Protection Mode"
    )
# Haftalık periyodik güvenlik hatırlatması
def weekly_security_reminder():
    return (
        "🔐 SECURITY REMINDER\n\n"
        "NECHH will NEVER:\n"
        "• DM you\n"
        "• Ask for payment via private messages\n"
        "• Ask for keys or wallets\n\n"
        "Only trust messages posted in this channel.\n"
        "Stay alert."
    )

# Olay bazlı güvenlik uyarısı
def security_alert():
    return (
        "🚨 SECURITY ALERT\n\n"
        "We have detected scam attempts impersonating NECHH.\n\n"
        "⚠️ Reminder:\n"
        "• NECHH does NOT contact users privately\n"
        "• Do NOT send funds or information to anyone\n\n"
        "Only trust this official channel."
    )

# Mini security footer (mesajların altına eklenebilir)
def security_footer():
    return "🔐 Security: NECHH never DMs users."
def position_opened_message(d):
    return f"""
📊 POSITION OPENED – {d['symbol']}

Model Decision: OPEN
Position Type: {d['side']}

📈 Scores:
• Combined: {d['combined']}
• Technical: {d['technical']}
• Sentiment: {d['sentiment']}
• Consensus: {d['consensus']}

💵 Entry: {d['entry']}
🛑 Stop Loss: {d['stop']}
🎯 Take Profit: {d['tp']}

⚠️ Algorithmic system output
⚠️ Not investment advice
"""


def hourly_summary(coins):
    msg = "🧠 MARKET SCAN SUMMARY (Hourly)\n\n"
    for c in coins[:5]:
        msg += f"• {c['symbol']} | Score: {c['combined']}\n"
    msg += "\n📌 Informational & educational output"
    msg += "\n📌 This is NOT a trade signal"
    return msg


def safety_warning():
    return (
        "⚠️ SECURITY NOTICE\n\n"
        "Admins will NEVER DM you.\n"
        "No private messages.\n"
        "No wallet requests.\n\n"
        "📌 Stay safe."
    )


# Trade açılmadığında neden açılmadığını açıklayan mesaj

# Trade açılmadığında gönderilecek Market Scenario mesajı (nihai format)
def position_not_opened_message(d):
    return f"""
🧠 MARKET SCENARIO – {d['symbol']}

Status: NO POSITION OPENED
Reason: {d['reason']}

📊 Model Scores:
• Combined: {d['combined']}
• Technical: {d['technical']}
• Sentiment: {d['sentiment']}
• Consensus: {d['consensus']}

🧩 Model Interpretation:
• {d['interp_1']}
• {d['interp_2']}
• {d['interp_3']}

📌 Informational & educational output
📌 This is NOT a trade signal
"""


# Saatlik market taraması mesajı

# Saatlik toplu Market Scenario Digest mesajı (onaylı format)
def market_scenario_digest_message(digest):
    msg = f"""
🧠 MARKET SCENARIO DIGEST – {digest['hour']} UTC\n\n"
    msg += "No new positions opened in the last hour.\n\n"
    msg += f"📊 Analyzed Symbols: {digest['analyzed_count']}\n\n"
    if digest.get('skipped'):
        msg += "⏸️ Skipped (Risk Controls Active):\n"
        for item in digest['skipped']:
            msg += f"• {item['symbol']} – {item['reason']}\n"
        msg += "\n"
    msg += "📈 Model Summary:\n"
    msg += f"• Average Combined Score: {digest['avg_combined']}\n"
    msg += f"• Consensus remains strong\n"
    msg += f"• Exposure intentionally limited\n\n"
    msg += "📌 Informational & educational output\n"
    msg += "📌 This is NOT a trade signal\n\n"
    msg += "🔐 Security reminder: NECHH never contacts users privately.\n"
    return msg
