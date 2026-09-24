"""Requests one frame from the Octane daemon."""

import argparse
import json
import socket
import sys


def print_lines(text):
    """Print verbatim so OpenJD macros still reach the agent."""
    for line in str(text).splitlines():
        print(line, flush=True)


def fail(reason, detail=None, show_in_monitor=False):
    print(("openjd_fail: " if show_in_monitor else "") + reason, flush=True)
    if detail:
        sys.stderr.write(detail + "\n")
    sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connection-file", required=True)
    parser.add_argument("--frame", type=int, required=True)
    return parser.parse_args()


def connect_to_daemon(connection_file_path):
    try:
        with open(connection_file_path) as connection_file:
            connection_info = json.load(connection_file)
    except (OSError, ValueError) as error:
        fail("could not read the Octane connection file at {}: {}".format(
            connection_file_path, error))

    daemon_socket_path = connection_info.get("socket")
    if not daemon_socket_path:
        fail("the connection file does not describe a running Octane daemon, so the "
             "environment that starts Octane did not finish")

    daemon_connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        daemon_connection.connect(daemon_socket_path)
    except OSError as error:
        daemon_connection.close()
        # The daemon reports its own failure when it stops.
        fail("could not reach the Octane daemon at {}: {}".format(
            daemon_socket_path, error))

    return daemon_connection


def send_render_command(daemon_connection, frame):
    print("openjd_status: rendering frame {}".format(frame), flush=True)
    try:
        with daemon_connection.makefile("w") as to_daemon:
            to_daemon.write(json.dumps({
                "action": "render",
                "frame": frame,
            }) + "\n")
            to_daemon.flush()
    except OSError as error:
        fail("could not ask the Octane daemon for frame {}: {}".format(frame, error))


def receive_response(daemon_connection, frame):
    try:
        with daemon_connection.makefile("r") as from_daemon:
            for line in from_daemon:
                try:
                    message = json.loads(line)
                except ValueError:
                    fail("the Octane daemon sent something that is not a message",
                         "the line was: " + line.strip())
                if message.get("type") == "log":
                    print_lines(message.get("message", ""))
                else:
                    return message
    except OSError as error:
        fail("lost contact with the Octane daemon during frame {}: {}".format(
            frame, error))

    fail("the Octane daemon closed the connection without finishing frame {}".format(
        frame))


def process_response(response, frame):
    response_type = response.get("type")
    if response_type == "error":
        reported = str(response.get("message", ""))
        print_lines(reported)
        reported_lines = reported.splitlines()
        fail("frame {} failed: {}".format(
            frame, reported_lines[0] if reported_lines else "no reason was given"),
            show_in_monitor=True)
    elif response_type != "reply":
        print_lines(json.dumps(response))
        fail("the Octane daemon answered frame {} with a '{}' message, which this client "
             "does not understand".format(frame, response_type))

    # A response for another frame cannot describe this task's files.
    responded_frame = response.get("frame")
    if responded_frame != frame:
        fail("the Octane daemon answered with frame {} while this task is frame {}".format(
            responded_frame, frame))

    print_lines(response.get("message", ""))

    output_files = response.get("files", [])
    print("Wrote {} file(s):".format(len(output_files)), flush=True)
    for output_path in output_files:
        print("  " + output_path, flush=True)
    print("openjd_progress: 100", flush=True)


def main():
    args = parse_arguments()
    with connect_to_daemon(args.connection_file) as daemon_connection:
        send_render_command(daemon_connection, args.frame)
        response = receive_response(daemon_connection, args.frame)
        process_response(response, args.frame)


if __name__ == "__main__":
    main()
