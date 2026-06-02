"""
Classify a single Sentinel-2 tile into land-cover classes using spectral indices.

Input:  4-band GeoTIFF (Red, Green, Blue, NIR)
Output: Classified GeoTIFF (single-band, class values 1-5) + PNG visualization

Classes:
  1 = Water (blue)
  2 = Vegetation (green)
  3 = Bare Soil (tan)
  4 = Rock (brown)
  5 = Cloud/Snow (white)

Method: Threshold-based decision tree on NDVI, NDWI, and BSI indices.
"""

import sys
import os
import numpy as np
import rasterio

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


def compute_indices(red, green, blue, nir):
    """Compute spectral indices from surface reflectance bands."""
    eps = 1e-10
    ndvi = (nir - red) / (nir + red + eps)
    ndwi = (green - nir) / (green + nir + eps)
    bsi = ((red + blue) - (nir + green)) / ((red + blue) + (nir + green) + eps)
    brightness = (red + green + blue + nir) / 4.0
    return ndvi, ndwi, bsi, brightness


def classify(ndvi, ndwi, bsi, brightness):
    """Apply threshold-based decision tree for classification.

    Thresholds calibrated to Sentinel-2 L2A surface reflectance (0-10000 scale):
      cloud:      brightness > 6000 (all bands saturated)
      water:      NDVI < -0.1 and NDWI > 0.2 (high green, very low NIR)
      vegetation: NDVI > 0.4 (high NIR relative to Red)
      soil:       brightness > 2200 and NDVI < 0.4 (bright, non-vegetated)
      rock:       everything else (moderate brightness, low NDVI)
    """
    result = np.full(ndvi.shape, 4, dtype=np.uint8)

    cloud_mask = brightness > 6000
    result[cloud_mask] = 5

    water_mask = (ndvi < -0.1) & (ndwi > 0.2) & ~cloud_mask
    result[water_mask] = 1

    veg_mask = (ndvi > 0.4) & ~cloud_mask & ~water_mask
    result[veg_mask] = 2

    soil_mask = (brightness > 2200) & (ndvi < 0.4) & ~cloud_mask & ~water_mask
    result[soil_mask] = 3

    return result


def render_png(classified, output_path, tile_name):
    """Render classified map as a color PNG with legend."""
    cmap_colors = [CLASS_COLORS[i] for i in range(1, 6)]
    cmap = ListedColormap(cmap_colors)

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(classified, cmap=cmap, vmin=1, vmax=5, interpolation="nearest")
    ax.set_title(f"Land Cover Classification\n{tile_name}", fontsize=14)
    ax.axis("off")

    legend_patches = [
        Patch(facecolor=CLASS_COLORS[i], edgecolor="black", label=CLASS_NAMES[i])
        for i in range(1, 6)
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=11, framealpha=0.9)

    total = classified.size
    stats = []
    for cls_id, cls_name in CLASS_NAMES.items():
        pct = (classified == cls_id).sum() / total * 100
        if pct > 0.1:
            stats.append(f"{cls_name}: {pct:.1f}%")
    ax.text(0.5, -0.02, " | ".join(stats), transform=ax.transAxes,
            ha="center", fontsize=9, color="gray")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: python classify_tile.py <input_tile.tif> <output_dir>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    tile_name = os.path.splitext(os.path.basename(input_path))[0]
    print(f"Classifying: {tile_name}")

    with rasterio.open(input_path) as src:
        red = src.read(1).astype(np.float32)
        green = src.read(2).astype(np.float32)
        blue = src.read(3).astype(np.float32)
        nir = src.read(4).astype(np.float32)
        profile = src.profile.copy()

    print("  Computing spectral indices (NDVI, NDWI, BSI)...")
    ndvi, ndwi, bsi, brightness = compute_indices(red, green, blue, nir)

    print("  Applying classification decision tree...")
    classified = classify(ndvi, ndwi, bsi, brightness)

    classified_path = os.path.join(output_dir, f"{tile_name}_classified.tif")
    out_profile = profile.copy()
    out_profile.update(count=1, dtype="uint8", compress="deflate")
    with rasterio.open(classified_path, "w", **out_profile) as dst:
        dst.write(classified, 1)
        dst.set_band_description(1, "Land Cover Class")
    print(f"  -> {classified_path}")

    png_path = os.path.join(output_dir, f"{tile_name}_classified.png")
    print("  Rendering visualization...")
    render_png(classified, png_path, tile_name)
    print(f"  -> {png_path}")

    total = classified.size
    print(f"\n  Classification results for {tile_name}:")
    for cls_id, cls_name in CLASS_NAMES.items():
        count = (classified == cls_id).sum()
        pct = count / total * 100
        print(f"    {cls_name:12s}: {pct:5.1f}% ({count:,} pixels)")
    print("\n  Done.")


if __name__ == "__main__":
    main()
