#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
This script runs inside KeyShot. It accepts JSON commands from STDIN and executes them.
"""

import json
import sys
import traceback
import lux  # noqa: F401

ENGINE_NAMES = {
    0: "RENDER_ENGINE_PRODUCT",
    1: "RENDER_ENGINE_INTERIOR",
    3: "RENDER_ENGINE_PRODUCT_GPU",
    4: "RENDER_ENGINE_INTERIOR_GPU",
}

# Map between equivalent CPU and GPU engines
ENGINE_MAP = {
    lux.RENDER_ENGINE_PRODUCT: lux.RENDER_ENGINE_PRODUCT_GPU,
    lux.RENDER_ENGINE_INTERIOR: lux.RENDER_ENGINE_INTERIOR_GPU,
    lux.RENDER_ENGINE_PRODUCT_GPU: lux.RENDER_ENGINE_PRODUCT,
    lux.RENDER_ENGINE_INTERIOR_GPU: lux.RENDER_ENGINE_INTERIOR,
}


def apply_render_device_override(render_device: str, override_render_device: bool) -> str:
    current_engine = lux.getRenderEngine()
    is_gpu = current_engine in [lux.RENDER_ENGINE_PRODUCT_GPU, lux.RENDER_ENGINE_INTERIOR_GPU]
    current_device = "GPU" if is_gpu else "CPU"
    original_render_device_param = render_device

    # Apply render device override logic
    if override_render_device:
        print("Option to override the Keyshot render device was selected.")
        if current_device == render_device:
            print(
                f"KeyShot render device {render_device} is already selected. Chosen override option matches Keyshot setting."
            )
        else:
            print(f"Overriding {current_device} with {render_device}...")
            if current_engine in ENGINE_MAP:
                try:
                    lux.setRenderEngine(ENGINE_MAP[current_engine])
                except Exception:
                    raise RuntimeError(
                        "GPU rendering was requested but no compatible GPU is available on this worker. Please manually set min GPUs to 1 under 'Host requirements' in the KeyShot integrated submitter."
                    )

        final_render_device = render_device
    else:
        print("Option to override the Keyshot render device was NOT selected.")
        if (
            current_device != original_render_device_param
            and original_render_device_param is not None
        ):
            print(
                f"WARNING: RenderDevice value from the submitter ({original_render_device_param}) will be ignored since override is not selected."
            )
        final_render_device = current_device

    # Print final engine and device info
    final_engine = lux.getRenderEngine()
    engine_name = ENGINE_NAMES[final_engine]
    print(f"Selected render engine: {engine_name}")
    print(f"Selected render device: {final_render_device}")

    return final_render_device


def handle_render(params: dict) -> None:
    """Handle render command with all parameters"""
    frame = params["frame"]
    output_path = params["output_path"]
    render_device = params["render_device"]
    output_format = params["output_format"]
    override_render_device = params.get("override_render_device", False)
    render_options = params.get("render_options", {})

    print(f"Rendering frame {frame} to {output_path}")

    lux.setAnimationFrame(frame)
    apply_render_device_override(render_device, override_render_device)

    print("Starting Render...")

    # Set up render options
    if render_options:
        opts = lux.RenderOptions(dict=render_options)
    else:
        opts = lux.getRenderOptions()

    opts.setAddToQueue(False)

    try:
        lux.renderImage(
            path=output_path, opts=opts, format=getattr(lux, f"RENDER_OUTPUT_{output_format}")
        )
    except Exception as e:
        error_message = str(e)
        if "This scene was saved using a newer version" in error_message:
            updated_error_message = "This scene was saved using a newer version. Opening it in an older version may cause some information to be lost."
            print(
                f"WARNING: Version mismatch detected but continuing: {updated_error_message}",
                flush=True,
            )
            # Assume render succeeded despite the warning
        else:
            raise

    print(f"Finished Rendering {output_path}", flush=True)


def handle_stop() -> None:
    print("Stopping KeyShot server")
    sys.exit(0)


def parse_and_handle_command() -> None:
    try:
        line = sys.stdin.readline()

        if not line:
            print("STDIN EOF reached, shutting down server", flush=True)
            sys.exit(0)

        command_json = line.strip()
        if not command_json:
            return

        command_data = json.loads(command_json)
        command = command_data.get("command")

        if command == "render":
            handle_render(command_data)
            print(f"ADAPTOR_STATUS=Success FRAME={str(command_data.get('frame'))}", flush=True)
        elif command == "stop":
            handle_stop()
        else:
            print(f"ADAPTOR_STATUS=Error Error=Unknown command: {command}", flush=True)

    except Exception as e:
        traceback.print_exc()
        message = str(e).replace('"', '\\"')
        print(f"ADAPTOR_STATUS=Error Error={message}", flush=True)


def main() -> None:
    print("KeyShot server is ready", flush=True)

    while True:
        parse_and_handle_command()


if __name__ == "__main__":
    main()
