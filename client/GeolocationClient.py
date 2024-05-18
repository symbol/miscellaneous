from .TimeoutHTTPAdapter import create_http_session


class GeolocationClient:
    def __init__(self):
        self.session = create_http_session()

    def get_ip_geolocation(self, ips):
        json_http_headers = {'Content-type': 'application/json'}
        json_response = self.session.post(
            'http://ip-api.com/batch?fields=1057493',
            json=ips,
            headers=json_http_headers).json()
        return json_response
