import importlib
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


class YouTubeSourceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("backend.youtube_source"),
                             "Downloader configuration must be implemented independently of app startup")
        self.source = importlib.import_module("backend.youtube_source")
        self.temp = tempfile.TemporaryDirectory(prefix="cutflow-youtube-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_validates_public_provider_url_without_credentials_or_custom_ports(self):
        self.assertEqual(self.source.validate_source_url("https://youtu.be/mRD0-GxqHVo"), "youtu.be")
        self.assertEqual(self.source.validate_source_url("https://vimeo.com/12345"), "vimeo.com")
        for url in ("http://127.0.0.1/video", "https://youtube.com.evil.example/watch", 
                    "https://user:password@youtube.com/watch", "https://youtube.com:8443/watch"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.source.validate_source_url(url)

    def test_uses_current_downloader_defaults_and_available_node_runtime(self):
        with patch.dict("os.environ", {}, clear=True):
            options = self.source.build_download_options(self.directory, 1024)
        self.assertNotIn("extractor_args", options)
        self.assertIn("node", options["js_runtimes"])
        self.assertNotIn("cookiefile", options)
        self.assertEqual(options["max_filesize"], 1024)

    def test_materializes_valid_cookies_with_restrictive_permissions(self):
        contents = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tfake-session\n"
        path = self.source.prepare_cookie_file(self.directory, contents)
        self.assertEqual(path.read_text(encoding="utf-8"), contents)
        with patch.dict("os.environ", {}, clear=True):
            options = self.source.build_download_options(self.directory, 1024, cookie_file=path)
        self.assertEqual(options["cookiefile"], str(path))

    def test_rejects_malformed_and_expired_cookie_configuration_without_values(self):
        for contents in ("SID=secret-value", "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1\tSID\tsecret-value\n"):
            with self.subTest(contents=contents), self.assertRaises(ValueError) as caught:
                self.source.prepare_cookie_file(self.directory, contents)
            self.assertNotIn("secret-value", str(caught.exception))

    def test_operator_can_override_clients_without_changing_default_for_everyone(self):
        with patch.dict("os.environ", {"YOUTUBE_PLAYER_CLIENTS": "web_safari,web"}, clear=True):
            options = self.source.build_download_options(self.directory, 1024)
        self.assertEqual(options["extractor_args"]["youtube"]["player_client"], ["web_safari", "web"])

    def test_bot_challenge_is_actionable_and_never_echoes_sensitive_download_parameters(self):
        result = self.source.safe_download_error("ERROR: [youtube] id: Sign in to confirm you're not a bot. cookiefile=/private/secret.txt&token=secret-value")
        self.assertIn("YouTube", result)
        self.assertIn("verification", result.lower())
        self.assertIn("upload", result.lower())
        self.assertNotIn("secret-value", result)
        self.assertNotIn("/private/", result)

    def test_unknown_download_failure_is_sanitized_and_useful(self):
        result = self.source.safe_download_error("connection failed at /private/token-value")
        self.assertIn("download", result.lower())
        self.assertNotIn("token-value", result)


if __name__ == "__main__":
    unittest.main()
