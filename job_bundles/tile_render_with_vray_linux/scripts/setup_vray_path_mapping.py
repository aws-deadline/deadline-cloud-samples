#!/usr/bin/env python3
"""Set up V-Ray path mapping from Deadline Cloud session path mapping rules."""
import json
import os
import sys

OUTPUT_FILE = "/tmp/vray_remap_paths.txt"

def main():
    os.environ["VRAY_PATH_REMAPPING_CASE_SENSITIVE"] = "1"
    
    path_mapping_file = sys.argv[1] if len(sys.argv) > 1 else ""
    
    if not path_mapping_file or not os.path.isfile(path_mapping_file):
        print(f"No path mapping rules file found: {path_mapping_file}")
        open(OUTPUT_FILE, "w").close()
        return
    
    with open(path_mapping_file) as f:
        data = json.load(f)
    
    rules = data.get("path_mapping_rules", [])
    remap_args = []
    
    for r in rules:
        src, dst = r.get("source_path"), r.get("destination_path")
        if src and dst:
            remap_args.append(f"-remapPath='{src}={dst}'")
            print(f"Path mapping: {src} -> {dst}")
    
    with open(OUTPUT_FILE, "w") as f:
        f.write(" ".join(remap_args))

if __name__ == "__main__":
    main()
