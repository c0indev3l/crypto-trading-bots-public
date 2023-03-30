import pandas as pd
import numpy as np

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT"]

def to_dataframe(dataMap, values="close"):
    df = None
    for symbol, data in dataMap.items():
        if data is None:
            continue
        
        if df is None:
            # idx = data.times
            idx = pd.to_datetime(data.times, unit="ms")
            df = pd.DataFrame(index=idx)
        df[symbol] = data.select(values)
    return df

@schedule(interval="1d", symbol=SYMBOLS, window_size=200)
def handler(state, dataMap):
   df = to_dataframe(dataMap)
   print(df)
   print(df.corr())  # print correlation matrix
