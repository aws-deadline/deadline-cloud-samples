from __future__ import annotations

import socket
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import check_external_links as checker  # noqa: E402
import check_markdown_links as markdown  # noqa: E402


class ExternalLinkCheckerTests(TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.original_external_root = checker.REPOSITORY_ROOT
        self.original_markdown_root = markdown.REPOSITORY_ROOT
        checker.REPOSITORY_ROOT = self.root
        markdown.REPOSITORY_ROOT = self.root
        self.addCleanup(setattr, checker, "REPOSITORY_ROOT", self.original_external_root)
        self.addCleanup(setattr, markdown, "REPOSITORY_ROOT", self.original_markdown_root)

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_collects_locations_strips_fragments_and_deduplicates(self) -> None:
        first = self.write(
            "README.md",
            "[one](https://example.com/guide#first)\n"
            "[two](https://example.com/guide#second)\n"
            "`[hidden](https://hidden.example/path)`\n",
        )
        second = self.write("docs/guide.md", "<https://example.com/guide#third>\n")
        links = checker.collect_external_links([first, second])
        self.assertEqual(
            {"https://example.com/guide": ["README.md:1", "README.md:2", "docs/guide.md:1"]},
            links,
        )

    def test_bare_url_locations_aggregate_and_deduplicate_with_other_syntaxes(self) -> None:
        url = "https://example.com/guide"
        source = self.write(
            "README.md",
            f"Bare {url}.\n"
            f"[Markdown]({url}) and duplicate bare {url}\n"
            f"<{url}> and <a href=\"{url}\">HTML</a>\n"
            "```text\nhttps://example.com/not-rendered\n```\n",
        )
        self.assertEqual(
            {url: ["README.md:1", "README.md:2", "README.md:3"]},
            checker.collect_external_links([source]),
        )

    def test_rejects_unsafe_url_shapes(self) -> None:
        unsafe = (
            "ftp://example.com/file",
            "https://user:secret@example.com/",
            "http://localhost/",
            "http://127.0.0.1/",
            "http://example.com:8080/",
            "https://single-label/",
            "https://example.com\\@127.0.0.1/",
        )
        for url in unsafe:
            with self.subTest(url=url), self.assertRaises(checker.UnsafeTarget):
                checker.parse_target(url)

    def test_rejects_multicast_literal_addresses(self) -> None:
        for url in ("http://224.0.0.1/", "http://[ff02::1]/"):
            with self.subTest(url=url), self.assertRaisesRegex(
                checker.UnsafeTarget, "multicast IP address"
            ):
                checker.parse_target(url)

    def test_rejects_ipv4_mapped_and_6to4_ipv6_literals(self) -> None:
        for url in (
            "http://[::ffff:169.254.169.254]/latest/meta-data/",  # IPv4-mapped link-local
            "http://[::ffff:10.0.0.1]/",  # IPv4-mapped private
            "http://[2002:0a00:0001::1]/",  # 6to4 wrapping 10.0.0.1
        ):
            with self.subTest(url=url), self.assertRaises(checker.UnsafeTarget):
                checker.parse_target(url)

    def test_rejects_dns_answer_set_containing_private_address(self) -> None:
        records = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]
        with mock.patch.object(checker.socket, "getaddrinfo", return_value=records):
            with self.assertRaisesRegex(checker.UnsafeTarget, "non-public IP address"):
                checker._public_addresses("example.com", 443)

    def test_rejects_mixed_dns_answer_set_containing_multicast(self) -> None:
        records = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("224.0.0.1", 443)),
        ]
        with mock.patch.object(checker.socket, "getaddrinfo", return_value=records):
            with self.assertRaisesRegex(checker.UnsafeTarget, "multicast IP address"):
                checker._public_addresses("example.com", 443)

    def test_rejects_sole_multicast_dns_answer(self) -> None:
        records = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("ff02::1", 443, 0, 0)),
        ]
        with mock.patch.object(checker.socket, "getaddrinfo", return_value=records):
            with self.assertRaisesRegex(checker.UnsafeTarget, "multicast IP address"):
                checker._public_addresses("example.com", 443)

    def test_unsafe_redirect_is_not_requested_or_retried_as_get(self) -> None:
        with mock.patch.object(
            checker,
            "_request_once",
            return_value=checker.Response(302, "http://169.254.169.254/latest/meta-data/"),
        ) as request:
            result = checker.check_url("https://example.com/start", checker.Settings(retries=2))
        self.assertFalse(result.success)
        self.assertIn("unsafe redirect target", result.detail)
        request.assert_called_once()

    def test_head_failure_falls_back_to_get_from_original_url(self) -> None:
        responses = [checker.Response(405, None), checker.Response(206, None)]
        with mock.patch.object(checker, "_request_once", side_effect=responses) as request:
            result = checker.check_url("https://example.com/start", checker.Settings(retries=0))
        self.assertTrue(result.success)
        self.assertEqual(
            [
                mock.call("https://example.com/start", "HEAD", mock.ANY),
                mock.call("https://example.com/start", "GET", mock.ANY),
            ],
            request.call_args_list,
        )

    def test_minimal_get_sets_range_and_identity_headers(self) -> None:
        captured: dict[str, object] = {}

        class FakeResponse:
            status = 206

            @staticmethod
            def getheader(name: str) -> None:
                return None

        class FakeConnection:
            def __init__(self, *args: object) -> None:
                captured["constructor"] = args

            def request(self, method: str, target: str, headers: dict[str, str]) -> None:
                captured.update(method=method, target=target, headers=headers)

            @staticmethod
            def getresponse() -> FakeResponse:
                return FakeResponse()

            @staticmethod
            def close() -> None:
                return None

        with (
            mock.patch.object(checker, "_public_addresses", return_value=[]),
            mock.patch.object(checker, "DirectHTTPSConnection", FakeConnection),
        ):
            response = checker._request_once("https://example.com/file", "GET", checker.Settings())
        self.assertEqual(206, response.status)
        headers = captured["headers"]
        self.assertIsInstance(headers, dict)
        self.assertEqual("bytes=0-0", headers["Range"])  # type: ignore[index]
        self.assertEqual("identity", headers["Accept-Encoding"])  # type: ignore[index]
        self.assertEqual(checker.USER_AGENT, headers["User-Agent"])  # type: ignore[index]

    def test_redirect_limit_is_deterministic(self) -> None:
        def redirect(url: str, method: str, settings: checker.Settings) -> checker.Response:
            number = int(url.rsplit("/", 1)[-1])
            return checker.Response(302, f"https://example.com/{number + 1}")

        with mock.patch.object(checker, "_request_once", side_effect=redirect):
            result = checker.check_url(
                "https://example.com/0", checker.Settings(retries=0, max_redirects=2)
            )
        self.assertFalse(result.success)
        self.assertIn("more than 2 redirects", result.detail)

    def test_retry_uses_exponential_backoff_for_transient_failure(self) -> None:
        failures = [checker.Response(503, None), checker.Response(503, None)]
        successes = [checker.Response(200, None)]
        sleep = mock.Mock()
        with mock.patch.object(checker, "_request_once", side_effect=failures + successes):
            result = checker.check_url(
                "https://example.com/", checker.Settings(retries=1, backoff=0.25), sleep=sleep
            )
        self.assertTrue(result.success)
        sleep.assert_called_once_with(0.25)

    def test_ignore_file_requires_dated_reason_and_uses_label_boundary(self) -> None:
        ignore_file = self.write(
            "ignore.txt",
            "# 2026-07-14: returned HTTP 403 to both checker methods\nexample.com\n",
        )
        rules = checker.load_ignore_file(ignore_file)
        self.assertIsNotNone(checker.matching_ignore("example.com", rules))
        self.assertIsNotNone(checker.matching_ignore("docs.example.com", rules))
        self.assertIsNone(checker.matching_ignore("notexample.com", rules))

    def test_ignore_file_rejects_wildcards_and_undocumented_domains(self) -> None:
        for content in (
            "*.example.com\n",
            "# explanation only\nexample.com\n",
            "# 2026-02-30: impossible date\nexample.com\n",
        ):
            with self.subTest(content=content):
                ignore_file = self.write("ignore.txt", content)
                with self.assertRaises(ValueError):
                    checker.load_ignore_file(ignore_file)

    def test_selected_markdown_keeps_only_tracked_markdown(self) -> None:
        tracked = self.write("docs/guide.md", "# Guide\n")
        self.write("docs/untracked.md", "# Untracked\n")
        self.write("docs/notes.txt", "notes\n")
        with mock.patch.object(markdown, "tracked_markdown", return_value=[tracked]):
            selected = checker._selected_markdown(
                [
                    Path("docs/guide.md"),  # tracked, relative
                    tracked,  # tracked, duplicate absolute -> deduplicated
                    Path("docs/untracked.md"),  # not tracked -> dropped
                    Path("docs/notes.txt"),  # not Markdown -> dropped
                    Path("docs/missing.md"),  # nonexistent -> dropped
                ]
            )
        self.assertEqual([tracked], selected)


if __name__ == "__main__":
    main()
