import unittest

from lambda_function import run_quote_pipeline

import logging
logging.basicConfig(level=logging.INFO)


class TestLiveGeminiQuote(unittest.TestCase):

    def test_live_gemini_quote(self):
        event_data = {
            # "pulseName": "2014 autumn chase",
            # "pulseName": "6789 Oaklawn Drive, Cincinnati, Ohio, 45227",
            # "pulseName": "475 19th Place Vero beach",
            "pulseName": "5555 Test Road, Cincinnati, Ohio, 45252",
            "pulseId": "1",
            "boardId": "18393705497",
        }

        run_quote_pipeline(event_data)


if __name__ == "__main__":
    unittest.main()