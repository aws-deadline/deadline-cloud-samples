"""Multi-sensor capture: Up to 6-camera RGB ring + 6 semantic segmentation + LiDAR + bounding boxes.

Runs as a background process alongside scenario_runner. All sensors capture
at ~1 FPS (configurable). Uses frame-synchronized collection: buffers
incoming images by CARLA frame ID, saves a complete set only when all RGB
cameras have reported for the same frame.

Usage (from entrypoint.sh):
    python capture_sensors.py /outputs &
    CAPTURE_PID=$!

Output structure:
    /outputs/
    ├── rgb/{front,front_left,front_right,rear,rear_left,rear_right}/frame_NNNNNN.png
    ├── rgb_mosaic/frame_NNNNNN.png  (2×3 composite)
    ├── semantic/{front,...}/frame_NNNNNN.png
    ├── semantic_mosaic/frame_NNNNNN.png  (2×3 composite)
    ├── lidar/frame_NNNNNN.ply
    ├── bbox_2d/{front,...}/frame_NNNNNN.txt   (KITTI format)
    └── bbox_3d/frame_NNNNNN.txt              (KITTI format, world coords)
"""

import os
import sys
import signal
import time
import threading
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import carla
import numpy as np

OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/outputs"
CAPTURE_FPS = float(os.environ.get("CAPTURE_FPS", "7"))
CARLA_HOST = os.environ.get("CARLA_HOST", "localhost")
CARLA_PORT = int(os.environ.get("CARLA_PORT", "2000"))
IMAGE_WIDTH = int(os.environ.get("CAPTURE_WIDTH", "1280"))
IMAGE_HEIGHT = int(os.environ.get("CAPTURE_HEIGHT", "720"))

_ALL_CAMS = ["front_left", "front", "front_right", "rear_left", "rear", "rear_right"]
_cameras_env = os.environ.get("CAMERAS", "").strip()
CAM_NAMES = [c.strip() for c in _cameras_env.split(",") if c.strip() in _ALL_CAMS] if _cameras_env else _ALL_CAMS

CAMERA_POSITIONS = {
    "front":       (carla.Location(x=2.0, z=1.5),   carla.Rotation(pitch=0, yaw=0)),
    "front_left":  (carla.Location(x=1.5, y=-0.8, z=1.5), carla.Rotation(pitch=0, yaw=-60)),
    "front_right": (carla.Location(x=1.5, y=0.8, z=1.5),  carla.Rotation(pitch=0, yaw=60)),
    "rear":        (carla.Location(x=-2.0, z=1.5),  carla.Rotation(pitch=0, yaw=180)),
    "rear_left":   (carla.Location(x=-1.5, y=-0.8, z=1.5), carla.Rotation(pitch=0, yaw=-120)),
    "rear_right":  (carla.Location(x=-1.5, y=0.8, z=1.5),  carla.Rotation(pitch=0, yaw=120)),
}

running = True
frame_counter = [0]
last_save_time = [0.0]

# Frame buffers: store latest frame per camera (overwritten each tick)
rgb_buffer = defaultdict(dict)     # {cam_name: {frame_id: numpy_array}}
sem_buffer = defaultdict(dict)     # {cam_name: {frame_id: numpy_array}}
buffer_lock = threading.Lock()


def handle_signal(signum, frame):
    global running
    running = False


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def find_ego(world, timeout=300):
    """Find the ego vehicle.

    OSC1 scenarios tag the ego with role_name="hero". OSC2 scenarios use the
    actor name from the .osc file (e.g. "ego_vehicle") and may not set
    role_name at all. We try several strategies in priority order:
      1. role_name == "hero"           (OSC1 convention)
      2. role_name == "ego_vehicle"    (OSC2 convention used by scenario_runner)
      3. role_name starts with "ego"   (defensive — other naming conventions)
      4. The Tesla Model3              (this scenario specifies Model3 as ego)
    """
    deadline = time.time() + timeout
    last_actor_count = -1
    while time.time() < deadline and running:
        actors = list(world.get_actors().filter("vehicle.*"))
        if len(actors) != last_actor_count:
            print(f"[sensors] {len(actors)} vehicle(s) in world: "
                  + ", ".join(f"{a.type_id}(role={a.attributes.get('role_name','')})" for a in actors))
            last_actor_count = len(actors)

        # Strategy 1: role_name == "hero"
        for a in actors:
            if a.attributes.get("role_name") == "hero":
                print(f"[sensors] Ego selected by role_name='hero': {a.type_id} (id={a.id})")
                return a
        # Strategy 2: role_name == "ego_vehicle" (OSC2)
        for a in actors:
            if a.attributes.get("role_name") == "ego_vehicle":
                print(f"[sensors] Ego selected by role_name='ego_vehicle': {a.type_id} (id={a.id})")
                return a
        # Strategy 3: role_name starts with "ego"
        for a in actors:
            role = a.attributes.get("role_name", "")
            if role.startswith("ego"):
                print(f"[sensors] Ego selected by role_name prefix 'ego': {a.type_id} role='{role}' (id={a.id})")
                return a
        # Strategy 4: the Tesla Model3 (scenario specifies Model3 as ego)
        for a in actors:
            if "tesla.model3" in a.type_id:
                print(f"[sensors] Ego selected by type tesla.model3: {a.type_id} (id={a.id})")
                return a

        time.sleep(1)
    print("[sensors] WARNING: no ego vehicle found by any strategy", file=sys.stderr)
    return None


