"""Keeps the Octane server open for a render session."""

import argparse
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback


SOCKET_FILENAME = "octane.sock"
REQUEST_CHANNEL_FILENAME = "octane_requests"
DAEMON_LOG_FILENAME = "octane_daemon.log"
DAEMON_EXIT_WAIT_SECONDS = 5.0
SERVER_MESSAGE_TYPES = frozenset(("ready", "ack", "reply", "error"))


def parse_server_message(line):
    """Return a known server message, or None when the line is Octane output."""
    try:
        message = json.loads(line)
    except ValueError:
        return None
    if isinstance(message, dict) and message.get("type") in SERVER_MESSAGE_TYPES:
        return message
    return None


def parse_requested_frame(request_line):
    try:
        request = json.loads(request_line)
    except ValueError:
        return None
    return request.get("frame") if isinstance(request, dict) else None


class OctaneDaemon(object):
    def __init__(self, client_listener, server_request_channel, server_process, log_file):
        self.client_listener = client_listener
        self.server_request_channel = server_request_channel
        # The Lua server runs inside this Octane process, so they share one PID.
        self.server_process = server_process
        self.log_file = log_file
        self.log_lock = threading.Lock()
        self.waiting_clients = queue.Queue()
        self.client_connection = None
        self.client_writer = None

    def write_to_log(self, text):
        with self.log_lock:
            self.log_file.write(text + "\n")
            self.log_file.flush()

    def handle_delivery_failure(self, error_message, undelivered_message):
        self.write_to_log("ERROR: {}".format(error_message))
        self.write_to_log("Unable to deliver message: {}".format(undelivered_message))
        self.kill_server()

    def kill_server(self):
        os.kill(self.server_process.pid, signal.SIGKILL)

    def send_to_client(self, message_text):
        try:
            self.client_writer.write(message_text + "\n")
            self.client_writer.flush()
        except (OSError, ValueError) as error:
            # Close first so later output does not report the same loss again.
            self.close_client_connection()
            self.handle_delivery_failure(
                "the task could not be reached ({})".format(error), message_text)

    def close_client_connection(self):
        for closeable in (self.client_writer, self.client_connection):
            if closeable is not None:
                try:
                    closeable.close()
                except OSError:
                    pass
        self.client_writer = None
        self.client_connection = None

    def route_octane_output(self, line):
        if self.client_writer is not None:
            self.send_to_client(json.dumps({"type": "log", "message": line}))
        else:
            self.write_to_log(line)

    def handle_server_message(self, message, payload):
        message_type = message.get("type")
        if message_type == "ack":
            self.on_frame_started(message, payload)
        elif message_type in ("reply", "error"):
            self.on_frame_finished(payload)
        else:
            self.handle_delivery_failure(
                "the server sent a message this daemon does not understand", payload)

    def on_frame_started(self, message, payload):
        if self.client_writer is not None:
            self.handle_delivery_failure(
                "The server started another render before finishing the previous one",
                payload)
            return
        try:
            (self.client_connection,
             self.client_writer,
             requested_frame) = self.waiting_clients.get_nowait()
        except queue.Empty:
            self.handle_delivery_failure(
                "Unable to locate the client that asked for the current render", payload)
            return
        if message.get("frame") != requested_frame:
            self.handle_delivery_failure(
                "The server acknowledged frame {} while the task requested frame {}".format(
                    message.get("frame"), requested_frame),
                payload)

    def on_frame_finished(self, payload):
        if self.client_writer is None:
            self.handle_delivery_failure(
                "The server reported completing a render that was never requested",
                payload)
            return
        self.send_to_client(payload)
        self.close_client_connection()

    def handle_server_exit(self):
        self.write_to_log("Lost connection to the server")
        if self.client_writer is not None:
            self.write_to_log("ERROR: Render was unfinished")
            self.send_to_client(json.dumps({
                "type": "error",
                "message": "Octane stopped before finishing the render.",
            }))
            self.close_client_connection()

    def accept_render_requests(self):
        try:
            while True:
                connection, _ = self.client_listener.accept()
                client_reader = connection.makefile("r")
                client_writer = connection.makefile("w")
                request_line = client_reader.readline().strip()
                # The writer keeps the socket open after the reader closes.
                client_reader.close()
                if not request_line:
                    # A task can only disappear here if its process died. Stop the session
                    # rather than leave later tasks connected to an abandoned listener.
                    self.write_to_log("ERROR: a task connected and disconnected without "
                                      "asking for a frame.")
                    client_writer.close()
                    connection.close()
                    self.kill_server()
                    return

                # Queue the client before sending its request so the ack cannot arrive
                # before the daemon knows which client it belongs to.
                requested_frame = parse_requested_frame(request_line)
                self.waiting_clients.put((connection, client_writer, requested_frame))
                self.server_request_channel.write(request_line + "\n")
                self.server_request_channel.flush()
        except Exception:
            self.write_to_log(
                "ERROR: this daemon stopped accepting tasks:\n" + traceback.format_exc())
            self.kill_server()

    def serve_until_server_exits(self):
        request_thread = threading.Thread(
            target=self.accept_render_requests, daemon=True)
        request_thread.start()
        for raw_line in self.server_process.stdout:
            line = raw_line.rstrip("\n")
            message = parse_server_message(line)
            if message is None:
                self.route_octane_output(line)
            else:
                self.handle_server_message(message, line)
        self.handle_server_exit()
        return 1


