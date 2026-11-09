import http.client
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer
from pathlib import Path
from cookie_setup import CookieError, handler, youtube_cookies


def fixture(expiry="0"):
    return ("# Netscape HTTP Cookie File\n"
            f"#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t{expiry}\tSID\tfixture-only\n"
            ".example.com\tTRUE\t/\tTRUE\t0\tSESSION\tunrelated-fixture\n").encode()


class CookieSetupTests(unittest.TestCase):
    def test_only_youtube_session_retained(self):
        cleaned = youtube_cookies(fixture())
        self.assertIn(b"#HttpOnly_.youtube.com", cleaned)
        self.assertNotIn(b"unrelated-fixture", cleaned)

    def test_expired_and_guest_only_rejected(self):
        with self.assertRaises(CookieError):
            youtube_cookies(fixture("100"), now=101)
        with self.assertRaises(CookieError):
            youtube_cookies(fixture().replace(b"\tSID\t", b"\tVISITOR_INFO1_LIVE\t"))

    def test_empty_malformed_or_wrong_site_rejected(self):
        for raw in [b"", b"not cookies", fixture().replace(b".youtube.com", b".youtube.com.example.org"),
                    fixture().replace(b"\t0\tSID", b"\tbad\tSID")]:
            with self.subTest(raw=raw), self.assertRaises(CookieError):
                youtube_cookies(raw)

    def test_capability_origin_single_use_and_no_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cookies.txt"
            token = "x" * 48
            path = "/youtube-bot-setup/" + token + "/"
            server = HTTPServer(("127.0.0.1", 0), handler(token, time.time()+300, target, "https://logic-coin.online"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def request(method, route, data=None, origin=None):
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                headers = {"Content-Type": "multipart/form-data; boundary=fixture-boundary"}
                if origin:
                    headers["Origin"] = origin
                connection.request(method, route, data, headers)
                response = connection.getresponse()
                status, body, security = response.status, response.read(), response.getheader("Cache-Control")
                connection.close()
                return status, body, security
            body = (b'--fixture-boundary\r\nContent-Disposition: form-data; name="cookies"; filename="cookies.txt"\r\nContent-Type: text/plain\r\n\r\n'
                    + fixture() + b'\r\n--fixture-boundary--\r\n')
            try:
                self.assertEqual(request("GET", "/youtube-bot-setup/wrong/")[0], 404)
                self.assertEqual(request("POST", path, body, "https://example.com")[0], 403)
                self.assertFalse(target.exists())
                status, _, security = request("POST", path, body, "https://logic-coin.online")
                self.assertEqual(status, 200)
                self.assertEqual(security, "no-store")
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(b"unrelated-fixture", target.read_bytes())
                self.assertEqual(request("POST", path, body, "https://logic-coin.online")[0], 409)
                self.assertNotIn(b"fixture-only", request("GET", path)[1])
                self.assertEqual(request("GET", path+"cookies.txt")[0], 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