def on_rgb(image, cam_name):
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))[:, :, :3][:, :, ::-1]
    with buffer_lock:
        rgb_buffer[cam_name] = {image.frame: array}


def on_semantic(image, cam_name):
    image.convert(carla.ColorConverter.CityScapesPalette)
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))[:, :, :3][:, :, ::-1]
    with buffer_lock:
        sem_buffer[cam_name] = {image.frame: array}


def save_lidar(point_cloud):
    if frame_counter[0] == 0:
        return
    out_dir = os.path.join(OUTPUT_DIR, "lidar")
    points = np.frombuffer(point_cloud.raw_data, dtype=np.float32)
    points = points.reshape((-1, 4))[:, :3]
    filename = os.path.join(out_dir, f"frame_{frame_counter[0]:06d}.ply")
    _save_ply(filename, points)


def flush_complete_frames():
    """Flush a frame set once the trigger camera has reported and enough time has elapsed."""
    now = time.time()
    if now - last_save_time[0] < (1.0 / CAPTURE_FPS):
        return

    with buffer_lock:
        trigger_cam = CAM_NAMES[0]
        if trigger_cam not in rgb_buffer or not rgb_buffer[trigger_cam]:
            return

    last_save_time[0] = now
    frame_counter[0] += 1

    # Grab the latest frame from each camera (may be different frame IDs)
    with buffer_lock:
        rgb_data = {}
        for cam_name in CAM_NAMES:
            if cam_name in rgb_buffer and rgb_buffer[cam_name]:
                latest_fid = max(rgb_buffer[cam_name].keys())
                rgb_data[cam_name] = rgb_buffer[cam_name][latest_fid]
        sem_data = {}
        for cam_name in CAM_NAMES:
            if cam_name in sem_buffer and sem_buffer[cam_name]:
                latest_fid = max(sem_buffer[cam_name].keys())
                sem_data[cam_name] = sem_buffer[cam_name][latest_fid]
        # Clear all buffers after grabbing
        rgb_buffer.clear()
        sem_buffer.clear()

    # Use front camera's frame counter for filenames
    frame_id = frame_counter[0]

    # Save individual RGB frames
    for cam_name in CAM_NAMES:
        if cam_name in rgb_data:
            out_dir = os.path.join(OUTPUT_DIR, "rgb", cam_name)
            _save_png(os.path.join(out_dir, f"frame_{frame_id:06d}.png"), rgb_data[cam_name])

    # Save RGB mosaic (2×3: top row front/front_left/front_right, bottom rear/rear_left/rear_right)
    mosaic = _make_mosaic(rgb_data)
    if mosaic is not None:
        mosaic_dir = os.path.join(OUTPUT_DIR, "rgb_mosaic")
        _save_png(os.path.join(mosaic_dir, f"frame_{frame_id:06d}.png"), mosaic)

    # Save individual semantic frames
    for cam_name in CAM_NAMES:
        if cam_name in sem_data:
            out_dir = os.path.join(OUTPUT_DIR, "semantic", cam_name)
            _save_png(os.path.join(out_dir, f"frame_{frame_id:06d}.png"), sem_data[cam_name])

    # Save semantic mosaic
    sem_mosaic = _make_mosaic(sem_data)
    if sem_mosaic is not None:
        sem_mosaic_dir = os.path.join(OUTPUT_DIR, "semantic_mosaic")
        _save_png(os.path.join(sem_mosaic_dir, f"frame_{frame_id:06d}.png"), sem_mosaic)

    if frame_counter[0] == 1:
        print(f"[sensors] First complete frame set saved (frame_id={frame_id})")


