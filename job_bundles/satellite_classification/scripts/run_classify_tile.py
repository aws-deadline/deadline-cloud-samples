"""
Wrapper that downloads a sample tile (if needed) then classifies it.

Usage: python run_classify_tile.py <tile_name> <sample_tiles_url> <tiles_dir> <output_dir>
"""

import subprocess
import sys

tile_name = sys.argv[1]
sample_tiles_url = sys.argv[2]
tiles_dir = sys.argv[3]
output_dir = sys.argv[4]
scripts_dir = sys.argv[5]

subprocess.check_call([
    sys.executable,
    f"{scripts_dir}/download_tile.py",
    tile_name,
    sample_tiles_url,
    tiles_dir,
])

subprocess.check_call([
    sys.executable,
    f"{scripts_dir}/classify_tile.py",
    f"{tiles_dir}/{tile_name}.tif",
    output_dir,
])
