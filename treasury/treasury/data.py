import datetime
import time

import pandas as pd
import requests
from tqdm import tqdm

GECKO_TICKER_MAP = {
   'ADA': 'cardano',
   'AVAX': 'avalanche-2',
   'BTC': 'bitcoin',
   'DOT': 'polkadot',
   'ETH': 'ethereum',
   'LTC': 'litecoin',
   'MATIC': 'matic-network',
   'SOL': 'solana',
   'TRX': 'tron',
   'XEM': 'nem',
   'XMR': 'monero',
   'XYM': 'symbol',
}

XYM_MOSAIC_ID = '6BED913FA20223F8'


def lookup_balance(address, asset, api_hosts):
    asset = asset.lower()
    if asset in ['symbol', 'xym']:
        return lookup_xym_balance(address, api_hosts['XYM'])
    if asset in ['nem', 'xem']:
        return lookup_xem_balance(address, api_hosts['XEM'])
    raise ValueError(f'Asset not supported for balance lookup: {asset}')


def lookup_xym_balance(address, xym_api_host):
    balance = 0
    json_account = requests.get('https://' + xym_api_host + ':3001/accounts/' + address).json()
    json_mosaics = json_account['account']['mosaics']
    for json_mosaic in json_mosaics:
        if XYM_MOSAIC_ID == json_mosaic['id']:
            balance = float(json_mosaic['amount']) / 1000000
        break

    return balance


def lookup_xem_balance(address, xem_api_host):
    response = requests.get('http://' + xem_api_host + ':7890/account/get?address=' + address).json()
    balance = float(response['account']['balance']) / 1000000
    return balance


def get_cm_prices(ticker, date_time, cm_key):

    response = requests.get(
        'https://api.coinmetrics.io/v4/timeseries/asset-metrics?assets=' +
        ticker +
        '&start_time=' +
        date_time +
        '&limit_per_asset=1&metrics=PriceUSD&api_key=' + cm_key).json()
    ref_rate = response['data'][0]['PriceUSD']
    return ref_rate


def get_cm_metrics(assets, metrics, cm_key, start_time='2016-01-01', end_time=None, frequency='1d'):
    if end_time is None:
        end_time = datetime.date.today()
    data = []
    url = (
        'https://api.coinmetrics.io/v4/timeseries/asset-metrics?' +
        f'assets={",".join(assets)}&' +
        f'start_time={start_time}&' +
        f'end_time={end_time}&' +
        f'metrics={",".join(metrics)}&' +
        f'frequency={frequency}&' +
        f'pretty=true&api_key={cm_key}')
    while True:
        response = requests.get(url).json()
        data.extend(response['data'])
        if 'next_page_url' in response:
            url = response['next_page_url']
        else:
            break
    return data


def fix_ticker(ticker):
    return GECKO_TICKER_MAP.get(ticker, ticker)


def get_gecko_spot(ticker, max_api_tries=6, retry_delay_seconds=15, currency='usd'):
    ticker = fix_ticker(ticker)
    tries = 1
    while tries <= max_api_tries:
        try:
            response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=' + ticker + '&vs_currencies=' + currency).json()
            return response[ticker][currency]
        except (KeyError, requests.exceptions.RequestException) as _:
            time.sleep(retry_delay_seconds)
            tries += 1
    return None


def get_gecko_price(ticker, date, max_api_tries=6, retry_delay_seconds=15, currency='usd'):
    ticker = fix_ticker(ticker)
    tries = 1
    while tries <= max_api_tries:
        try:
            response = requests.get(
                'https://api.coingecko.com/api/v3/coins/' +
                ticker +
                '/history?date=' +
                date +
                '&localization=false').json()
            if 'name' in response and 'market_data' not in response:
                return None
            return response['market_data']['current_price'][currency]
        except (KeyError, requests.exceptions.RequestException) as _:
            print(f'Failed to get gecko price {ticker} : {date} on try {tries}; retrying in {retry_delay_seconds}s')
            time.sleep(retry_delay_seconds)
            tries += 1
    return None


def get_gecko_prices(ticker, start_date, end_date, max_api_tries=6, retry_delay_seconds=15, currency='usd'):
    dates = pd.date_range(start_date, end_date, freq='D')
    prices = {'date': dates, ticker: []}
    for date_time in tqdm(dates):
        prices[ticker].append(get_gecko_price(ticker, date_time.strftime('%d-%m-%Y'), max_api_tries, retry_delay_seconds, currency))
    return pd.DataFrame.from_records(prices).set_index('date')
