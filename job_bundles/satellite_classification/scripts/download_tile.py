"""
Download a single sample tile from the Deadline Cloud samples CDN.

Usage: python download_tile.py <tile_name> <base_url> <output_dir>
"""

import os
import sys
import urllib.request


def main():
    if len(sys.argv) < 4:
        print("Usage: python download_tile.py <tile_name> <base_url> <output_dir>")
        sys.exit(1)

    tile_name = sys.argv[1]
    base_url = sys.argv[2].rstrip("/")
    output_dir = sys.argv[3]

    os.makedirs(output_dir, exist_ok=True)

    filename = f"{tile_name}.tif"
    url = f"{base_url}/{filename}"
    dest = os.path.join(output_dir, filename)

    if os.path.exists(dest):
        print(f"  Tile already exists: {dest}")
        return

    print(f"  Downloading {url}")
    urllib.request.urlretrieve(url, dest)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"  -> {dest} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
