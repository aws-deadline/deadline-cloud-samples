"""
Generate synthetic Sentinel-2 L2A tiles simulating Grand Canyon area.

Creates 5 GeoTIFF files with 4 bands (Red, Green, Blue, NIR) that mimic
real spectral signatures for: canyon rock, Colorado River, rim vegetation,
desert floor, and mixed terrain.

Prerequisites: pip install numpy rasterio
"""

import numpy as np
import os
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS


TILE_SIZE = 512
TILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_tiles")

TILE_CONFIGS = [
    {
        "name": "T12S_GC_North_Rim",
        "bounds": (-112.2, 36.2, -112.0, 36.3),
        "description": "North Rim - dense vegetation + exposed rock",
        "mix": {"vegetation": 0.45, "rock": 0.40, "soil": 0.10, "water": 0.0, "cloud": 0.05},
    },
    {
        "name": "T12S_GC_South_Rim",
        "bounds": (-112.2, 36.0, -112.0, 36.1),
        "description": "South Rim - sparse vegetation + desert + rock",
        "mix": {"vegetation": 0.20, "rock": 0.35, "soil": 0.35, "water": 0.0, "cloud": 0.10},
    },
    {
        "name": "T12S_GC_Inner_Canyon",
        "bounds": (-112.2, 36.1, -112.0, 36.2),
        "description": "Inner Canyon - river corridor + steep rock walls",
        "mix": {"vegetation": 0.05, "rock": 0.65, "soil": 0.10, "water": 0.15, "cloud": 0.05},
    },
    {
        "name": "T12S_GC_Desert_East",
        "bounds": (-112.0, 36.0, -111.8, 36.1),
        "description": "Eastern desert - painted desert, minimal vegetation",
        "mix": {"vegetation": 0.05, "rock": 0.20, "soil": 0.65, "water": 0.0, "cloud": 0.10},
    },
    {
        "name": "T12S_GC_River_West",
        "bounds": (-112.4, 36.1, -112.2, 36.2),
        "description": "Western river section - wider river + riparian vegetation",
        "mix": {"vegetation": 0.15, "rock": 0.40, "soil": 0.15, "water": 0.25, "cloud": 0.05},
    },
]

# Typical Sentinel-2 surface reflectance values (scaled 0-10000)
# Format: [Red (B04), Green (B03), Blue (B02), NIR (B08)]
SPECTRAL_SIGNATURES = {
    "vegetation": {"mean": [600, 900, 500, 4500], "std": [150, 200, 100, 800]},
    "water":      {"mean": [400, 500, 600, 200], "std": [80, 100, 120, 50]},
    "rock":       {"mean": [2200, 1800, 1500, 2500], "std": [400, 350, 300, 500]},
    "soil":       {"mean": [2800, 2200, 1800, 3000], "std": [500, 400, 350, 600]},
    "cloud":      {"mean": [8000, 8500, 9000, 7500], "std": [500, 500, 500, 600]},
}


def generate_class_mask(size, mix, seed=42):
    """Generate a spatially coherent land-cover mask using Voronoi-like regions."""
    rng = np.random.default_rng(seed)
    classes = list(mix.keys())
    fractions = np.array([mix[c] for c in classes])

    n_seeds = 30
    seed_y = rng.integers(0, size, n_seeds)
    seed_x = rng.integers(0, size, n_seeds)

    counts_target = (fractions * n_seeds).astype(int)
    for i, f in enumerate(fractions):
        if f > 0 and counts_target[i] == 0:
            counts_target[i] = 1
    remainder = n_seeds - counts_target.sum()
    if remainder > 0:
        top_idx = np.argsort(-fractions)
        for j in range(remainder):
            counts_target[top_idx[j % len(top_idx)]] += 1
    elif remainder < 0:
        top_idx = np.argsort(-counts_target)
        for j in range(-remainder):
            counts_target[top_idx[j % len(top_idx)]] -= 1

    seed_classes = []
    for i, count in enumerate(counts_target):
        seed_classes.extend([i] * count)
    rng.shuffle(seed_classes)
    seed_classes = np.array(seed_classes[:n_seeds])

    yy, xx = np.mgrid[0:size, 0:size]
    mask = np.zeros((size, size), dtype=np.uint8)
    min_dist = np.full((size, size), np.inf)

    for idx in range(n_seeds):
        dist = (yy - seed_y[idx])**2 + (xx - seed_x[idx])**2
        jitter = rng.normal(0, size * 5, (size, size))
        dist = dist.astype(np.float64) + jitter
        closer = dist < min_dist
        min_dist[closer] = dist[closer]
        mask[closer] = seed_classes[idx]

    return mask, classes


def generate_tile_data(mask, classes):
    """Generate 4-band reflectance data from a class mask."""
    rng = np.random.default_rng(123)
    h, w = mask.shape
    bands = np.zeros((4, h, w), dtype=np.float32)

    for class_idx, class_name in enumerate(classes):
        pixels = mask == class_idx
        n_pixels = pixels.sum()
        if n_pixels == 0:
            continue
        sig = SPECTRAL_SIGNATURES[class_name]
        for band_idx in range(4):
            values = rng.normal(sig["mean"][band_idx], sig["std"][band_idx] * 0.3, n_pixels)
            bands[band_idx][pixels] = values

    bands = np.clip(bands, 0, 10000).astype(np.uint16)
    return bands


def write_geotiff(filepath, bands, bounds):
    """Write a 4-band GeoTIFF with geographic metadata."""
    h, w = bands.shape[1], bands.shape[2]
    transform = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], w, h)

    with rasterio.open(
        filepath,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=4,
        dtype="uint16",
        crs=CRS.from_epsg(4326),
        transform=transform,
        compress="deflate",
    ) as dst:
        dst.write(bands)
        dst.set_band_description(1, "Red (B04)")
        dst.set_band_description(2, "Green (B03)")
        dst.set_band_description(3, "Blue (B02)")
        dst.set_band_description(4, "NIR (B08)")


def main():
    os.makedirs(TILES_DIR, exist_ok=True)

    print(f"Generating {len(TILE_CONFIGS)} synthetic Sentinel-2 tiles...")
    print(f"Output directory: {TILES_DIR}\n")

    for tile_idx, config in enumerate(TILE_CONFIGS):
        print(f"  Generating: {config['name']}")
        print(f"    {config['description']}")

        mask, classes = generate_class_mask(TILE_SIZE, config["mix"], seed=42 + tile_idx)
        bands = generate_tile_data(mask, classes)

        filepath = os.path.join(TILES_DIR, f"{config['name']}.tif")
        write_geotiff(filepath, bands, config["bounds"])
        print(f"    -> {filepath} ({bands.nbytes / 1024:.0f} KB)\n")

    print("Done! Tiles ready for classification.")


if __name__ == "__main__":
    main()
