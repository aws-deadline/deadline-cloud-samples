#!/usr/bin/env python3
"""Check live external links in every tracked Markdown file.

The checker intentionally bypasses proxy settings and pins each connection to an IP
address from a validated DNS result. Redirect targets are independently validated.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import http.client
import ipaddress
import re
import socket
import ssl
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import check_markdown_links as markdown

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IGNORE_FILE = REPOSITORY_ROOT / ".github" / "external-link-ignore.txt"
USER_AGENT = "deadline-cloud-samples-link-checker/1.0 (+https://github.com/aws-deadline/deadline-cloud-samples)"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
RETRYABLE_STATUSES = frozenset({408, 425, 429})
DATED_COMMENT = re.compile(r"^#\s*(\d{4}-\d{2}-\d{2}):\s*(\S.*)$")
DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


class UnsafeTarget(ValueError):
    """A URL or DNS result is unsafe for requests from CI."""


@dataclass(frozen=True)
class Settings:
    timeout: float = 10.0
    retries: int = 2
    backoff: float = 1.0
    max_redirects: int = 5


@dataclass(frozen=True)
class ParsedTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    host_header: str
    request_target: str


@dataclass(frozen=True)
class Response:
    status: int
    location: str | None


@dataclass(frozen=True)
class ChainResult:
    success: bool
    final_url: str
    status: int | None = None
    error: str | None = None
    hard_failure: bool = False

    @property
    def retryable(self) -> bool:
        return not self.hard_failure and (
            self.error is not None
            or self.status in RETRYABLE_STATUSES
            or (self.status is not None and self.status >= 500)
        )

    def describe(self) -> str:
        if self.error:
            return self.error
        return f"HTTP {self.status} at {self.final_url}"


@dataclass(frozen=True)
class CheckResult:
    url: str
    success: bool
    detail: str


def _require_public_unicast(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Reject every address class that CI must not contact, including multicast."""
    # Unwrap IPv4-in-IPv6 forms before classification. Older interpreters do not
    # always classify the embedded IPv4 (e.g. ::ffff:169.254.169.254 or a 6to4
    # address wrapping a private range) as non-global, so evaluate the IPv4 directly.
    if isinstance(address, ipaddress.IPv6Address):
        embedded = address.ipv4_mapped or address.sixtofour
        if embedded is not None:
            address = embedded
    if address.is_multicast:
        raise UnsafeTarget(f"multicast IP address {address} is not allowed")
    if not address.is_global:
        raise UnsafeTarget(f"non-public IP address {address} is not allowed")


def _ascii_hostname(hostname: str) -> str:
    if hostname.endswith("."):
        raise UnsafeTarget("hostnames with a trailing dot are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as error:
            raise UnsafeTarget(f"invalid internationalized hostname: {error}") from error
        if "." not in ascii_hostname:
            raise UnsafeTarget("single-label and localhost hostnames are not allowed")
        if ascii_hostname == "localhost" or ascii_hostname.endswith(".localhost"):
            raise UnsafeTarget("localhost targets are not allowed")
        labels = ascii_hostname.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        ):
            raise UnsafeTarget("malformed DNS hostname")
        if len(ascii_hostname) > 253:
            raise UnsafeTarget("DNS hostname is too long")
        return ascii_hostname
    _require_public_unicast(address)
    return address.compressed


def parse_target(url: str) -> ParsedTarget:
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url):
        raise UnsafeTarget("URL contains whitespace or control characters")
    if "\\" in url:
        raise UnsafeTarget("URL contains a backslash")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise UnsafeTarget(f"malformed URL: {error}") from error
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeTarget("only http and https URLs are allowed")
    if not parsed.netloc or parsed.hostname is None:
        raise UnsafeTarget("URL has no hostname")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise UnsafeTarget("URL credentials are not allowed")
    expected_port = 80 if scheme == "http" else 443
    if port is not None and port != expected_port:
        raise UnsafeTarget(f"non-standard port {port} is not allowed for {scheme}")

    hostname = _ascii_hostname(parsed.hostname)
    effective_port = port or expected_port
    host_header = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        host_header = f"{host_header}:{port}"
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(parsed.query, safe="%/?@!$&'()*+,;=:-._~")
    request_target = f"{path}?{query}" if query else path
    normalized_url = urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, ""))
    return ParsedTarget(normalized_url, scheme, hostname, effective_port, host_header, request_target)


