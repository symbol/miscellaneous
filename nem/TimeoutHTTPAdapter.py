import requests
from urllib3.util.retry import Retry


class TimeoutHTTPAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs['timeout']
        del kwargs['timeout']

        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        # pylint: disable=arguments-differ
        timeout = kwargs.get('timeout')

        if timeout is None:
            kwargs['timeout'] = self.timeout

        return super().send(request, **kwargs)


def create_http_session():
    retries = Retry(total=7, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = TimeoutHTTPAdapter(max_retries=retries, timeout=10)

    http = requests.Session()
    http.mount('http://', adapter)
    http.mount('https://', adapter)
    return http
