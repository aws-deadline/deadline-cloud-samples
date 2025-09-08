# Note that maya_launcher is invoked via the maya-2024 rez package
# Launch functionality has been organized via classes.
import maya.OpenMaya as api
import maya.cmds as cmds
import maya.mel as mel
import os
import sys
import re
from pathlib import Path
import platform
from maya_base_paths import pathUtils


class projResolution:
    def __init__(self):
        self.add_proj_callbacks()
        self.bp = pathUtils()

    def set_proj_env_variable(self, *args):
        # set the PROJ environment variable based on current fileName
        file_name = cmds.file(q=1, sn=1)
        prod = file_name
        for split in ["prod", "assets", "sequences"]:
            prod = prod.split("/" + split + "/")[0]
        os.environ["PROJ"] = prod
        print("    -> environent variable PROJ set: " + os.environ["PROJ"])

    def set_maya_project(self, *args):
        workSpaceDir = "/".join(cmds.file(q=1, sn=1).split("/")[0:-2])
        if os.path.exists(workSpaceDir):
            cmds.workspace(workSpaceDir, openWorkspace=True)
        print(f"   -> project set to {workSpaceDir}")

    def add_proj_callbacks(self):
        # after open scene
        set_projenv_id = api.MSceneMessage.addCallback(api.MSceneMessage.kBeforeFileRead, self.set_proj_env_variable)
        set_proj_id = api.MSceneMessage.addCallback(api.MSceneMessage.kBeforeFileRead, self.set_maya_project)
        print(set_projenv_id, set_proj_id)


class deadlineCloudSubmitterShelf(pathUtils):
    def __init__(self) -> None:
        super().__init__()
        self.remove_maya_render_submission_button()

    def add_maya_render_submission_button(self):
        module = "maya_fp_deadline_render_pyqt_submitter"
        command = f"import importlib; import {module} as {module}; importlib.reload({module}); {module}.main()"
        label = "FuzzyPixelDeadlineCloudSubmitter"
        shelf_button_icon = (self.maya_tools_path / "fp-deadlinecloud.bmp").as_posix()
        cmds.shelfButton(image1=shelf_button_icon, l=label, c=command, p="AWSDeadline")

    def remove_maya_render_submission_button(self):
        """
        Buttons stack up in maya, so delete the button if it exists already to prevent this.
        """
        buttons = cmds.shelfLayout("AWSDeadline", q=1, ca=1)
        for button in buttons:
            if cmds.control(button, exists=True):
                for button in buttons:
                    if cmds.control(button, exists=True):
                        label = cmds.shelfButton(button, query=True, label=True)
                        if label == "FuzzyPixelDeadlineCloudSubmitter":
                            cmds.deleteUI(button)


def main():
    pr = projResolution()
    dcs = deadlineCloudSubmitterShelf()
    dcs.add_maya_render_submission_button()


if __name__ == "__main__":
    main()
