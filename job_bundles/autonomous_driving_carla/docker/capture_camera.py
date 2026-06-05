"""Attach an RGB camera to the ego vehicle and save frames to disk.

Runs as a background process alongside scenario_runner. Captures at ~24 FPS
(configurable via CAPTURE_FPS env var). Stops when the ego vehicle is
destroyed or when the process receives SIGTERM.

Usage (from entrypoint.sh):
    python capture_camera.py /outputs/frames &
    CAPTURE_PID=$!
"""

import os
import sys
import signal
import time

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import carla
import numpy as np

OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/outputs/frames"
CAPTURE_FPS = float(os.environ.get("CAPTURE_FPS", "24"))
CARLA_HOST = os.environ.get("CARLA_HOST", "localhost")
CARLA_PORT = int(os.environ.get("CARLA_PORT", "2000"))
IMAGE_WIDTH = int(os.environ.get("CAPTURE_WIDTH", "1920"))
IMAGE_HEIGHT = int(os.environ.get("CAPTURE_HEIGHT", "1080"))

os.makedirs(OUTPUT_DIR, exist_ok=True)

running = True


def handle_signal(signum, frame):
    global running
    running = False


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def find_ego(world, timeout=300):
    """Wait for an ego vehicle to appear. Prefer role_name='hero', fall back to first vehicle."""
    deadline = time.time() + timeout
    while time.time() < deadline and running:
        actors = world.get_actors().filter("vehicle.*")
        for a in actors:
            if a.attributes.get("role_name") == "hero":
                print(f"[capture_camera] Found hero vehicle: {a.type_id} (id={a.id})")
                return a
        if len(actors) > 0:
            a = actors[0]
            print(f"[capture_camera] No 'hero' found, using first vehicle: {a.type_id} (id={a.id})")
            return a
        time.sleep(1)
    return None


def save_image(image, output_dir):
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))[:, :, :3]
    filename = os.path.join(output_dir, f"frame_{image.frame:06d}.png")
    try:
        from PIL import Image
        img = Image.fromarray(array[:, :, ::-1])
        img.save(filename)
    except ImportError:
        _write_png(filename, array[:, :, ::-1])


def _write_png(filename, rgb_array):
    """Minimal PNG writer when PIL is unavailable."""
    import zlib

    h, w, _ = rgb_array.shape
    raw = b""
    for row in rgb_array:
        raw += b"\x00" + row.tobytes()
    compressed = zlib.compress(raw)

    def chunk(tag, data):
        c = tag + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return len(data).to_bytes(4, "big") + c + crc.to_bytes(4, "big")

    with open(filename, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        ihdr = (
            w.to_bytes(4, "big")
            + h.to_bytes(4, "big")
            + b"\x08\x02\x00\x00\x00"
        )
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", compressed))
        f.write(chunk(b"IEND", b""))


def main():
    global running

    client = carla.Client(CARLA_HOST, CARLA_PORT)
    client.set_timeout(30.0)
    world = client.get_world()

    print(f"[capture_camera] Waiting for ego vehicle (role_name='hero')...")
    ego = find_ego(world)
    if ego is None:
        print("[capture_camera] No ego vehicle found, exiting")
        return

    print(f"[capture_camera] Found ego: {ego.type_id} (id={ego.id})")

    bp_lib = world.get_blueprint_library()
    camera_bp = bp_lib.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(IMAGE_WIDTH))
    camera_bp.set_attribute("image_size_y", str(IMAGE_HEIGHT))
    camera_bp.set_attribute("fov", "90")

    transform = carla.Transform(
        carla.Location(x=-5.5, z=2.5),
        carla.Rotation(pitch=-15)
    )
    camera = world.spawn_actor(camera_bp, transform, attach_to=ego)
    print(f"[capture_camera] Camera attached to ego, "
          f"saving {CAPTURE_FPS} fps ({IMAGE_WIDTH}x{IMAGE_HEIGHT}) to {OUTPUT_DIR}")

    frame_count = [0]
    last_save_time = [0.0]

    def on_image(image):
        now = time.time()
        if now - last_save_time[0] < (1.0 / CAPTURE_FPS):
            return
        last_save_time[0] = now
        save_image(image, OUTPUT_DIR)
        frame_count[0] += 1
        if frame_count[0] == 1:
            print(f"[capture_camera] First frame saved (frame_id={image.frame})")

    camera.listen(on_image)

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            camera.stop()
            camera.destroy()
        except RuntimeError:
            # Camera may already be destroyed if the ego vehicle was removed
            pass
        print(f"[capture_camera] Done. Captured {frame_count[0]} frames.")


if __name__ == "__main__":
    main()