def _public_addresses(hostname: str, port: int) -> list[tuple[int, int, int, tuple[object, ...]]]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise OSError(f"DNS resolution failed for {hostname}: {error}") from error
    if not records:
        raise OSError(f"DNS resolution returned no addresses for {hostname}")

    addresses: list[tuple[int, int, int, tuple[object, ...]]] = []
    seen: set[tuple[int, tuple[object, ...]]] = set()
    for family, socktype, protocol, _, sockaddr in records:
        raw_address = str(sockaddr[0]).split("%", 1)[0]
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as error:
            raise UnsafeTarget(f"DNS returned malformed address {raw_address!r}") from error
        try:
            _require_public_unicast(address)
        except UnsafeTarget as error:
            raise UnsafeTarget(
                f"DNS for {hostname} returned unsafe address {address}; refusing all addresses: {error}"
            ) from error
        key = (family, sockaddr)
        if key not in seen:
            seen.add(key)
            addresses.append((family, socktype, protocol, sockaddr))
    return addresses


def _connect(
    addresses: list[tuple[int, int, int, tuple[object, ...]]], timeout: float
) -> socket.socket:
    last_error: OSError | None = None
    for family, socktype, protocol, sockaddr in addresses:
        sock = socket.socket(family, socktype, protocol)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            return sock
        except OSError as error:
            last_error = error
            sock.close()
    raise OSError(f"could not connect to any validated address: {last_error}")


class DirectHTTPConnection(http.client.HTTPConnection):
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        addresses: list[tuple[int, int, int, tuple[object, ...]]],
    ) -> None:
        super().__init__(host, port, timeout=timeout)
        self._addresses = addresses

    def connect(self) -> None:
        self.sock = _connect(self._addresses, self.timeout)


class DirectHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        addresses: list[tuple[int, int, int, tuple[object, ...]]],
    ) -> None:
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._addresses = addresses

    def connect(self) -> None:
        raw_socket = _connect(self._addresses, self.timeout)
        try:
            # The original hostname is retained for TLS SNI and certificate verification.
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except BaseException:
            raw_socket.close()
            raise


def _request_once(url: str, method: str, settings: Settings) -> Response:
    target = parse_target(url)
    addresses = _public_addresses(target.hostname, target.port)
    connection_class = DirectHTTPSConnection if target.scheme == "https" else DirectHTTPConnection
    connection = connection_class(target.hostname, target.port, settings.timeout, addresses)
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "Host": target.host_header,
        "User-Agent": USER_AGENT,
    }
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    try:
        connection.request(method, target.request_target, headers=headers)
        response = connection.getresponse()
        return Response(response.status, response.getheader("Location"))
    finally:
        # Do not consume response bodies. Closing is sufficient for this one-shot connection.
        connection.close()