def wait_for_scene_ready(server_process):
    for raw_line in server_process.stdout:
        line = raw_line.rstrip("\n")
        print(line, flush=True)
        message = parse_server_message(line)
        if message is not None and message.get("type") == "ready":
            return
    print("openjd_fail: Octane closed unexpectedly while loading the scene.", flush=True)
    sys.exit("Octane closed unexpectedly while loading the scene.")


def launch_server_and_daemon(args):
    if not args.scene:
        sys.exit("Missing scene file. Define one with --scene <scene-file>")

    session_directory = os.path.dirname(os.path.abspath(args.connection_file))
    client_socket_path = os.path.join(session_directory, SOCKET_FILENAME)
    server_requests_path = os.path.join(session_directory, REQUEST_CHANNEL_FILENAME)
    daemon_log_path = os.path.join(session_directory, DAEMON_LOG_FILENAME)
    for path in (client_socket_path, server_requests_path):
        if os.path.exists(path):
            os.remove(path)
    os.mkfifo(server_requests_path)
    daemon_log = open(daemon_log_path, "a", buffering=1)

    client_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_listener.bind(client_socket_path)
    client_listener.listen(1)

    server_request_channel = os.fdopen(
        os.open(server_requests_path, os.O_RDWR), "w", buffering=1)

    octane_binary = os.environ.get("OCTANE_STANDALONE_BINARY", "octane")
    octane_command = [
        octane_binary,
        "--no-gui",
        "--verbose",
        args.scene,
        "--script", args.server_script,
        "-a", "requests=" + server_requests_path,
    ] + args.server_args

    print("openjd_status: Starting: " + " ".join(octane_command), flush=True)
    try:
        server_process = subprocess.Popen(
            octane_command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            # Octane writes its logging and Lua output to stderr.
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError:
        print("Could not start '" + octane_binary + "'. Set OCTANE_STANDALONE_BINARY "
              "to the OctaneRender Standalone executable, or make 'octane' available on "
              "PATH", flush=True)
        return 1

    server_start_time = get_process_start_time(server_process.pid)
    if server_start_time is None:
        kill_and_wait_for_process(server_process.pid)
        sys.exit("Could not read the Octane process start time from /proc.")

    connection_info = {
        "server_pid": server_process.pid,
        "server_start_time": server_start_time,
        "log": daemon_log_path,
    }
    try:
        with open(args.connection_file, "w") as connection_file:
            json.dump(connection_info, connection_file)
    except Exception:
        kill_and_wait_for_process(server_process.pid, server_start_time)
        raise

    wait_for_scene_ready(server_process)

    daemon_pid = os.fork()
    if daemon_pid > 0:
        daemon_start_time = get_process_start_time(daemon_pid)
        connection_info.update({
            "daemon_pid": daemon_pid,
            "daemon_start_time": daemon_start_time,
            "socket": client_socket_path,
        })
        try:
            if daemon_start_time is None:
                raise RuntimeError(
                    "Could not read the Octane daemon process start time from /proc.")
            with open(args.connection_file, "w") as connection_file:
                json.dump(connection_info, connection_file)
        except Exception:
            kill_and_wait_for_process(server_process.pid, server_start_time)
            kill_and_wait_for_process(daemon_pid, daemon_start_time)
            raise
        sys.stdout.flush()
        # The daemon still uses the parent's resources, so do not unwind them here.
        os._exit(0)

    # Detach the daemon from the onEnter action that started it.
    os.setsid()
    os.dup2(daemon_log.fileno(), 1)
    os.dup2(daemon_log.fileno(), 2)
    daemon = OctaneDaemon(
        client_listener, server_request_channel, server_process, daemon_log)
    os._exit(daemon.serve_until_server_exits())


def get_process_start_time(pid):
    try:
        with open("/proc/{}/stat".format(pid)) as stat_file:
            # Fields after the command start with process state (field 3).
            return stat_file.read().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError, TypeError):
        return None


