import zipfile, os, sys

addons_dir = "/opt/blender-plugins/addons"
plugins_dir = "/tmp/plugins"

for fname in sorted(os.listdir(plugins_dir)):
    if not fname.endswith(".zip"):
        continue
    zip_path = os.path.join(plugins_dir, fname)
    z = zipfile.ZipFile(zip_path)
    names = z.namelist()
    top_dirs = set(n.split("/")[0] for n in names if "/" in n)
    has_top_dir = len(top_dirs) == 1 and all(
        n.startswith(list(top_dirs)[0] + "/") or n == list(top_dirs)[0] for n in names
    )
    if has_top_dir:
        dest = addons_dir
    else:
        addon_name = os.path.splitext(fname)[0].replace("-", "_").replace(" ", "_").replace(".", "_")
        dest = os.path.join(addons_dir, addon_name)
        os.makedirs(dest, exist_ok=True)
        print(f"  Flat zip detected, extracting to: {dest}")
    z.extractall(dest)
    print(f"  Extracted: {fname}")
