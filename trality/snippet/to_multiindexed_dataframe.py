import pandas as pd

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT"]

def to_multiindexed_dataframe(dataMap):
    df = None
    values = ["open", "high", "low", "close", "volume"]
    for symbol, data in dataMap.items():
        if data is None:
            continue        
        if df is None:
            # times = data.times
            times = pd.to_datetime(data.times, unit="ms")
            index = pd.MultiIndex.from_product([times, values], names=["datetime", "value"])
            # df = pd.DataFrame(columns=SYMBOLS, index=index)
            df = pd.DataFrame(index=index)
            df.columns.name = "symbol"
        for value in values:
            df.loc[(slice(None), value), symbol] = data.select(value)
    return df

@schedule(interval="1d", symbol=SYMBOLS, window_size=200)
def handler(state, dataMap):
   df = to_multiindexed_dataframe(dataMap)
   print(df)
