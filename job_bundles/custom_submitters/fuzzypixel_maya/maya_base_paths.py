import os
import sys
from pathlib import Path


class pathUtils:
    """
    Establish some common paths and variables we'll use. Windows only.
    """

    def __init__(self):
        """
        These attributes should reflect your system setup
        """
        # We forward slash this path since it will be used in Maya
        self.maya_tools_path = Path(os.path.dirname(__file__))
        # We are using Python-3.10.8 to match Maya 2024's version of python
        self.python_packages = "C:\\Program Files\\Python-3.10.8\\Lib\site-packages"
        self.maya_installation = "C:\\Program Files\\Autodesk\\Maya2024"

    def set_farm_vars(self):
        """
        These attributes should reflect your farm setup
        """
        self.default_farm_display_name = "YourDefaultFarmNameTheNameNotTheID"
        self.default_farm_id = "YourDefaultFarmID"
        self.default_queue = "YourDefaultQueueNameTheNameNotTheID"
        self.default_fleet_attr = "YourDefaultFleetAttrNoneIfNoFleetAttrs"

    def set_appends(self):
        """
        Perform path appends so Maya can get these tools and your installed python packages.
        """
        sys.path.append(self.maya_tools_path.as_posix())
        sys.path.append(self.python_packages)
