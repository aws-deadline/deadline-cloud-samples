#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
KeyShot Bridge

This script opens the KeyShot subprocess and forwards data from socket clients to the
processes's STDIN. It runs for the duration of the session.
"""

import argparse
import asyncio
from asyncio import Server, StreamReader, StreamWriter
from asyncio.subprocess import Process, PIPE
import os
import sys
from pathlib import Path
import shutil


def get_keyshot_executable() -> str:
    """Find the KeyShot executable in the system."""
    possible_exes = [
        os.environ.get("KEYSHOT_EXECUTABLE"),
        f"{os.environ.get('KEYSHOT_LOCATION')}\\bin\\keyshot_headless.exe",
        "keyshot_headless.exe",
        "keyshot_headless",
        "keyshot",
    ]

    for possible_exe in possible_exes:
        if possible_exe:
            found_exe = shutil.which(possible_exe)
            if found_exe:
                return found_exe

    raise FileNotFoundError("Cannot find KeyShot executable. Looked for: " + str(possible_exes))


async def start_socket_server(process: Process, port: int) -> tuple[Server, asyncio.Task]:
    # Create shared output queue for all clients. We need to keep read KeyShot's STDOUT even when
    # there's not a client (e.g. between tasks) so the buffer doens't fill and crash KeyShot.
    output_queue: asyncio.Queue = asyncio.Queue()
    keyshot_task = asyncio.create_task(continuous_keyshot_reader(process, output_queue))

    # Multiple clients will connect and disconnect over a session. Each task will connact as a
    # separate client. There should be only 1 client connected at a time.
    async def client_handler(reader: StreamReader, writer: StreamWriter) -> None:
        print("Client connected")
        await handle_client(reader, writer, process, output_queue)
        print("Client disconnected")

    # Bind to loopback interface only to prevent external network access
    return await asyncio.start_server(client_handler, "127.0.0.1", port), keyshot_task


async def continuous_keyshot_reader(process: Process, output_queue: asyncio.Queue) -> None:
    """Always reads KeyShot output to prevent blocking, independent of client connections."""
    while process.returncode is None:
        if line := await process.stdout.readline():  # type: ignore[union-attr]
            await output_queue.put(line)
        else:
            break


async def handle_client(
    reader: StreamReader, writer: StreamWriter, process: Process, output_queue: asyncio.Queue
) -> None:
    async def forward_to_keyshot(source: StreamReader, destination: StreamWriter) -> None:
        while process.returncode is None:
            if line := await source.readline():
                print(f"[Client -> KeyShot] {line.decode().strip()}")
                destination.write(line)
                await destination.drain()
            else:
                break

    async def forward_from_queue(queue: asyncio.Queue, destination: StreamWriter) -> None:
        while True:
            line = await queue.get()
            destination.write(line)
            await destination.drain()
            queue.task_done()

    # Create tasks for client communication only
    client_task = asyncio.create_task(forward_to_keyshot(reader, process.stdin))  # type: ignore[arg-type]
    output_task = asyncio.create_task(forward_from_queue(output_queue, writer))

    try:
        _, pending = await asyncio.wait(
            [client_task, output_task], return_when=asyncio.FIRST_COMPLETED
        )

        # When one task ends, cancel the other
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="KeyShot Bridge - Socket server for KeyShot communication"
    )
    parser.add_argument("--scene-file", required=True, help="Path to KeyShot scene file")
    parser.add_argument(
        "--keyshot-command-handler-script", required=True, help="Path to KeyShot command handler"
    )
    parser.add_argument("--port", type=int, help="Port for socket server")
    args = parser.parse_args()

    # Validate inputs
    if not Path(args.scene_file).exists():
        raise FileNotFoundError(f"Scene file not found: {args.scene_file}")

    if not Path(args.keyshot_command_handler_script).exists():
        raise FileNotFoundError(f"Command handler not found: {args.keyshot_command_handler_script}")

    # Build KeyShot command line arguments
    cmd = [
        get_keyshot_executable(),
        # On Mac and Linux, the -headless flag is required. Omit it on Windows.
        *([] if os.name == "nt" else ["-headless"]),
        "-progress",
        "-floating_feature",
        "keyshot2",
        "--scene-file",
        args.scene_file,
        "-script",
        args.keyshot_command_handler_script,
    ]

    print(f"Starting KeyShot: {' '.join(cmd)}")
    sys.stdout.flush()

    process = None
    server = None
    try:
        # Start KeyShot process using asyncio subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        print(f"KeyShot process started with PID: {process.pid}")

        # Save _keyshot_task in a variable so it isn't garbage collected
        server, _keyshot_task = await start_socket_server(process, port=args.port)
        print(f"Socket server listening on port {args.port}")

        # Check if KeyShot process is still running
        if process.returncode is not None:
            error_message = f"ERROR: KeyShot process exited early with code: {process.returncode}"
            if process.stderr is not None:
                stderr_output = await process.stderr.read()
                if stderr_output:
                    error_message += f"\nKeyShot stderr: {stderr_output.decode()}"
            raise RuntimeError(error_message)

        print("KeyShot server is ready")
        sys.stdout.flush()

        await process.wait()
        print(f"KeyShot process ended with return code: {process.returncode}")
    finally:
        print("Closing KeyShot bridge...")
        if server:
            server.close()
            await server.wait_closed()
            print("Socket server closed")
        if process:
            # Try to terminate gracefully first
            process.terminate()

            # Wait a bit for graceful shutdown
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                # Force kill if it doesn't terminate gracefully
                print("Force killing KeyShot process...")
                process.kill()
                await process.wait()

            print(f"KeyShot process (PID: {process.pid}) terminated")


if __name__ == "__main__":
    asyncio.run(main())
