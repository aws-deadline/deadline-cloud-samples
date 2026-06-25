"""
Mosaic all classified tiles into a single combined map.

Reads all *_classified.tif files from the output directory,
merges them into one image, and produces a final overview PNG.
"""

import sys
import os
import glob
import numpy as np
import rasterio
from rasterio.merge import merge

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


CLASS_NAMES = {1: "Water", 2: "Vegetation", 3: "Bare Soil", 4: "Rock", 5: "Cloud/Snow"}
CLASS_COLORS = {
    1: [0.18, 0.55, 0.78],
    2: [0.30, 0.69, 0.29],
    3: [0.85, 0.75, 0.55],
    4: [0.55, 0.35, 0.20],
    5: [0.95, 0.95, 0.95],
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python mosaic.py <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    classified_files = sorted(glob.glob(os.path.join(output_dir, "*_classified.tif")))

    if not classified_files:
        print("No classified tiles found. Run classify_tile.py first.")
        sys.exit(1)

    print(f"Merging {len(classified_files)} classified tiles...")
    datasets = [rasterio.open(f) for f in classified_files]
    mosaic_data, mosaic_transform = merge(datasets, method="first")
    mosaic_data = mosaic_data[0]

    merged_path = os.path.join(output_dir, "grand_canyon_mosaic.tif")
    out_profile = datasets[0].profile.copy()
    out_profile.update(
        height=mosaic_data.shape[0],
        width=mosaic_data.shape[1],
        transform=mosaic_transform,
        count=1,
        dtype="uint8",
        compress="deflate",
    )
    with rasterio.open(merged_path, "w", **out_profile) as dst:
        dst.write(mosaic_data, 1)
    print(f"  -> {merged_path}")

    for ds in datasets:
        ds.close()

    cmap_colors = [CLASS_COLORS[i] for i in range(1, 6)]
    cmap = ListedColormap(cmap_colors)
    cmap.set_under(color="lightgray")
    masked_data = np.ma.masked_where(mosaic_data == 0, mosaic_data)

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_facecolor("lightgray")
    ax.imshow(masked_data, cmap=cmap, vmin=1, vmax=5, interpolation="nearest")
    ax.set_title("Grand Canyon Land Cover Classification\n"
                 "Sentinel-2 Spectral Index Analysis", fontsize=16)
    ax.axis("off")

    legend_patches = [
        Patch(facecolor=CLASS_COLORS[i], edgecolor="black", label=CLASS_NAMES[i])
        for i in range(1, 6)
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=12, framealpha=0.9)

    valid_mask = mosaic_data > 0
    total = valid_mask.sum() if valid_mask.any() else mosaic_data.size
    stats = []
    for cls_id, cls_name in CLASS_NAMES.items():
        pct = (mosaic_data == cls_id).sum() / total * 100
        if pct > 0.1:
            stats.append(f"{cls_name}: {pct:.1f}%")
    ax.text(0.5, -0.02, " | ".join(stats), transform=ax.transAxes,
            ha="center", fontsize=10, color="gray")

    mosaic_png = os.path.join(output_dir, "grand_canyon_mosaic.png")
    plt.tight_layout()
    plt.savefig(mosaic_png, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> {mosaic_png}")

    print("\nFinal mosaic statistics:")
    for cls_id, cls_name in CLASS_NAMES.items():
        count = (mosaic_data == cls_id).sum()
        pct = count / total * 100
        print(f"  {cls_name:12s}: {pct:5.1f}% ({count:,} pixels)")
    print("\nMosaic complete!")


if __name__ == "__main__":
    main()
