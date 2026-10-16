# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from session_manager import start_session, send_stop_command


class TestSessionManager:

    @pytest.mark.asyncio
    @patch("asyncio.open_connection")
    @patch("session_manager.find_available_port_and_start_bridge")
    @patch("session_manager.write_session_info")
    async def test_start_session_complete(
        self, mock_write_session_info, mock_find_and_start, mock_connection
    ):
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_find_and_start.return_value = (mock_process, 9000)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_connection.return_value = (mock_reader, mock_writer)

        mock_reader.readline.side_effect = [b"KeyShot server is ready\n"]

        with patch("time.time", return_value=0):
            await start_session("scene.ksp", "executor.py", "bridge.py")

        # Verify port discovery and bridge start
        mock_find_and_start.assert_called_once()
        bridge_cmd = mock_find_and_start.call_args[0][0]
        assert "bridge.py" in bridge_cmd
        assert "--scene-file" in bridge_cmd
        assert "scene.ksp" in bridge_cmd

        # Verify session info was written
        mock_write_session_info.assert_called_once_with(9000)

        # Verify connection attempt and cleanup
        mock_connection.assert_called_with("localhost", 9000)

    @pytest.mark.asyncio
    @patch("asyncio.open_connection")
    async def test_send_stop_command(self, mock_connection):
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.drain = AsyncMock()  # Fix: make drain async
        mock_connection.return_value = (mock_reader, mock_writer)

        with patch("session_manager.read_session_info", return_value=9000):
            await send_stop_command()

        # Verify stop command was sent
        mock_writer.write.assert_called_once()
        written_data = mock_writer.write.call_args[0][0]
        assert b'{"command": "stop"}' in written_data

        # Verify connection cleanup
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()

    def test_write_and_read_session_info(self):
        import tempfile  # Fix: add missing import
        from session_manager import write_session_info, read_session_info

        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = os.path.join(temp_dir, "keyshot_session_info.json")

            with patch("session_manager.SESSION_INFO_FILE", session_file):
                # Test writing session info
                write_session_info(8080)
                assert os.path.exists(session_file)

                # Test reading session info
                port = read_session_info()
                assert port == 8080

    @pytest.mark.asyncio
    @patch("asyncio.open_connection")
    @patch("session_manager.read_session_info", return_value=9000)
    async def test_stop_command_complete(self, mock_read_session_info, mock_connection):
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_connection.return_value = (mock_reader, mock_writer)

        await send_stop_command()

        # Verify session info was read
        mock_read_session_info.assert_called_once()

        # Verify connection
        mock_connection.assert_called_once_with("localhost", 9000)

        # Verify JSON stop command sent
        mock_writer.write.assert_called_once_with(b'{"command": "stop"}\n')
        mock_writer.drain.assert_called_once()

        # Verify cleanup
        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("asyncio.open_connection")
    async def test_timeout_scenarios(self, mock_connection):
        # Test connection timeout
        mock_connection.side_effect = ConnectionRefusedError()

        with patch("time.time", side_effect=[0, 9999]):  # Simulate timeout
            with pytest.raises(RuntimeError, match="Timeout: Could not connect"):
                from session_manager import connect_and_validate

                await connect_and_validate(1234)

        # Test server ready timeout
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_connection.side_effect = None
        mock_connection.return_value = (mock_reader, mock_writer)

        mock_reader.readline.return_value = b"Other message\n"

        with patch("time.time", side_effect=[0, 100]):  # Simulate timeout
            with pytest.raises(asyncio.TimeoutError, match="Timeout waiting for KeyShot server"):
                from session_manager import wait_for_server_ready

                await wait_for_server_ready(mock_reader, 0)

    @pytest.mark.asyncio
    @patch("session_manager.find_available_port_and_start_bridge")
    @patch("session_manager.write_session_info")
    async def test_process_failure_scenarios(self, mock_write_session_info, mock_find_and_start):
        # Test bridge process exits early
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 1  # Process exited
        mock_process.returncode = 1
        mock_find_and_start.return_value = (mock_process, 9000)

        with patch("session_manager.connect_and_validate", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="Bridge process.*has exited"):
                await start_session("scene.ksp", "executor.py", "bridge.py")

        # Verify process was checked
        mock_process.poll.assert_called_once()
        assert mock_process.returncode == 1
