import numpy as np
import pandas as pd


def get_mean_variance_forecasts(prices, ref_ticker, forecast_window=60, trend_scale=1.0, vol_scale=1.0, num_sims=1000):
    forecast_dates = pd.date_range(prices.index[-1], periods=forecast_window+1)
    logret = np.log(prices[ref_ticker].pct_change().dropna()+1)
    loc = logret.mean()
    sigma = logret.std()
    data = np.random.normal(loc=loc*trend_scale, scale=sigma*vol_scale, size=[forecast_window+1, num_sims])
    data[0] = 0.0
    return np.e**pd.DataFrame(data, index=forecast_dates).cumsum()
