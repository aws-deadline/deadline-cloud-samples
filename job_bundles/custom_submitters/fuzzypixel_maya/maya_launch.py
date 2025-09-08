from pathlib import Path
from maya_base_paths import pathUtils
import subprocess

pu = pathUtils()
maya_folder = Path(pu.maya_installation) / "bin" / "maya.exe"
launcher_path = (pu.maya_tools_path / "maya_launcher.py").as_posix()
maya_launch_cmd = f'"{maya_folder}" -command "python(\\"exec(open(\\\'{launcher_path}\\\').read())\\")"'
result = subprocess.run(
    maya_launch_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
)
if result.stderr:
    print(maya_launch_cmd)
    print(result.stderr)
else:
    result = result.stdout.strip()