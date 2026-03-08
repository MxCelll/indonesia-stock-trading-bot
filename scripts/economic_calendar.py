from datetime import datetime, timedelta

def get_economic_calendar(country='Indonesia', days_ahead=7):
    # Data dummy
    events = [
        {
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'time': '14:00',
            'country': 'Indonesia',
            'event': 'Suku Bunga BI',
            'actual': '6.00%',
            'forecast': '6.00%',
            'previous': '5.75%'
        },
        {
            'date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
            'time': '10:00',
            'country': 'Indonesia',
            'event': 'Inflasi YoY',
            'actual': '-',
            'forecast': '2.8%',
            'previous': '2.7%'
        }
    ]
    return events

def format_calendar(events):
    if not events:
        return "📅 Tidak ada event ekonomi dalam 7 hari ke depan."
    lines = ["📅 *Kalender Ekonomi (7 hari ke depan)*\n"]
    for e in events:
        lines.append(
            f"🗓️ {e['date']} {e['time']}\n"
            f"🇮🇩 {e['country']} - {e['event']}\n"
            f"  Aktual: {e['actual']} | Forecast: {e['forecast']} | Sebelumnya: {e['previous']}\n"
        )
    return '\n'.join(lines)