def _make_mosaic(cam_data):
    """Compose a compact mosaic from camera data in spatial order.

    Order: front_left, front, front_right, rear_left, rear, rear_right.
    Tiles into rows of 3 (or 2 if fewer than 3 cameras).
    Returns None if fewer than 2 cameras have data.
    """
    grid_order = ["front_left", "front", "front_right", "rear_left", "rear", "rear_right"]
    imgs = [cam_data[n] for n in grid_order if n in cam_data]
    if len(imgs) < 2:
        return None
    cols = 2 if len(imgs) <= 2 else 3
    # Pad with black to fill the last row if needed
    while len(imgs) % cols != 0:
        imgs.append(np.zeros_like(imgs[0]))
    rows = []
    for i in range(0, len(imgs), cols):
        rows.append(np.concatenate(imgs[i:i+cols], axis=1))
    return np.concatenate(rows, axis=0)


def _save_png(filename, rgb_array):
    try:
        from PIL import Image
        img = Image.fromarray(rgb_array)
        img.save(filename)
    except ImportError:
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
            ihdr = w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
            f.write(chunk(b"IHDR", ihdr))
            f.write(chunk(b"IDAT", compressed))
            f.write(chunk(b"IEND", b""))


def _save_ply(filename, points):
    header = (
        f"ply\nformat ascii 1.0\n"
        f"element vertex {len(points)}\n"
        f"property float x\nproperty float y\nproperty float z\n"
        f"end_header\n"
    )
    with open(filename, "w") as f:
        f.write(header)
        for p in points:
            f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")


def get_camera_intrinsic(width, height, fov):
    focal = width / (2.0 * np.tan(np.radians(fov) / 2.0))
    cx = width / 2.0
    cy = height / 2.0
    return np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1]])


def world_to_camera(point_world, camera_transform):
    cam_loc = camera_transform.location
    cam_rot = camera_transform.rotation
    point = np.array([
        point_world.x - cam_loc.x,
        point_world.y - cam_loc.y,
        point_world.z - cam_loc.z
    ])
    yaw = np.radians(-cam_rot.yaw)
    pitch = np.radians(-cam_rot.pitch)
    roll = np.radians(-cam_rot.roll)
    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll), np.sin(roll)
    R_yaw = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    R_pitch = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    R_roll = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ue4_to_cam = np.array([[0, 1, 0], [0, 0, -1], [1, 0, 0]])
    R = ue4_to_cam @ R_roll @ R_pitch @ R_yaw
    return R @ point


def compute_2d_bbox(actor, camera_sensor, K):
    bb = actor.bounding_box
    verts = bb.get_world_vertices(actor.get_transform())
    cam_transform = camera_sensor.get_transform()
    points_2d = []
    for v in verts:
        p_cam = world_to_camera(v, cam_transform)
        if p_cam[2] <= 0:
            return None
        p_2d = K @ p_cam
        p_2d = p_2d[:2] / p_2d[2]
        points_2d.append(p_2d)
    points_2d = np.array(points_2d)
    x_min = max(0, int(np.min(points_2d[:, 0])))
    y_min = max(0, int(np.min(points_2d[:, 1])))
    x_max = min(IMAGE_WIDTH, int(np.max(points_2d[:, 0])))
    y_max = min(IMAGE_HEIGHT, int(np.max(points_2d[:, 1])))
    if x_min >= x_max or y_min >= y_max:
        return None
    return (x_min, y_min, x_max, y_max)


def compute_3d_bbox_kitti(actor):
    bb = actor.bounding_box
    transform = actor.get_transform()
    extent = bb.extent
    location = transform.location
    rotation = transform.rotation
    return {
        "type": _actor_type_label(actor),
        "location": [location.x, location.y, location.z],
        "dimensions": [extent.x * 2, extent.y * 2, extent.z * 2],
        "rotation_y": np.radians(rotation.yaw),
    }


def _actor_type_label(actor):
    type_id = actor.type_id
    if "vehicle" in type_id:
        return "Car"
    elif "walker" in type_id or "pedestrian" in type_id:
        return "Pedestrian"
    return "DontCare"


def save_bbox_2d(world, cameras_dict, K, frame_id):
    actors = list(world.get_actors().filter("vehicle.*")) + \
             list(world.get_actors().filter("walker.*"))
    for cam_name, cam_sensor in cameras_dict.items():
        out_dir = os.path.join(OUTPUT_DIR, "bbox_2d", cam_name)
        filename = os.path.join(out_dir, f"frame_{frame_id:06d}.txt")
        lines = []
        for actor in actors:
            bbox = compute_2d_bbox(actor, cam_sensor, K)
            if bbox is None:
                continue
            x_min, y_min, x_max, y_max = bbox
            label = _actor_type_label(actor)
            lines.append(
                f"{label} 0.0 0 0.0 {x_min} {y_min} {x_max} {y_max} "
                f"0.0 0.0 0.0 0.0 0.0 0.0 0.0"
            )
        with open(filename, "w") as f:
            f.write("\n".join(lines))


