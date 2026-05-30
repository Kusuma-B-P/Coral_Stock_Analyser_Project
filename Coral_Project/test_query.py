import subprocess, os
from datetime import datetime, timedelta

coral = r".\coral.exe"
cwd = r"D:\Coral_Project_New\Coral_Project"

def run(label, q):
    print(f"\n=== {label} ===")
    r = subprocess.run([coral, "sql", q], capture_output=True, text=True, timeout=30, cwd=cwd)
    if r.returncode != 0:
        print("STDERR:", r.stderr.strip()[:400])
    else:
        print(r.stdout.strip()[:600] or "(empty result)")

now_unix = int(datetime.now().timestamp())
ago_unix = int((datetime.now() - timedelta(days=30)).timestamp())

# Test news with datetime range filter
run("news with datetime range", f"""
    SELECT headline, source, datetime FROM finnhub.news
    WHERE symbol = 'NVDA'
      AND datetime >= {ago_unix}
      AND datetime <= {now_unix}
    ORDER BY datetime DESC LIMIT 5
""")

# Test stock_prices
run("stock_prices", """
    SELECT date, open, close, volume FROM stock_prices.daily
    WHERE ticker = 'NVDA'
    ORDER BY date DESC LIMIT 3
""")