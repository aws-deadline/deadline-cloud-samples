# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from task_manager import main, check_line_for_completion, send_command_and_monitor


class TestTaskManager:

    @patch("task_manager.send_command_and_monitor", new_callable=AsyncMock)
    @patch("task_manager.read_session_info", return_value=9000)
    def test_render_command_generation(self, mock_read_session_info, mock_send):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "render_%d.png")

            with patch(
                "sys.argv",
                [
                    "task_manager.py",
                    "--frame",
                    "42",
                    "--output-path",
                    output_path,
                    "--output-format",
                    "EXR",
                    "--render-device",
                    "GPU",
                ],
            ):
                asyncio.run(main())

            # Verify session info was read
            mock_read_session_info.assert_called_once()

            # Verify JSON command was sent
            mock_send.assert_called_once()
            command = mock_send.call_args[0][0]  # First argument to send_command_and_monitor

            assert command["command"] == "render"
            assert command["frame"] == 42
            assert "render_42.png" in command["output_path"]
            assert command["output_format"] == "EXR"
            assert command["render_device"] == "GPU"

    def test_read_session_info_file(self):
        # Test that session info is properly read (without mocking the function we're testing)
        from task_manager import read_session_info

        with tempfile.TemporaryDirectory() as temp_dir:
            session_file = Path(temp_dir) / "keyshot_session_info.json"
            session_data = {"port": 8080}

            with open(session_file, "w") as f:
                import json

                json.dump(session_data, f)

            with patch("task_manager.SESSION_INFO_FILE", str(session_file)):
                port = read_session_info()
                assert port == 8080

    def test_check_line_for_completion(self):
        from task_manager import check_line_for_completion

        # Test success detection
        assert check_line_for_completion("ADAPTOR_STATUS=Success FRAME=1", 1)
        assert not check_line_for_completion("ADAPTOR_STATUS=Success FRAME=2", 1)

        # Test error detection raises exception
        with pytest.raises(RuntimeError):
            check_line_for_completion("ADAPTOR_STATUS=Error Error=Something failed", 1)

        # Test normal output
        assert not check_line_for_completion("Rendering frame 1...", 1)
        assert not check_line_for_completion("", 1)

    def test_frame_substitution_in_output_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_template = str(Path(temp_dir) / "render_%d.png")

            with patch(
                "sys.argv",
                [
                    "task_manager.py",
                    "--frame",
                    "42",
                    "--output-path",
                    output_template,
                    "--output-format",
                    "PNG",
                    "--render-device",
                    "CPU",
                ],
            ):
                with patch(
                    "task_manager.send_command_and_monitor", new_callable=AsyncMock
                ) as mock_send:
                    with patch("task_manager.read_session_info", return_value=9000):
                        asyncio.run(main())

                command = mock_send.call_args[0][0]
                expected_path = str(Path(temp_dir) / "render_42.png")
                assert command["output_path"] == expected_path

            # Verify send_command_and_monitor called with correct parameters
            mock_send.assert_called_once_with(command, 42, 9000)

    def test_progress_and_completion_monitoring(self):
        # Test success completion
        success_line = "ADAPTOR_STATUS=Success FRAME=5"
        assert check_line_for_completion(success_line, 5)

        # Test error completion
        error_line = "ADAPTOR_STATUS=Error FRAME=5 Error=Render failed"
        with pytest.raises(RuntimeError, match="Render failed"):
            check_line_for_completion(error_line, 5)

        # Test wrong frame number
        wrong_frame_line = "ADAPTOR_STATUS=Success FRAME=10"
        assert not check_line_for_completion(wrong_frame_line, 5)

        # Test progress pattern matching
        progress_line = "KeyShot: [I] Rendering: 54.5%"
        with patch("builtins.print") as mock_print:
            result = check_line_for_completion(progress_line, 5)
            assert not result
            mock_print.assert_called_with("openjd_progress: 54.5")

    @pytest.mark.asyncio
    async def test_socket_communication_and_timeout(self):
        # Test successful communication
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        # Mock successful completion
        mock_reader.readline.side_effect = [
            b"KeyShot starting\n",
            b"ADAPTOR_STATUS=Success FRAME=1\n",
        ]

        command = {"command": "render", "frame": 1, "output_path": "/path/output.png"}

        with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            await send_command_and_monitor(command, 1, 1234)

        # Verify connection and JSON command sending
        expected_json = b'{"command": "render", "frame": 1, "output_path": "/path/output.png"}\n'
        mock_writer.write.assert_called_once_with(expected_json)
        mock_writer.drain.assert_called_once()
        mock_writer.close.assert_called_once()

        # Test timeout scenario with fresh mocks
        mock_reader_timeout = AsyncMock()
        mock_writer_timeout = MagicMock()
        mock_writer_timeout.write = MagicMock()
        mock_writer_timeout.drain = AsyncMock()
        mock_writer_timeout.close = MagicMock()
        mock_writer_timeout.wait_closed = AsyncMock()

        # Mock continuous non-completion messages
        mock_reader_timeout.readline.return_value = b"KeyShot starting\n"

        with patch(
            "asyncio.open_connection", return_value=(mock_reader_timeout, mock_writer_timeout)
        ):
            with patch("time.time", side_effect=[0, 0, 100000]):  # Simulate timeout
                with pytest.raises(RuntimeError, match="Timeout waiting for frame"):
                    command = {"command": "render", "frame": 1, "output_path": "/path/output.png"}
                    await send_command_and_monitor(command, 1, 1234)

        # Test connection closed by server with fresh mocks
        mock_reader_closed = AsyncMock()
        mock_writer_closed = MagicMock()
        mock_writer_closed.write = MagicMock()
        mock_writer_closed.drain = AsyncMock()
        mock_writer_closed.close = MagicMock()
        mock_writer_closed.wait_closed = AsyncMock()

        mock_reader_closed.readline.return_value = b""  # EOF

        with patch(
            "asyncio.open_connection", return_value=(mock_reader_closed, mock_writer_closed)
        ):
            with pytest.raises(RuntimeError, match="Socket connection closed by server"):
                command = {"command": "render", "frame": 1, "output_path": "/path/output.png"}
                await send_command_and_monitor(command, 1, 1234)