def is_process_running(pid, expected_start_time=None):
    """Return whether the expected process exists and is not a zombie."""
    try:
        os.kill(pid, 0)
    except (OSError, TypeError):
        return False
    try:
        with open("/proc/{}/stat".format(pid)) as stat_file:
            # The command can contain spaces and parentheses, so read after the last one.
            fields = stat_file.read().rsplit(")", 1)[1].split()
            if expected_start_time is not None and fields[19] != expected_start_time:
                return False
            return fields[0] != "Z"
    except (OSError, IndexError):
        return expected_start_time is None


def kill_and_wait_for_process(pid, expected_start_time=None):
    if not is_process_running(pid, expected_start_time):
        return True
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return True
    wait_end = time.time() + DAEMON_EXIT_WAIT_SECONDS
    while time.time() < wait_end:
        if not is_process_running(pid, expected_start_time):
            return True
        time.sleep(0.1)
    return False


def stop_server_and_daemon(args):
    with open(args.connection_file) as connection_file:
        connection_info = json.load(connection_file)
        server_pid = connection_info.get("server_pid")
        server_start_time = connection_info.get("server_start_time")
        daemon_pid = connection_info.get("daemon_pid")
        daemon_start_time = connection_info.get("daemon_start_time")
        daemon_log = connection_info.get("log")

        server_stopped = kill_and_wait_for_process(server_pid, server_start_time)
        print("Stopping server at pid {}.".format(server_pid), flush=True)
        if not server_stopped:
            print("ERROR: Failed to stop server")

        daemon_stopped = kill_and_wait_for_process(daemon_pid, daemon_start_time)
        print("Stopping daemon at pid {}.".format(daemon_pid), flush=True)
        if not daemon_stopped:
            print("ERROR: Failed to stop daemon")

        print("=== Octane daemon log", flush=True)
        with open(daemon_log) as log_file:
            sys.stdout.write(log_file.read())
        print("===", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "stop"])
    parser.add_argument("--connection-file", required=True)
    parser.add_argument("--scene")
    parser.add_argument("--server-script")

    # argparse cannot collect trailing server arguments after these optional arguments.
    daemon_argv = sys.argv[1:]
    server_args = []
    if "--" in daemon_argv:
        separator = daemon_argv.index("--")
        daemon_argv, server_args = daemon_argv[:separator], daemon_argv[separator + 1:]
    args = parser.parse_args(daemon_argv)
    args.server_args = server_args

    if args.command == "start":
        return launch_server_and_daemon(args)
    return stop_server_and_daemon(args)


if __name__ == "__main__":
    sys.exit(main())
