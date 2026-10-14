# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
import os
from unittest import mock
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Mock lux module before importing our code
sys.modules["lux"] = mock.MagicMock()
import lux  # noqa: E402

# Set up the engine constants BEFORE importing our module
RENDER_ENGINE_PRODUCT = 0
RENDER_ENGINE_INTERIOR = 1
RENDER_ENGINE_PRODUCT_GPU = 3
RENDER_ENGINE_INTERIOR_GPU = 4

lux.RENDER_ENGINE_PRODUCT = RENDER_ENGINE_PRODUCT
lux.RENDER_ENGINE_INTERIOR = RENDER_ENGINE_INTERIOR
lux.RENDER_ENGINE_PRODUCT_GPU = RENDER_ENGINE_PRODUCT_GPU
lux.RENDER_ENGINE_INTERIOR_GPU = RENDER_ENGINE_INTERIOR_GPU
lux.RENDER_OUTPUT_PNG = 1
lux.RENDER_OUTPUT_JPEG = 2

from keyshot_command_handler import (  # noqa: E402
    handle_render,
    handle_stop,
    apply_render_device_override,
    parse_and_handle_command,
)


def test_apply_render_device_override_gpu_with_override():
    with (
        mock.patch.object(lux, "getRenderEngine", return_value=RENDER_ENGINE_PRODUCT),
        mock.patch.object(lux, "setRenderEngine") as set_render_engine_mock,
        mock.patch("builtins.print"),
    ):
        result = apply_render_device_override("GPU", True)

        set_render_engine_mock.assert_called_once_with(RENDER_ENGINE_PRODUCT_GPU)
        assert result == "GPU"


def test_apply_render_device_override_cpu_with_gpu_engine():
    with (
        mock.patch.object(lux, "getRenderEngine", return_value=RENDER_ENGINE_PRODUCT_GPU),
        mock.patch.object(lux, "setRenderEngine") as set_render_engine_mock,
        mock.patch("builtins.print"),
    ):
        result = apply_render_device_override("CPU", True)

        set_render_engine_mock.assert_called_once_with(RENDER_ENGINE_PRODUCT)
        assert result == "CPU"


def test_apply_render_device_override_with_override_false():
    with (
        mock.patch.object(lux, "getRenderEngine", return_value=RENDER_ENGINE_PRODUCT),
        mock.patch.object(lux, "setRenderEngine") as set_render_engine_mock,
        mock.patch("builtins.print"),
    ):
        result = apply_render_device_override("GPU", False)

        set_render_engine_mock.assert_not_called()
        assert result == "CPU"  # Should return current device


def test_apply_render_device_override_gpu_unavailable():
    with (
        mock.patch.object(lux, "getRenderEngine", return_value=RENDER_ENGINE_PRODUCT),
        mock.patch.object(lux, "setRenderEngine", side_effect=Exception("GPU not available")),
        mock.patch("builtins.print"),
    ):
        with pytest.raises(
            RuntimeError, match="GPU rendering was requested but no compatible GPU is available"
        ):
            apply_render_device_override("GPU", True)


def test_handle_render_uses_passed_render_options():
    mock_render_options_obj = mock.MagicMock()
    with (
        mock.patch.object(lux, "renderImage") as render_image_mock,
        mock.patch.object(lux, "setAnimationFrame"),
        mock.patch.object(lux, "getRenderOptions") as get_render_options_mock,
        mock.patch.object(lux, "RenderOptions", return_value=mock_render_options_obj),
        mock.patch.object(lux, "getRenderEngine", return_value=0),
        mock.patch("builtins.print"),
    ):

        params = {
            "frame": 1,
            "output_path": "test_1.png",
            "render_device": "CPU",
            "output_format": "PNG",
            "override_render_device": False,
            "render_options": {"engine_anti_aliasing": 1, "progressive_max_samples": 10},
        }

        handle_render(params)

        get_render_options_mock.assert_not_called()
        render_image_mock.assert_called_once_with(
            path="test_1.png", opts=mock_render_options_obj, format=lux.RENDER_OUTPUT_PNG
        )


def test_handle_render_output_format():
    with (
        mock.patch.object(lux, "renderImage") as render_image_mock,
        mock.patch.object(lux, "setAnimationFrame"),
        mock.patch.object(lux, "getRenderOptions", return_value=mock.MagicMock()),
        mock.patch.object(lux, "getRenderEngine", return_value=0),
        mock.patch("builtins.print"),
    ):

        params = {
            "frame": 1,
            "output_path": "test_1.jpg",
            "render_device": "CPU",
            "output_format": "JPEG",
            "override_render_device": False,
        }

        handle_render(params)

        render_image_mock.assert_called_once()
        call_args = render_image_mock.call_args
        assert call_args[1]["format"] == lux.RENDER_OUTPUT_JPEG


def test_handle_stop():
    with mock.patch("sys.exit") as exit_mock:
        handle_stop()
        exit_mock.assert_called_once_with(0)


def test_handle_render_version_mismatch_warning():
    with (
        mock.patch.object(lux, "getRenderEngine", return_value=RENDER_ENGINE_PRODUCT),
        mock.patch.object(
            lux, "renderImage", side_effect=Exception("This scene was saved using a newer version")
        ),
        mock.patch.object(lux, "setAnimationFrame"),
        mock.patch.object(lux, "getRenderOptions", return_value=mock.MagicMock()),
        mock.patch("builtins.print") as print_mock,
    ):

        params = {
            "frame": 1,
            "output_path": "test_1.png",
            "render_device": "CPU",
            "output_format": "PNG",
            "override_render_device": False,
        }

        handle_render(params)

        # Check that warning message was printed
        warning_calls = [
            call for call in print_mock.call_args_list if "WARNING:" in str(call[0][0])
        ]
        assert len(warning_calls) == 1
        assert "Version mismatch detected but continuing" in warning_calls[0][0][0]


