from nem.TimeoutHTTPAdapter import create_http_session


class PriceSnapshot():
    def __init__(self, date):
        self.date = date
        self.price = 0
        self.volume = 0
        self.market_cap = 0
        self.comments = None


class CoinGeckoClient:
    def __init__(self):
        self.session = create_http_session()

    def get_price_spot(self, ticker, currency):
        json_response = self._get_json('simple/price?ids={}&vs_currencies={}'.format(ticker, currency))
        return json_response[ticker][currency]

    def get_price_snapshot(self, date, ticker, currency):
        json_response = self._get_json('coins/{}/history?date={}&localization=false'.format(ticker, date.strftime('%d-%m-%Y')))

        snapshot = PriceSnapshot(date.strftime('%Y-%m-%d'))

        if 'market_data' in json_response:
            market_data = json_response['market_data']
            snapshot.price = float(market_data['current_price'][currency])
            snapshot.volume = float(market_data['total_volume'][currency])

            market_cap = market_data['market_cap'][currency]
            if market_cap is not None:
                snapshot.market_cap = float(market_cap)
        else:
            snapshot.comments = 'no price data available'

        return snapshot

    def _get_json(self, rest_path):
        json_http_headers = {'Content-type': 'application/json'}
        return self.session.get('https://api.coingecko.com/api/v3/{}'.format(rest_path), headers=json_http_headers).json()