def _request_chain(original_url: str, method: str, settings: Settings) -> ChainResult:
    current_url = original_url
    visited: set[str] = set()
    for redirect_count in range(settings.max_redirects + 1):
        try:
            current_url = parse_target(current_url).url
            if current_url in visited:
                return ChainResult(False, current_url, error="redirect loop detected", hard_failure=True)
            visited.add(current_url)
            response = _request_once(current_url, method, settings)
        except UnsafeTarget as error:
            return ChainResult(False, current_url, error=f"unsafe target: {error}", hard_failure=True)
        except (OSError, ssl.SSLError, http.client.HTTPException) as error:
            return ChainResult(False, current_url, error=f"{type(error).__name__}: {error}")

        if 200 <= response.status < 300:
            return ChainResult(True, current_url, status=response.status)
        if response.status not in REDIRECT_STATUSES:
            return ChainResult(False, current_url, status=response.status)
        if not response.location:
            return ChainResult(
                False,
                current_url,
                status=response.status,
                error=f"HTTP {response.status} redirect has no Location header",
                hard_failure=True,
            )
        if redirect_count == settings.max_redirects:
            return ChainResult(
                False,
                current_url,
                status=response.status,
                error=f"more than {settings.max_redirects} redirects",
                hard_failure=True,
            )
        try:
            current_url = parse_target(urljoin(current_url, response.location)).url
        except UnsafeTarget as error:
            return ChainResult(
                False,
                current_url,
                error=f"unsafe redirect target {response.location!r}: {error}",
                hard_failure=True,
            )
    raise AssertionError("unreachable redirect state")


def _probe_once(url: str, settings: Settings) -> tuple[bool, str, bool]:
    head = _request_chain(url, "HEAD", settings)
    if head.success:
        return True, f"HEAD {head.status} at {head.final_url}", False
    if head.hard_failure:
        return False, f"HEAD: {head.describe()}", False

    # Some servers reject or mishandle HEAD. Restart at the original URL with a one-byte GET.
    get = _request_chain(url, "GET", settings)
    if get.success:
        return True, f"GET {get.status} at {get.final_url} (HEAD: {head.describe()})", False
    return False, f"HEAD: {head.describe()}; GET: {get.describe()}", get.retryable


def check_url(
    url: str, settings: Settings, sleep: Callable[[float], None] = time.sleep
) -> CheckResult:
    try:
        normalized = parse_target(url).url
    except UnsafeTarget as error:
        return CheckResult(url, False, f"unsafe target: {error}")

    detail = ""
    for attempt in range(settings.retries + 1):
        success, detail, retryable = _probe_once(normalized, settings)
        if success:
            return CheckResult(normalized, True, detail)
        if not retryable or attempt == settings.retries:
            break
        delay = settings.backoff * (2**attempt)
        sleep(delay)
    return CheckResult(normalized, False, detail)


def _target_with_line_locations(text: str) -> list[tuple[str, int]]:
    return markdown.extract_targets_with_lines(text)


def collect_external_links(paths: list[Path] | None = None) -> dict[str, list[str]]:
    links: dict[str, set[str]] = {}
    for source in paths if paths is not None else markdown.tracked_markdown():
        text = source.read_text(encoding="utf-8")
        for raw_target, line in _target_with_line_locations(text):
            target = markdown.normalize_target(raw_target)
            if not re.match(r"^https?://", target, re.IGNORECASE):
                continue
            try:
                network_url = parse_target(target).url
            except UnsafeTarget:
                network_url = target.split("#", 1)[0]
            # as_posix() so reported locations use forward slashes on every
            # platform; str() on a Windows path yields "docs\guide.md".
            location = f"{source.relative_to(REPOSITORY_ROOT).as_posix()}:{line}"
            links.setdefault(network_url, set()).add(location)
    return {url: sorted(locations) for url, locations in sorted(links.items())}


def load_ignore_file(path: Path) -> dict[str, str]:
    rules: dict[str, str] = {}
    dated_comment: tuple[str, str] | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            dated_comment = None
            continue
        if line.startswith("#"):
            match = DATED_COMMENT.match(line)
            if match:
                try:
                    date.fromisoformat(match.group(1))
                except ValueError as error:
                    raise ValueError(
                        f"{path}:{line_number}: invalid evidence date {match.group(1)!r}"
                    ) from error
                dated_comment = (match.group(1), match.group(2))
            else:
                dated_comment = None
            continue
        domain = line.lower().rstrip(".")
        if (
            dated_comment is None
            or not DOMAIN.fullmatch(domain)
            or "*" in domain
            or "/" in domain
            or ".." in domain
        ):
            raise ValueError(
                f"{path}:{line_number}: each exact domain needs an immediately preceding "
                "'# YYYY-MM-DD: observed reason' comment"
            )
        if domain in rules:
            raise ValueError(f"{path}:{line_number}: duplicate domain {domain}")
        rules[domain] = f"{dated_comment[0]}: {dated_comment[1]}"
        dated_comment = None
    return rules


