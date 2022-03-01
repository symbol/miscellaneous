import time
import os
from datetime import date

import pandas as pd
import requests
from tqdm import tqdm

XYM_API_HOST = os.getenv('XYM_API_HOST', 'wolf.importance.jp')
XEM_API_HOST = os.getenv('XEM_API_HOST', 'alice5.nem.ninja')
CM_KEY = os.getenv('CM_KEY' '')

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
MAX_TRIES = 6
RETRY_S = 15


def lookup_balance(address, asset):
    asset = asset.lower()
    if asset in ['symbol', 'xym']:
        return lookup_xym_balance(address)
    elif asset in ['nem', 'xem']:
        return lookup_xem_balance(address)
    else:
        raise ValueError(f"Asset not supported: {asset}")


def lookup_xym_balance(address):

    balance = 0
    json_account = requests.get('https://' + XYM_API_HOST + ':3001/accounts/' + address).json()
    json_mosaics = json_account['account']['mosaics']
    for json_mosaic in json_mosaics:
        if XYM_MOSAIC_ID == json_mosaic['id']:
            balance = float(json_mosaic['amount']) / 1000000
        break

    return balance


def lookup_xem_balance(address):
  
    response = requests.get('http://' + XEM_API_HOST + ':7890/account/get?address=' + address).json()
    balance = float(response['account']['balance']) / 1000000
    return balance


def get_cm_prices(ticker, datetime):

    response = requests.get(
        'https://api.coinmetrics.io/v4/timeseries/asset-metrics?assets=' +
        ticker +
        '&start_time=' +
        datetime +
        '&limit_per_asset=1&metrics=PriceUSD&api_key=' + CM_KEY).json()
    ref_rate = response['data'][0]['PriceUSD']
    return ref_rate


def get_cm_metrics(assets, metrics, start_time='2016-01-01', end_time=None, frequency='1d'):
    if end_time is None:
        end_time = date.today()
    data = []
    url = (
        f'https://api.coinmetrics.io/v4/timeseries/asset-metrics?' +
        f'assets={",".join(assets)}&' +
        f'start_time={start_time}&' +
        f'end_time={end_time}&' +
        f'metrics={",".join(metrics)}&' +
        f'frequency={frequency}&' +
        f'pretty=true&api_key={CM_KEY}')
    while True:
        r = requests.get(url).json()
        data.extend(r['data'])
        if 'next_page_url' in r:
            url = r['next_page_url']
        else:
            break
    return data


def fix_ticker(ticker):
    if ticker in GECKO_TICKER_MAP:
        ticker = GECKO_TICKER_MAP[ticker]
    return ticker


def get_gecko_spot(ticker, currency='usd'):
    ticker = fix_ticker(ticker)
    tries = 1
    while tries <= MAX_TRIES:
        try:
            response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=' + ticker + '&vs_currencies=' + currency).json()
            return response[ticker][currency]
        except:
            time.sleep(RETRY_S)
            tries += 1
    return None


def get_gecko_price(ticker, date, currency='usd'):
    ticker = fix_ticker(ticker)
    tries = 1
    while tries <= MAX_TRIES:
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
        except:
            print(f'Failed to get gecko price {ticker} : {date} on try {tries}; retrying in {RETRY_S}s')
            time.sleep(RETRY_S)
            tries += 1
    return None


def get_gecko_prices(ticker, start_date, end_date, currency='usd'):
    dates = pd.date_range(start_date, end_date, freq='D')
    prices = {'date': dates, ticker: []}
    for datetime in tqdm(dates):
        prices[ticker].append(get_gecko_price(ticker, datetime.strftime('%d-%m-%Y'), currency))
    return pd.DataFrame.from_records(prices).set_index('date')