def test_parse_and_handle_command_unknown_command():
    with (
        mock.patch("sys.stdin.readline", return_value='{"command": "invalid"}\n'),
        mock.patch("builtins.print") as print_mock,
    ):
        parse_and_handle_command()

        # Check that adaptor error message was printed
        error_calls = [
            call for call in print_mock.call_args_list if "ADAPTOR_STATUS=Error" in str(call[0][0])
        ]
        assert len(error_calls) == 1
        assert "Unknown command: invalid" in error_calls[0][0][0]


def test_parse_and_handle_command_exception_handling():
    with (
        mock.patch("sys.stdin.readline", side_effect=Exception("Test exception")),
        mock.patch("builtins.print") as print_mock,
        mock.patch("traceback.print_exc"),
    ):
        parse_and_handle_command()

        # Check that adaptor error message was printed
        error_calls = [
            call for call in print_mock.call_args_list if "ADAPTOR_STATUS=Error" in str(call[0][0])
        ]
        assert len(error_calls) == 1
        assert "Test exception" in error_calls[0][0][0]


def test_parse_and_handle_command_exception_with_quotes():
    with (
        mock.patch("sys.stdin.readline", side_effect=Exception('Error with "quotes"')),
        mock.patch("builtins.print") as print_mock,
        mock.patch("traceback.print_exc"),
    ):
        parse_and_handle_command()

        # Check that quotes are escaped in error message
        error_calls = [
            call for call in print_mock.call_args_list if "ADAPTOR_STATUS=Error" in str(call[0][0])
        ]
        assert len(error_calls) == 1
        assert 'Error with \\"quotes\\"' in error_calls[0][0][0]


def test_parse_and_handle_command_empty_line():
    with (
        mock.patch("sys.stdin.readline", return_value="\n"),
        mock.patch("builtins.print") as print_mock,
    ):
        parse_and_handle_command()

        # Should not print any error messages for empty lines
        error_calls = [
            call for call in print_mock.call_args_list if "ADAPTOR_STATUS=Error" in str(call[0][0])
        ]
        assert len(error_calls) == 0


def test_parse_and_handle_command_eof():
    with (
        mock.patch("sys.stdin.readline", return_value=""),
        mock.patch("builtins.print") as print_mock,
        mock.patch("sys.exit") as exit_mock,
    ):
        parse_and_handle_command()

        # Should print EOF message and exit
        eof_calls = [
            call for call in print_mock.call_args_list if "STDIN EOF reached" in str(call[0][0])
        ]
        assert len(eof_calls) == 1
        exit_mock.assert_called_once_with(0)


def test_parse_and_handle_command_render_success():
    render_command = '{"command": "render", "frame": 1, "output_path": "test.png", "render_device": "CPU", "output_format": "PNG"}'
    with (
        mock.patch("sys.stdin.readline", return_value=render_command + "\n"),
        mock.patch("builtins.print") as print_mock,
        mock.patch.object(lux, "setAnimationFrame"),
        mock.patch.object(lux, "getRenderOptions", return_value=mock.MagicMock()),
        mock.patch.object(lux, "renderImage"),
        mock.patch.object(lux, "getRenderEngine", return_value=0),
    ):
        parse_and_handle_command()

        # Should print success message with frame number
        success_calls = [
            call
            for call in print_mock.call_args_list
            if "ADAPTOR_STATUS=Success FRAME=1" in str(call[0][0])
        ]
        assert len(success_calls) == 1


def test_parse_and_handle_command_stop():
    with (
        mock.patch("sys.stdin.readline", return_value='{"command": "stop"}\n'),
        mock.patch("sys.exit") as exit_mock,
    ):
        parse_and_handle_command()

        exit_mock.assert_called_once_with(0)


def test_handle_render_sets_animation_frame():
    with (
        mock.patch.object(lux, "setAnimationFrame") as set_frame_mock,
        mock.patch.object(lux, "renderImage"),
        mock.patch.object(lux, "getRenderOptions", return_value=mock.MagicMock()),
        mock.patch.object(lux, "getRenderEngine", return_value=0),
        mock.patch("builtins.print"),
    ):
        params = {
            "frame": 42,
            "output_path": "test.png",
            "render_device": "CPU",
            "output_format": "PNG",
            "override_render_device": False,
        }

        handle_render(params)
        set_frame_mock.assert_called_once_with(42)


def test_handle_render_no_render_options():
    mock_default_options = mock.MagicMock()
    with (
        mock.patch.object(lux, "renderImage") as render_image_mock,
        mock.patch.object(lux, "setAnimationFrame"),
        mock.patch.object(lux, "getRenderOptions", return_value=mock_default_options),
        mock.patch.object(lux, "getRenderEngine", return_value=0),
        mock.patch("builtins.print"),
    ):
        params = {
            "frame": 1,
            "output_path": "test.png",
            "render_device": "CPU",
            "output_format": "PNG",
            "override_render_device": False,
        }

        handle_render(params)

        # Should use default render options when none provided
        render_image_mock.assert_called_once_with(
            path="test.png", opts=mock_default_options, format=lux.RENDER_OUTPUT_PNG
        )
