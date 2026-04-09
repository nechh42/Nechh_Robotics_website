import sys
sys.path.insert(0, '.')
import requests
import pandas as pd
from strategies.indicators import calc_atr

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "DOTUSDT", "XRPUSDT"]
print("ATR/Price ratios (1m candles):")
for s in symbols:
    url = f"https://api.binance.com/api/v3/klines?symbol={s}&interval=1m&limit=30"
    data = requests.get(url, timeout=5).json()
    df = pd.DataFrame({
        "open": [float(r[1]) for r in data],
        "high": [float(r[2]) for r in data],
        "low": [float(r[3]) for r in data],
        "close": [float(r[4]) for r in data],
    })
    atr = calc_atr(df).iloc[-1]
    price = df["close"].iloc[-1]
    ratio = atr / price if price > 0 else 0
    print(f"  {s:12} price=${price:.4f} ATR={atr:.6f} ratio={ratio:.6f} {'OK' if 0.003 <= ratio <= 0.03 else 'FILTERED'}")
