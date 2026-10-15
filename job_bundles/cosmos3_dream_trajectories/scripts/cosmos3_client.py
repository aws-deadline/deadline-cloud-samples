"""Minimal vLLM-Omni client for NVIDIA Cosmos 3, standard library only.

This runs inside whatever container the queue environment started, so the Python
version is the image's, not the worker's. `vllm/vllm-omni:cosmos3` carries 3.12.
Installing `requests` per task would add a network dependency to every task, so
this module speaks multipart/form-data over urllib instead. It is kept 3.9
compatible and dependency free so the same scripts run under `openjd run` on a
plain host, where the system Python can be much older.

Two endpoints are used, and they are not interchangeable:

  POST /v1/videos/sync   returns the generated MP4 bytes in the response body.
  POST /v1/videos        returns a job id; poll GET /v1/videos/{id} until
                         status == completed, then read the `action` object.

Inverse dynamics only reports through the async endpoint, because its payload is
an action array rather than a video. Forward dynamics and image-to-video use the
sync endpoint. Source: the vLLM-Omni examples on the nvidia/Cosmos3-Nano model
card.
"""

import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid


class Cosmos3Error(RuntimeError):
    """A request failed, or the server reported a failed job."""


def _encode_multipart(fields, files):
    """Build a multipart/form-data body.

    `fields` maps name -> str. `files` maps name -> (filename, bytes, mime).
    Returns (content_type, body_bytes).
    """
    boundary = "----cosmos3-" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        out += ("--%s\r\n" % boundary).encode("utf-8")
        out += ('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode("utf-8")
        out += str(value).encode("utf-8")
        out += b"\r\n"
    for name, (filename, payload, mime) in files.items():
        out += ("--%s\r\n" % boundary).encode("utf-8")
        out += (
            'Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (name, filename)
        ).encode("utf-8")
        out += ("Content-Type: %s\r\n\r\n" % mime).encode("utf-8")
        out += payload
        out += b"\r\n"
    out += ("--%s--\r\n" % boundary).encode("utf-8")
    return "multipart/form-data; boundary=%s" % boundary, bytes(out)


def _request(url, method="GET", body=None, content_type=None, accept=None, timeout=600):
    req = urllib.request.Request(url, data=body, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    if accept:
        req.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:4000]
        # Surface the server's own message. Cosmos 3 rejects an unsupported
        # domain_name / raw_action_dim combination here, and the text is the
        # only authoritative list of what it accepts.
        raise Cosmos3Error(
            "HTTP %s from %s %s\n%s" % (exc.code, method, url, detail)
        ) from exc
    except urllib.error.URLError as exc:
        raise Cosmos3Error("could not reach %s: %s" % (url, exc.reason)) from exc


def guess_mime(path, fallback="application/octet-stream"):
    return mimetypes.guess_type(path)[0] or fallback


def process_alive(pid):
    """True when `pid` still exists. Signal 0 only checks for existence."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_server(base_url, timeout_seconds, poll_seconds=5.0, log=print, pid=None):
    """Block until the server answers, or raise after timeout_seconds.

    Loading a 16B checkpoint is slow, and on first use the weights are still
    downloading, so this is minutes rather than seconds. `vllm serve` is given
    --init-timeout 1800 on the model card for the same reason.

    When `pid` is given, a dead server is reported immediately instead of after
    the full timeout. Almost every startup failure is a crash rather than a hang,
    and waiting 45 minutes to be told so wastes a GPU hour.
    """
    deadline = time.time() + timeout_seconds
    last_error = "never attempted"
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        if pid is not None and not process_alive(pid):
            raise Cosmos3Error(
                "the server process (pid %d) exited during startup after %ds. "
                "Its log holds the reason; out-of-memory is the usual one."
                % (pid, int(timeout_seconds - (deadline - time.time())))
            )
        # Probe /health, then /v1/models. vLLM serves /health, but the Omni
        # build's documented surface is only the /v1/videos endpoints, so do not
        # depend on /health alone being present.
        for probe in ("/health", "/v1/models"):
            try:
                status, _ = _request(base_url.rstrip("/") + probe, timeout=15)
                if status == 200:
                    log("server healthy on %s after %d probe(s)" % (probe, attempt))
                    return
                last_error = "%s returned %s" % (probe, status)
            except Cosmos3Error as exc:
                last_error = str(exc).splitlines()[0]
        if attempt % 12 == 1:
            log(
                "waiting for Cosmos 3 server (%ds left): %s"
                % (int(deadline - time.time()), last_error)
            )
        time.sleep(poll_seconds)
    raise Cosmos3Error(
        "Cosmos 3 server did not become healthy within %ds. Last probe: %s"
        % (timeout_seconds, last_error)
    )


def generate_sync(base_url, fields, files, timeout=1800):
    """POST /v1/videos/sync and return the response body (MP4 bytes)."""
    content_type, body = _encode_multipart(fields, files)
    _, payload = _request(
        base_url.rstrip("/") + "/v1/videos/sync",
        method="POST",
        body=body,
        content_type=content_type,
        accept="video/mp4",
        timeout=timeout,
    )
    if not payload:
        raise Cosmos3Error("/v1/videos/sync returned an empty body")
    # An MP4 has 'ftyp' at bytes 4..8. A JSON error body that arrived with a 200
    # would silently become a zero-frame video file otherwise.
    if payload[4:8] != b"ftyp":
        head = payload[:400].decode("utf-8", "replace")
        raise Cosmos3Error(
            "/v1/videos/sync returned %d bytes that are not an MP4: %s" % (len(payload), head)
        )
    return payload


def submit_async(base_url, fields, files, timeout=600):
    """POST /v1/videos and return the job id."""
    content_type, body = _encode_multipart(fields, files)
    _, payload = _request(
        base_url.rstrip("/") + "/v1/videos",
        method="POST",
        body=body,
        content_type=content_type,
        timeout=timeout,
    )
    initial = json.loads(payload.decode("utf-8"))
    if "id" not in initial:
        raise Cosmos3Error("/v1/videos response carried no id: %s" % json.dumps(initial)[:2000])
    return initial["id"]


def poll_async(base_url, job_id, timeout_seconds, poll_seconds=2.0, log=print):
    """Poll GET /v1/videos/{id} until completed, and return the final payload."""
    deadline = time.time() + timeout_seconds
    last_progress = None
    while time.time() < deadline:
        _, payload = _request(base_url.rstrip("/") + "/v1/videos/" + job_id, timeout=60)
        final = json.loads(payload.decode("utf-8"))
        status = final.get("status")
        progress = final.get("progress", 0)
        if progress != last_progress:
            log("%s %s %s%%" % (job_id, status, progress))
            last_progress = progress
        if status == "completed":
            return final
        if status in ("failed", "cancelled"):
            raise Cosmos3Error("job %s %s:\n%s" % (job_id, status, json.dumps(final, indent=2)))
        time.sleep(poll_seconds)
    raise Cosmos3Error("job %s did not complete within %ds" % (job_id, timeout_seconds))


def base_url_from_env():
    """Read the URL the step environment published, or fail loudly."""
    url = os.environ.get("COSMOS3_BASE_URL", "").strip()
    if not url:
        raise Cosmos3Error(
            "COSMOS3_BASE_URL is unset. The Cosmos3Server step environment "
            "publishes it in its onEnter; this script cannot run without it."
        )
    return url


def _main(argv):
    """`python3 cosmos3_client.py --wait <url>` for use from the serve script.

    The health probe lives here rather than in bash because the serving image is
    guaranteed to carry python3 and is not guaranteed to carry curl.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Wait for a Cosmos 3 server.")
    parser.add_argument("--wait", required=True, metavar="URL")
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)

    def log(message):
        print("[cosmos3_client] %s" % message, flush=True)

    try:
        wait_for_server(
            args.wait,
            timeout_seconds=args.timeout,
            poll_seconds=args.poll_seconds,
            log=log,
            pid=args.pid,
        )
    except Cosmos3Error as exc:
        print("openjd_fail: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
