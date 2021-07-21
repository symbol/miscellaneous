from nem.TimeoutHTTPAdapter import create_http_session


class CoinGeckoClient:
    def __init__(self):
        self.session = create_http_session()

    def get_price_spot(self, ticker, currency):
        headers = {'Content-type': 'application/json'}
        uri = 'https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies={}'.format(ticker, currency)
        json_response = self.session.get(uri, headers=headers).json()
        return json_response[ticker][currency]
