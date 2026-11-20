"""Turn SimFoundry's stage 2 depth output into files you can look at.

Reads the Depth Anything 3 results (s2_da/da/exports/npz/results.npz) and writes, next to it:
  depth_preview.png  each sampled frame above its depth map
  point_cloud.ply    every frame back-projected into one coloured point cloud
  depth_summary.json frame count, resolution and depth range
"""

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image

MAX_PREVIEW_FRAMES = 8
MAX_POINTS = 2_000_000


def depth_to_rgb(depth, lo, hi):
    scaled = np.clip((depth - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return (matplotlib.colormaps["turbo"](1.0 - scaled)[..., :3] * 255).astype(np.uint8)


def write_preview(images, depths, path):
    n = len(images)
    picks = np.linspace(0, n - 1, min(n, MAX_PREVIEW_FRAMES)).round().astype(int)
    lo, hi = np.percentile(depths[picks], [2, 98])
    columns = [np.concatenate([images[i], depth_to_rgb(depths[i], lo, hi)], axis=0) for i in picks]
    Image.fromarray(np.concatenate(columns, axis=1)).save(path)


def write_point_cloud(data, path):
    images, depths = data["image"], data["depth"]
    intrinsics, extrinsics = data["intrinsics"], data["extrinsics"]
    conf = data["conf"] if "conf" in data else np.ones_like(depths)
    keep_conf = np.percentile(conf, 30)
    n, h, w = depths.shape
    v, u = np.mgrid[0:h, 0:w]
    pixels = np.stack([u, v, np.ones_like(u)], axis=-1).reshape(-1, 3).astype(np.float64)
    points, colours = [], []
    for i in range(n):
        mask = (conf[i].reshape(-1) >= keep_conf) & (depths[i].reshape(-1) > 0)
        rays = pixels[mask] @ np.linalg.inv(intrinsics[i]).T
        camera = rays * depths[i].reshape(-1)[mask, None]
        # DA3 extrinsics are world-to-camera [R|t].
        rotation, translation = extrinsics[i][:3, :3], extrinsics[i][:3, 3]
        points.append((camera - translation) @ rotation)
        colours.append(images[i].reshape(-1, 3)[mask])
    points, colours = np.concatenate(points), np.concatenate(colours)
    if len(points) > MAX_POINTS:
        keep = np.random.default_rng(0).choice(len(points), MAX_POINTS, replace=False)
        points, colours = points[keep], colours[keep]
    vertex = np.empty(len(points), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                                          ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    vertex["x"], vertex["y"], vertex["z"] = points.T
    vertex["red"], vertex["green"], vertex["blue"] = colours.T
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {len(vertex)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    )
    with open(path, "wb") as f:
        f.write(header.encode())
        f.write(vertex.tobytes())
    return len(vertex)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene_dir", type=Path, help="Data/<scene> directory written by pipeline A")
    args = parser.parse_args()

    npz = args.scene_dir / "s2_da" / "da" / "exports" / "npz" / "results.npz"
    data = dict(np.load(npz))
    out_dir = npz.parents[3]
    write_preview(data["image"], data["depth"], out_dir / "depth_preview.png")
    n_points = write_point_cloud(data, out_dir / "point_cloud.ply")

    depth = data["depth"]
    summary = {
        "frames": int(depth.shape[0]),
        "resolution": [int(depth.shape[2]), int(depth.shape[1])],
        "depth_min": float(depth.min()),
        "depth_median": float(np.median(depth)),
        "depth_max": float(depth.max()),
        "point_cloud_points": n_points,
    }
    (out_dir / "depth_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