def save_bbox_3d(world, frame_id):
    actors = list(world.get_actors().filter("vehicle.*")) + \
             list(world.get_actors().filter("walker.*"))
    out_dir = os.path.join(OUTPUT_DIR, "bbox_3d")
    filename = os.path.join(out_dir, f"frame_{frame_id:06d}.txt")
    lines = []
    for actor in actors:
        info = compute_3d_bbox_kitti(actor)
        loc = info["location"]
        dim = info["dimensions"]
        lines.append(
            f"{info['type']} {dim[2]:.2f} {dim[1]:.2f} {dim[0]:.2f} "
            f"{loc[0]:.2f} {loc[1]:.2f} {loc[2]:.2f} {info['rotation_y']:.4f}"
        )
    with open(filename, "w") as f:
        f.write("\n".join(lines))


def main():
    global running

    client = carla.Client(CARLA_HOST, CARLA_PORT)
    client.set_timeout(30.0)
    world = client.get_world()

    print("[sensors] Waiting for ego vehicle...")
    ego = find_ego(world)
    if ego is None:
        print("[sensors] No ego vehicle found, exiting")
        return
    print(f"[sensors] Found ego: {ego.type_id} (id={ego.id})")

    bp_lib = world.get_blueprint_library()
    sensors = []
    rgb_cameras = {}

    # Create output dirs
    for cam_name in CAM_NAMES:
        os.makedirs(os.path.join(OUTPUT_DIR, "rgb", cam_name), exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, "semantic", cam_name), exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, "bbox_2d", cam_name), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "lidar"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "bbox_3d"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "rgb_mosaic"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "semantic_mosaic"), exist_ok=True)

    # Spawn RGB cameras
    rgb_bp = bp_lib.find("sensor.camera.rgb")
    rgb_bp.set_attribute("image_size_x", str(IMAGE_WIDTH))
    rgb_bp.set_attribute("image_size_y", str(IMAGE_HEIGHT))
    rgb_bp.set_attribute("fov", "90")

    for cam_name in CAM_NAMES:
        loc, rot = CAMERA_POSITIONS[cam_name]
        transform = carla.Transform(loc, rot)
        cam = world.spawn_actor(rgb_bp, transform, attach_to=ego)
        cam.listen(lambda img, cn=cam_name: on_rgb(img, cn))
        sensors.append(cam)
        rgb_cameras[cam_name] = cam

    # Spawn semantic segmentation cameras
    sem_bp = bp_lib.find("sensor.camera.semantic_segmentation")
    sem_bp.set_attribute("image_size_x", str(IMAGE_WIDTH))
    sem_bp.set_attribute("image_size_y", str(IMAGE_HEIGHT))
    sem_bp.set_attribute("fov", "90")

    for cam_name in CAM_NAMES:
        loc, rot = CAMERA_POSITIONS[cam_name]
        transform = carla.Transform(loc, rot)
        cam = world.spawn_actor(sem_bp, transform, attach_to=ego)
        cam.listen(lambda img, cn=cam_name: on_semantic(img, cn))
        sensors.append(cam)

    # Spawn LiDAR
    lidar_bp = bp_lib.find("sensor.lidar.ray_cast")
    lidar_transform = carla.Transform(carla.Location(x=0, z=2.5))
    lidar = world.spawn_actor(lidar_bp, lidar_transform, attach_to=ego)
    lidar.listen(save_lidar)
    sensors.append(lidar)

    K = get_camera_intrinsic(IMAGE_WIDTH, IMAGE_HEIGHT, 90)

    n_rgb = len(CAM_NAMES)
    print(f"[sensors] Spawned {len(sensors)} sensors "
          f"({n_rgb} RGB + {n_rgb} semantic + 1 LiDAR). "
          f"Cameras: {CAM_NAMES}. Capturing at {CAPTURE_FPS} FPS.")

    last_bbox_time = 0.0
    try:
        while running:
            flush_complete_frames()
            now = time.time()
            if now - last_bbox_time >= (1.0 / CAPTURE_FPS) and frame_counter[0] > 0:
                last_bbox_time = now
                try:
                    save_bbox_2d(world, rgb_cameras, K, frame_counter[0])
                    save_bbox_3d(world, frame_counter[0])
                except RuntimeError:
                    break
            time.sleep(0.05)
    finally:
        for s in sensors:
            try:
                s.stop()
                s.destroy()
            except RuntimeError:
                pass
        print(f"[sensors] Done. Captured {frame_counter[0]} frame sets.")


if __name__ == "__main__":
    main()
    