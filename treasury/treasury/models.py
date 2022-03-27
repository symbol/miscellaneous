import arch
import numpy as np
import pandas as pd
import tensorflow_probability as tfp

tfd = tfp.distributions


def get_garch_residuals(data, dist='skewt'):
    model = arch.arch_model(100*data.dropna(), dist=dist)
    res = model.fit(update_freq=1)
    return res.std_resid


def get_garch_forecasts(data, last_obs, mean='AR', lags=2, dist='skewt', horizon=1, simulations=1000):
    last_obs = pd.to_datetime(last_obs, utc=True)
    split_date = data.loc[:last_obs].index[-2]
    res = arch.arch_model(100*data.loc[:split_date].dropna(), mean=mean, lags=lags, dist=dist).fit(update_freq=0, last_obs=last_obs)
    fres = arch.arch_model(100*data.loc[split_date:].dropna(), mean=mean, lags=lags, dist=dist).fit(update_freq=0)
    # can potentially be improved by using the .fix() method on the arch_model class instead of .fit
    return fres.forecast(res.params, horizon=horizon, start=last_obs, method='simulation', simulations=simulations)
    # forecasts.simulations.values.squeeze().T[:, 2:]


def get_mean_variance_forecasts(prices, ref_ticker, forecast_window=60, trend_scale=1.0, vol_scale=1.0, num_sims=1000):
    forecast_dates = pd.date_range(prices.index[-1], periods=forecast_window+1)
    logret = np.log(prices[ref_ticker].pct_change().dropna()+1)
    loc = logret.mean()
    sigma = logret.std()
    dist = tfd.Normal(loc=loc*trend_scale, scale=sigma*vol_scale)
    data = dist.sample([forecast_window+1, num_sims]).numpy()
    data[0] = 0.0
    return np.e**pd.DataFrame(data, index=forecast_dates).cumsum()