def matching_ignore(hostname: str, rules: dict[str, str]) -> tuple[str, str] | None:
    host = hostname.lower().rstrip(".")
    for domain, reason in rules.items():
        if host == domain or host.endswith(f".{domain}"):
            return domain, reason
    return None


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-ignore", action="store_true", help="audit every URL, including ignored domains")
    parser.add_argument("--ignore-file", type=Path, default=DEFAULT_IGNORE_FILE)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--backoff", type=float, default=1.0)
    parser.add_argument("--max-redirects", type=int, default=5)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Markdown files to check; defaults to every tracked Markdown file when omitted",
    )
    return parser.parse_args()


def _selected_markdown(paths: list[Path]) -> list[Path]:
    """Resolve requested Markdown paths, ignoring non-Markdown or untracked entries."""
    tracked = {path.resolve(): path for path in markdown.tracked_markdown()}
    selected: list[Path] = []
    for path in paths:
        resolved = (path if path.is_absolute() else (REPOSITORY_ROOT / path)).resolve()
        tracked_path = tracked.get(resolved)
        if tracked_path is not None and tracked_path not in selected:
            selected.append(tracked_path)
    return selected


def main() -> int:
    arguments = _arguments()
    if (
        arguments.workers < 1
        or arguments.timeout <= 0
        or arguments.retries < 0
        or arguments.backoff < 0
        or arguments.max_redirects < 0
    ):
        print("invalid checker limits", file=sys.stderr)
        return 2
    try:
        ignore_rules = load_ignore_file(arguments.ignore_file)
    except (OSError, ValueError) as error:
        print(f"Cannot load external-link ignore file: {error}", file=sys.stderr)
        return 2

    if arguments.paths:
        selected = _selected_markdown(arguments.paths)
        if not selected:
            print("No tracked Markdown files selected; nothing to check")
            return 0
        links = collect_external_links(selected)
    else:
        links = collect_external_links()
    ignored: dict[str, tuple[str, str]] = {}
    to_check: list[str] = []
    malformed: list[CheckResult] = []
    for url in links:
        try:
            target = parse_target(url)
        except UnsafeTarget as error:
            malformed.append(CheckResult(url, False, f"unsafe target: {error}"))
            continue
        rule = matching_ignore(target.hostname, ignore_rules)
        if rule and not arguments.no_ignore:
            ignored[url] = rule
        else:
            to_check.append(url)

    settings = Settings(arguments.timeout, arguments.retries, arguments.backoff, arguments.max_redirects)
    results = list(malformed)
    if to_check:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(arguments.workers, len(to_check))) as executor:
            results.extend(executor.map(lambda url: check_url(url, settings), to_check))
    failures = sorted((result for result in results if not result.success), key=lambda result: result.url)

    if ignored:
        ignored_domains = sorted({domain for domain, _ in ignored.values()})
        print(
            f"Ignored {len(ignored)} URL(s) on documented bot-blocking domain(s): "
            f"{', '.join(ignored_domains)}"
        )
    if failures:
        print(
            f"External Markdown link validation failed: {len(failures)} of {len(results)} checked URL(s)",
            file=sys.stderr,
        )
        for result in failures:
            print(f"  {result.url}\n    {result.detail}", file=sys.stderr)
            for location in links[result.url]:
                print(f"    linked from {location}", file=sys.stderr)
        return 1

    occurrence_count = sum(len(locations) for locations in links.values())
    print(
        "External Markdown links valid "
        f"({len(results)} unique URL(s) checked, {len(ignored)} ignored, "
        f"{occurrence_count} source location(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
