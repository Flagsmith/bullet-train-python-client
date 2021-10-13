import json
import typing
from datetime import datetime

from requests_futures.sessions import FuturesSession

ANALYTICS_ENDPOINT = "analytics/flags/"

# Used to control how often we send data(in seconds)
ANALYTICS_TIMER = 10

session = FuturesSession(max_workers=4)


class AnalyticsProcessor:
    """
    AnalyticsProcessor is used to track how often individual Flags are evaluated within
    the Flagsmith SDK. Docs: https://docs.flagsmith.com/advanced-use/flag-analytics.
    """

    def __init__(
        self, base_api_url: str, http_headers: typing.Dict[str, str], timeout: int = 3
    ):
        """
        Initialise the AnalyticsProcessor to handle sending analytics on flag usage to
        the Flagsmith API.

        :param base_api_url: base api url to override when using self hosted version
        :param http_headers: All the http headers required to communicate with the server(including x-enviroment-key)
        :param timeout(optional): used to tell requests to stop waiting for a response after a
            given number of seconds
        """
        self.analytics_endpoint = base_api_url + ANALYTICS_ENDPOINT
        self.headers = http_headers
        # Add content type if not present
        self.headers.update({"Content-Type": "application/json"})

        self._last_flushed = datetime.now()
        self.analytics_data = {}
        self.timeout = timeout

    def flush(self):
        """
        Sends all the collected data to the api asynchronously and resets the timer
        """

        if not self.analytics_data:
            return
        session.post(
            self.analytics_endpoint,
            data=json.dumps(self.analytics_data),
            timeout=self.timeout,
            headers=self.headers,
        )

        self.analytics_data.clear()
        self._last_flushed = datetime.now()

    def track_feature(self, feature_id: int):
        self.analytics_data[feature_id] = self.analytics_data.get(feature_id, 0) + 1
        if (datetime.now() - self._last_flushed).seconds > ANALYTICS_TIMER:
            self.flush()
