#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
KeyShot Session Manager

Start launches the KeyShot bridge and waits for session establishment.
Stop connects to the bridge and sends a termination command to KeyShot.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SESSION_INFO_FILE = "keyshot_session_info.json"
MAX_PORT_DISCOVERY_ATTEMPTS = 100
STARTUP_TIMEOUT_SECONDS = 15 * 60  # 15 minutes. Leaves time to open a large scene.


def find_available_port_and_start_bridge(bridge_cmd: list) -> tuple[subprocess.Popen, int]:
    """Find available port and start bridge in one operation."""
    start_port = 9000
    for port in range(start_port, start_port + MAX_PORT_DISCOVERY_ATTEMPTS):
        # Try to start bridge with this port - let it fail if port is taken
        cmd_with_port = bridge_cmd + ["--port", str(port)]

        popen_kwargs = {
            "shell": False,
            "close_fds": True,
            "start_new_session": True,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,  # Capture output to check for errors
            "stderr": subprocess.PIPE,
        }

        if os.name == "nt":  # Windows
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        try:
            process = subprocess.Popen(cmd_with_port, **popen_kwargs)  # type: ignore[call-overload]
        except OSError:
            # Failed to start process, try next port
            continue

        # Give the process a moment to start and potentially fail due to port conflict
        time.sleep(0.5)

        # Check if process is still running (didn't fail due to port conflict)
        if process.poll() is None:
            return process, port

    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + MAX_PORT_DISCOVERY_ATTEMPTS - 1}"
    )


def write_session_info(port: int) -> None:
    with open(SESSION_INFO_FILE, "w") as f:
        json.dump({"port": port}, f)


def read_session_info() -> int:
    with open(SESSION_INFO_FILE, "r") as f:
        return int(json.load(f)["port"])


async def wait_for_server_ready(reader: asyncio.StreamReader, timeout_deadline: float) -> None:
    while time.time() < timeout_deadline:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=1.0)
            if line:
                output = line.decode().strip()
                print(output)
                sys.stdout.flush()
                if "KeyShot server is ready" in output:
                    return
        except asyncio.TimeoutError:
            continue

    raise asyncio.TimeoutError("Timeout waiting for KeyShot server to be ready")


async def connect_and_validate(port: int) -> None:
    timeout_deadline = time.time() + STARTUP_TIMEOUT_SECONDS

    while time.time() < timeout_deadline:
        try:
            reader, writer = await asyncio.open_connection("localhost", port)
            print(f"Connected to KeyShot bridge on port {port}")

            try:
                await wait_for_server_ready(reader, timeout_deadline)
                print("KeyShot server is ready - session startup complete")
                return
            finally:
                writer.close()
                await writer.wait_closed()

        except OSError:
            # Bridge not ready yet, wait and retry
            await asyncio.sleep(1)
            continue

    raise RuntimeError("Timeout: Could not connect to bridge or receive ready message")


async def send_stop_command() -> None:
    port = read_session_info()
    try:
        _reader, writer = await asyncio.open_connection("localhost", port)
        print(f"Connected to KeyShot bridge on port {port}")

        command_json = json.dumps({"command": "stop"}) + "\n"
        writer.write(command_json.encode())
        await writer.drain()
        print("Sent stop command to KeyShot server")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:  # noqa: E722
            # Ignore any errors while closing the connection since we're exiting
            pass

    print("Stop command sent successfully")


async def start_session(scene_file: str, script_executor: str, bridge_script: str) -> None:
    # Build KeyShot bridge command (without port)
    bridge_cmd = [
        sys.executable,
        bridge_script,
        "--scene-file",
        scene_file,
        "--keyshot-command-handler-script",
        script_executor,
    ]

    print("Starting KeyShot bridge...")

    # Find available port and start bridge atomically
    bridge_process, port = find_available_port_and_start_bridge(bridge_cmd)
    print(f"KeyShot bridge started. Port:{port} PID: {bridge_process.pid}")
    write_session_info(port)

    print(f"Waiting for KeyShot server to be ready (timeout: {STARTUP_TIMEOUT_SECONDS}s)...")
    await connect_and_validate(port)

    # Check if bridge process is still running
    if bridge_process.poll() is not None:
        raise RuntimeError(
            f"WARNING: Bridge process (PID: {bridge_process.pid}) has exited with code: {bridge_process.returncode}"
        )

    print("Session manager started successfully")


async def main() -> None:
    parser = argparse.ArgumentParser(description="KeyShot Session Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Start subcommand
    start_parser = subparsers.add_parser("start", help="Start the KeyShot session")
    start_parser.add_argument("--scene-file", required=True, help="Path to KeyShot scene file")
    start_parser.add_argument(
        "--keyshot-command-handler-script", required=True, help="Path to KeyShot command handler"
    )
    start_parser.add_argument(
        "--keyshot-bridge-script", required=True, help="Path to KeyShot bridge"
    )

    # Stop subcommand
    subparsers.add_parser("stop", help="Stop the KeyShot session")

    args = parser.parse_args()

    if args.command == "start":
        if not Path(args.scene_file).exists():
            raise RuntimeError(f"ERROR: Scene file not found: {args.scene_file}")
        if not Path(args.keyshot_command_handler_script).exists():
            raise RuntimeError(
                f"ERROR: Command handler not found: {args.keyshot_command_handler_script}"
            )
        if not Path(args.keyshot_bridge_script).exists():
            raise RuntimeError(f"ERROR: Bridge not found: {args.keyshot_bridge_script}")

        return await start_session(
            args.scene_file,
            args.keyshot_command_handler_script,
            args.keyshot_bridge_script,
        )

    elif args.command == "stop":
        return await send_stop_command()


if __name__ == "__main__":
    asyncio.run(main())
