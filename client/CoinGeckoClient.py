from .pod import PriceSnapshot
from .TimeoutHTTPAdapter import create_http_session


class CoinGeckoClient:
    def __init__(self):
        self.session = create_http_session()

    def get_price_spot(self, ticker, currency):
        json_response = self._get_json(f'simple/price?ids={ticker}&vs_currencies={currency}')
        return json_response[ticker][currency]

    def get_price_snapshot(self, date, ticker, currency):
        formatted_date = date.strftime('%d-%m-%Y')
        json_response = self._get_json(f'coins/{ticker}/history?date={formatted_date}&localization=false')

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
        return self.session.get(f'https://api.coingecko.com/api/v3/{rest_path}', headers=json_http_headers).json()
