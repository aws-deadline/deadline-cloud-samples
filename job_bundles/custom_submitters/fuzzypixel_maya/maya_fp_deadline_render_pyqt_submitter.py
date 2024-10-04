from PySide2.QtUiTools import QUiLoader
from PySide2 import QtCore, QtGui, QtWidgets, QtUiTools
from PySide2.QtWidgets import QStyledItemDelegate, QLineEdit
from pathlib import Path
import maya.cmds as cmds
import platform
import sys
import os
import subprocess
from copy import deepcopy
import re
import boto3
import json
import yaml
import subprocess

from maya_base_paths import pathUtils

pu = pathUtils()
pu.set_appends()


def getMayaWindow():
    import maya.OpenMayaUI as omui
    import shiboken2

    # type: () -> shiboken2.wrapInstance()
    """
  Get the main Maya window as a QtGui.QMainWindow instance
  @return: QtGuit.QMainWindow instance of the top level Maya Window
  """
    pointer = omui.MQtUtil.mainWindow()
    if pointer is not None:
        mayaWin = shiboken2.wrapInstance(int(pointer), QtWidgets.QWidget)
        return mayaWin


class NonEditableDelegate(QStyledItemDelegate):
    """
    Delegate for a table cell that is not editable.
    """

    def createEditor(self, parent, option, index):
        if index.column() == 1 and index.row() == 1:
            # Make the "Age" cell of child2 editable
            editor = QLineEdit(parent)
            return editor
        else:
            return None


class mayaSubmitterUI(QtCore.QObject):
    """
    This is the main submitter UI.
    """

    instance = None  # This will contain an instance of this class.

    def __init__(self, parent=None):
        self.delete_instance()
        self.__class__.instance = self
        super(mayaSubmitterUI, self).__init__(parent)
        self.bp = pathUtils()
        self.tu = deadlineTemplateUtils()
        self.template_dir = self.tu.maya_tools_path / "FuzzyPixelMayaRender"
        self.parameter_file = self.template_dir / "parameter_values.yaml"
        self.template_file = self.template_dir / "template.yaml"
        ui_file = (self.bp.maya_tools_path / "maya_fp_maya_submitter.ui").as_posix()
        ui_file = QtCore.QFile(ui_file)
        ui_file.open(QtCore.QFile.ReadOnly)

        loader = QtUiTools.QUiLoader()
        self.window = loader.load(ui_file)
        self.window.setWindowTitle("FuzzyPixel MayaSubmitter")
        ui_file.close()
        self.widget = loader.load(ui_file, None)
        self.initUI()
        self.window.show()

    def initUI(self):
        # UI Elements
        self.job_name = self.window.findChild(QtWidgets.QLineEdit, "name_field")
        self.farm_name = self.window.findChild(QtWidgets.QComboBox, "farm_combo")
        self.queue_name = self.window.findChild(QtWidgets.QComboBox, "queue_combo")
        self.priority_field = self.window.findChild(QtWidgets.QLineEdit, "priority_field")
        self.job_retry_field = self.window.findChild(QtWidgets.QLineEdit, "job_retry_field")
        self.task_retry_field = self.window.findChild(QtWidgets.QLineEdit, "task_retry_field")
        self.frames_override = self.window.findChild(QtWidgets.QCheckBox, "frames_override")
        self.frames_field = self.window.findChild(QtWidgets.QLineEdit, "frames_field")
        self.frames_field.setReadOnly(True)
        self.output_field = self.window.findChild(QtWidgets.QLineEdit, "output_field")
        self.path_field = self.window.findChild(QtWidgets.QLineEdit, "path_field")
        self.width_field = self.window.findChild(QtWidgets.QLineEdit, "width_field")
        self.height_field = self.window.findChild(QtWidgets.QLineEdit, "height_field")
        self.fleet_attr_combo = self.window.findChild(QtWidgets.QComboBox, "fleet_attr_combo")
        self.login_button = self.window.findChild(QtWidgets.QPushButton, "login_button")
        self.submit_button = self.window.findChild(QtWidgets.QPushButton, "submit_button")
        self.login_label = self.window.findChild(QtWidgets.QLabel, "login_label")
        self.cancel_button = self.window.findChild(QtWidgets.QPushButton, "cancel_button")
        self.render_layer_tree = self.window.findChild(QtWidgets.QTreeWidget, "render_layer_tree")
        self.sui = mayaSubmitterStatusUI(getMayaWindow())
        self.swui = mayaSubmitterWarningUI(getMayaWindow())

        # Main Submitter Button Connections
        self.login_button.clicked.connect(self.handle_login_button_clicked)
        self.submit_button.clicked.connect(self.handle_submit_button_clicked)
        self.cancel_button.clicked.connect(self.handle_cancel_button_clicked)
        self.farm_name.currentIndexChanged.connect(self.handle_farm_combo_updated)
        self.queue_name.currentIndexChanged.connect(self.handle_update_fleet_attr)
        self.frames_override.stateChanged.connect(self.handle_frames_override)

        # Submission Status Button Connections
        self.sui.dismiss_button.clicked.connect(self.handle_dismiss_button_clicked)

        # Submission Warning Button Connections
        self.swui.okay_button.clicked.connect(self.handle_okay_button_clicked)
        self.swui.canceljob_button.clicked.connect(self.handle_canceljob_button_clicked)

        self.update_job_name()
        self.update_farm_combo()
        self.update_paths()
        self.update_resolution()
        self.update_framerange()
        self.get_login_status()
        self.init_render_layer_tree()
        self.set_render_layer_tree()

    def delete_instance(self):
        if self.__class__.instance is not None:
            try:
                self.__class__.instance.deleteLater()
            except Exception as e:
                pass

    def update_job_name(self) -> None:
        """
        Update the job name from Maya query and populate the name field with it.
        """
        file_name = cmds.file(q=True, sn=True, shn=True)
        self.job_name.setText(file_name)

    def update_paths(self):
        """
        Update the parameter GUI with the actual project path
        """
        workspace = cmds.workspace(q=True, active=True)
        output = f"{workspace}/maya/images"
        self.path_field.setText(workspace)
        self.output_field.setText(output)

    def update_resolution(self):
        """
        Update the GUI with the actual resolution
        """
        self.width_field.setText(str(cmds.getAttr("defaultResolution.width")))
        self.height_field.setText(str(cmds.getAttr("defaultResolution.height")))

    def update_framerange(self):
        """
        Update the GUI with the actual framerange
        """
        fs = cmds.getAttr("defaultRenderGlobals.startFrame")
        fe = cmds.getAttr("defaultRenderGlobals.endFrame")
        self.frames_field.setText(f"{int(fs)}-{int(fe)}")

    def init_render_layer_tree(self) -> None:
        """
        Initialize the render layer tree
        """
        # Set up the columns
        self.render_layer_tree.setColumnWidth(0, 150)
        self.render_layer_tree.setColumnWidth(1, 150)

        # Set the editable fields
        layer = self.render_layer_tree.topLevelItem(0)
        size = layer.child(0)
        frame_range = layer.child(1)
        width = size.child(0)
        height = size.child(1)

        # Set a non-editable delegate for the "Name" column
        non_editable_delegate = NonEditableDelegate()
        self.render_layer_tree.setItemDelegateForColumn(0, non_editable_delegate)
        frame_range.setFlags(frame_range.flags() | QtCore.Qt.ItemIsEditable)
        width.setFlags(width.flags() | QtCore.Qt.ItemIsEditable)
        height.setFlags(height.flags() | QtCore.Qt.ItemIsEditable)

    def set_render_layer_tree(self) -> None:
        """
        Update the render layer tree with the current render layers
        """
        top = self.render_layer_tree.topLevelItem(0)
        render_layer_list = self.get_nondefault_render_layers(0)
        num_clones = len(render_layer_list) - 1
        # Create all of the required layers
        while num_clones > 0:
            clone = top.clone()
            self.render_layer_tree.addTopLevelItem(clone)
            num_clones -= 1
        # Update clones with render_layer data
        for i, layer in enumerate(render_layer_list):
            top = self.render_layer_tree.topLevelItem(i)
            size = top.child(0)
            width = size.child(0)
            height = size.child(1)
            frame_range = top.child(1)
            top.setText(0, layer)

            # Update the frame data Note that get_layer_frame_range also sets the layer
            # to the current render layer, so we can get frame range and image size in context.
            frame_list = self.get_layer_frame_range(layer)
            frame_range_string = f"{frame_list[0]}-{frame_list[1]}"
            frame_range.setText(1, frame_range_string)

            # Update image size
            width.setText(1, str(cmds.getAttr("defaultResolution.width")))
            height.setText(1, str(cmds.getAttr("defaultResolution.height")))

            # Update renderable state
            if layer != "defaultRenderLayer":
                layer = f"rs_{layer}"
            check_state = QtCore.Qt.Unchecked
            is_renderable = self.is_render_layer_renderable(layer)
            if is_renderable:
                check_state = QtCore.Qt.Checked
            top.setCheckState(0, check_state)
            if not is_renderable:
                top.setExpanded(False)
            else:
                top.setExpanded(True)
                size.setExpanded(True)

    def get_render_cam(self) -> str:
        """
        Get the render camera
        """
        cameras = cmds.listCameras()
        render_cam_list = []
        render_cam = ""

        for item in cameras:
            if cmds.objExists(item + "Shape.renderable"):
                cmds.setAttr(item + "Shape.renderable", 0)

        for item in cameras:
            if "shotCam" in item:
                if cmds.objExists(item + "Shape.renderable"):
                    render_cam_list.append(item)
                    cmds.setAttr(item + "Shape.renderable", 1)
                    render_cam = item
        return render_cam

    def get_nondefault_render_layers(self, test_renderable) -> list:
        """
        Get a list of non default render layers
        :param test_renderable: Test the renderable state of the render layer
        """
        renderable = False
        r_layer_list = []
        render_layers = cmds.ls(type="renderLayer")
        for layer in render_layers:
            if test_renderable:
                renderable = self.is_render_layer_renderable(layer)
            else:
                renderable = self.is_render_layer_referenced(layer)
            if renderable:
                layer = re.sub("rs_", "", layer)
                r_layer_list.append(layer)
        return r_layer_list

    def is_render_layer_referenced(self, render_layer_name) -> bool:
        referenced = False
        renderable = False
        referenced = cmds.referenceQuery(render_layer_name, isNodeReferenced=True)
        if not referenced:
            renderable = True
        return renderable

    def is_render_layer_renderable(self, render_layer_name) -> bool:
        renderable = False
        referenced = False
        is_renderable = False
        referenced = cmds.referenceQuery(render_layer_name, isNodeReferenced=True)
        renderable = cmds.getAttr(f"{render_layer_name}.renderable")
        if renderable and not referenced:
            is_renderable = True
        return is_renderable

    def update_farm_combo(self) -> None:
        """
        Update the DeadlineCloud farm combo list
        """
        farm_list = self.tu.get_farm_info()
        if farm_list:
            for item in farm_list:
                self.farm_name.addItem(item["displayName"])
                self.farm_name.setItemData(self.farm_name.count() - 1, item["farmId"], QtCore.Qt.UserRole)
        else:
            print("No farm found")
        default_index = self.farm_name.findText(self.tu.default_farm_display_name)
        self.farm_name.setCurrentIndex(default_index)

    def handle_frames_override(self) -> None:
        """
        Handle the frames override check box
        """
        if self.frames_override.isChecked():
            self.frames_field.setReadOnly(False)
        else:
            self.frames_field.setReadOnly(True)

    def handle_farm_combo_updated(self) -> None:
        """
        Update the DeadlineCloud queue combo list based upon the farm combo custom data containing the farmId.
        """
        this_index = self.farm_name.currentIndex()
        farm_id = self.farm_name.itemData(this_index, QtCore.Qt.UserRole)
        self.update_queue(farm_id)
        self.get_fleet_attr_defaults()

    def get_fleet_attr_defaults(self) -> None:
        """
        Get the fleet attribute defaults
        """
        if self.farm_name.currentText() == "FuzzyPixelProdFarm":
            default_queue_index = self.queue_name.findText(self.tu.default_queue)
            self.queue_name.setCurrentIndex(default_queue_index)
            default_fleet_index = self.fleet_attr_combo.findText(self.tu.default_fleet_attr)
            self.fleet_attr_combo.setCurrentIndex(default_fleet_index)

    def handle_login_button_clicked(self) -> None:
        """
        Handle the login button click
        """
        self.tu.deadline_login()
        self.get_login_status()

    def handle_submit_button_clicked(self) -> None:
        """
        Handle the submit button click
        """
        parameter_data = self.update_template_parameters()
        template_data = self.update_template_steps_from_render_layer_tree()
        self.tu.write_template_data(parameter_data, self.parameter_file)
        self.tu.write_template_data(template_data, self.template_file)
        # Handle the submission UI
        self.sui.window.show()
        priority = self.priority_field.text()
        job_retries = self.job_retry_field.text()
        task_retries = self.task_retry_field.text()
        farm_id = self.get_farm_id()
        queue_id = self.get_queue_id()
        submission_status = self.tu.deadline_submit(
            priority, job_retries, task_retries, self.template_dir, farm_id, queue_id
        )
        self.sui.submission_text.setText(submission_status)
        proceed_warning = "Do you wish to proceed?"
        if proceed_warning in submission_status:
            self.swui.warning_text.setText(submission_status)
            self.swui.show()

    def handle_dismiss_button_clicked(self) -> None:
        """
        Handle the submission status dismiss button click
        """
        self.sui.window.close()
        self.window.close()

    def handle_cancel_button_clicked(self) -> None:
        """
        Handle the cancel button click
        """
        self.window.close()

    def handle_okay_button_clicked(self, submit_status) -> None:
        """
        Handle the submission warning okay button click
        """
        proceed_command = "y"
        proceed_status = subprocess.run(
            f"{proceed_command}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.swui.window.close()
        self.sui.window.close()
        self.window.close()

    def handle_canceljob_button_clicked(self) -> None:
        """
        Handle the cancel job button click
        """
        proceed_command = "n"
        proceed_status = subprocess.run(
            f"{proceed_command}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.swui.window.close()
        self.sui.window.close()
        self.window.close()

    def update_queue(self, farm_id) -> None:
        """
        Update the queue
        """
        queue_list = self.tu.get_queue_info(farm_id)
        if queue_list:
            self.queue_name.clear()
            for item in queue_list:
                self.queue_name.addItem(item["displayName"])
                self.queue_name.setItemData(self.queue_name.count() - 1, item["queueId"], QtCore.Qt.UserRole)
        else:
            pass

    def handle_update_fleet_attr(self) -> None:
        """
        Update the fleet attribute based upon the queue.
        """
        farm_id = self.get_farm_id()
        self.update_fleet_attr(farm_id)
        self.get_fleet_attr_defaults()

    def update_fleet_attr(self, farm_id) -> None:
        """
        Update the fleet attributed based upon the farm and queue.
        """
        fleet_list = self.tu.get_fleet_info(farm_id)
        if fleet_list:
            self.fleet_attr_combo.clear()
            for item in fleet_list:
                self.fleet_attr_combo.addItem(item["custom_attr"])
                self.fleet_attr_combo.setItemData(
                    self.fleet_attr_combo.count() - 1, item["attr_name"], QtCore.Qt.UserRole
                )
        else:
            self.fleet_attr_combo.clear()

    def update_template_parameters(self) -> object:
        """
        Update the parameter values
        :return: object: parameter data
        """
        data = self.tu.read_template_data(self.parameter_file)
        data["parameterValues"][0]["value"] = cmds.file(q=True, sn=True)
        data["parameterValues"][1]["value"] = self.frames_field.text()
        data["parameterValues"][3]["value"] = int(self.width_field.text())
        data["parameterValues"][4]["value"] = int(self.height_field.text())
        data["parameterValues"][5]["value"] = self.path_field.text()
        data["parameterValues"][6]["value"] = self.output_field.text()
        this_index = self.fleet_attr_combo.currentIndex()
        data["parameterValues"][13]["value"] = self.fleet_attr_combo.itemData(this_index, QtCore.Qt.UserRole)
        data["parameterValues"][14]["value"] = self.fleet_attr_combo.currentText()
        return data

    def get_login_status(self) -> None:
        """
        Get the login status and update the login button accordingly
        """
        status = self.tu.deadline_get_auth_status()
        if status:
            self.login_label.setStyleSheet("QLabel { color: green; }")
            self.login_label.setText("AUTHENTICATED")
        else:
            self.login_label.setStyleSheet("QLabel { color: red; }")
            self.login_label.setText("NOT AUTHENTICATED")

    def get_farm_id(self) -> str:
        """
        Get the farm id
        """
        this_index = self.farm_name.currentIndex()
        farm_id = self.farm_name.itemData(this_index, QtCore.Qt.UserRole)
        return farm_id

    def get_queue_id(self) -> str:
        """
        Get the queue id
        """
        this_index = self.queue_name.currentIndex()
        queue_id = self.queue_name.itemData(this_index, QtCore.Qt.UserRole)
        return queue_id

    def get_layer_frame_range(self, layer_name) -> list:
        """
        Set the layer and get the frame range
        :param layer_name: The name of the layer
        :return: list: the frame range
        """
        frame_list = []
        if layer_name != "defaultRenderLayer":
            layer_name = f"rs_{layer_name}"
        cmds.editRenderLayerGlobals(currentRenderLayer=layer_name)
        frame_list.append(int(cmds.getAttr("defaultRenderGlobals.startFrame")))
        frame_list.append(int(cmds.getAttr("defaultRenderGlobals.endFrame")))
        return frame_list

    def update_template_steps_from_render_layer_tree(self) -> object:
        """
        Update the template steps from the render layer tree
        """
        data = self.tu.read_template_data(self.template_file)
        render_cam = self.get_render_cam()
        scene = os.path.basename(cmds.file(q=True, sn=True))
        data["name"] = scene
        num_tree_items = self.render_layer_tree.topLevelItemCount()
        copy_list = []
        lre = ".*?\nrender_layer: (.*?)\n.*"
        widthre = ".*?\nimage_width: (.*?)\n.*"
        heightre = ".*?\nimage_height: (.*?)\n.*"
        for i in range(num_tree_items):
            copy_list.append(deepcopy(data["steps"][0]))
        data["steps"] = []
        r = 0
        for i in range(len(copy_list)):
            layer = self.render_layer_tree.topLevelItem(i)
            size = layer.child(0)
            width = size.child(0)
            height = size.child(1)
            frame_range = layer.child(1)
            check_state = layer.checkState(0)
            if check_state == QtCore.Qt.Checked:
                data["steps"].append(copy_list[r])
                data["steps"][r]["name"] = layer.text(0)
                if not self.frames_override.isChecked():
                    frame_range = frame_range.text(1)
                else:
                    frame_range = self.frames_field.text()
                data["steps"][r]["parameterSpace"]["taskParameterDefinitions"][0]["range"] = frame_range
                # Update the layer data
                data["steps"][r]["parameterSpace"]["taskParameterDefinitions"][1]["range"] = [render_cam]
                this_data = data["steps"][r]["stepEnvironments"][0]["script"]["embeddedFiles"][0]
                lm = re.search(lre, this_data["data"])
                this_data["data"] = this_data["data"].replace(lm.group(1), layer.text(0))
                heightm = re.search(heightre, this_data["data"])
                this_data["data"] = this_data["data"].replace(heightm.group(1), height.text(1))
                widthm = re.search(widthre, this_data["data"])
                this_data["data"] = this_data["data"].replace(widthm.group(1), width.text(1))
                data["steps"][r]["stepEnvironments"][0]["script"]["embeddedFiles"][0] = this_data
                r += 1
        return data


class mayaSubmitterStatusUI(QtCore.QObject):
    instance = None  # This will contain an instance of this class.

    def __init__(self, parent=None):
        self.delete_instance()
        self.__class__.instance = self
        super(mayaSubmitterStatusUI, self).__init__(parent)
        self.bp = pathUtils()
        ui_file = (self.bp.maya_tools_path / "maya_fp_maya_submission_status.ui").as_posix()
        ui_file = QtCore.QFile(ui_file)
        ui_file.open(QtCore.QFile.ReadOnly)

        loader = QtUiTools.QUiLoader()
        self.window = loader.load(ui_file)
        self.window.setWindowTitle("Submission Status")
        ui_file.close()
        self.widget = loader.load(ui_file, None)
        self.initUI()

    def initUI(self):
        self.submission_text = self.window.findChild(QtWidgets.QTextEdit, "submission_text")
        self.dismiss_button = self.window.findChild(QtWidgets.QPushButton, "dismiss_button")

    def delete_instance(self):
        if self.__class__.instance is not None:
            try:
                self.__class__.instance.deleteLater()
            except Exception as e:
                pass


class mayaSubmitterWarningUI(QtCore.QObject):
    instance = None  # This will contain an instance of this class.

    def __init__(self, parent=None):
        self.delete_instance()
        self.__class__.instance = self
        super(mayaSubmitterWarningUI, self).__init__(parent)
        self.bp = pathUtils()
        ui_file = (self.bp.maya_tools_path / "maya_fp_maya_submission_warning.ui").as_posix()
        ui_file = QtCore.QFile(ui_file)
        ui_file.open(QtCore.QFile.ReadOnly)

        loader = QtUiTools.QUiLoader()
        self.window = loader.load(ui_file)
        self.window.setWindowTitle("Submission Warning")
        ui_file.close()
        self.widget = loader.load(ui_file, None)
        self.initUI()

    def initUI(self):
        self.warning_text = self.window.findChild(QtWidgets.QTextEdit, "submission_warning").__str__()
        self.okay_button = self.window.findChild(QtWidgets.QPushButton, "okay_button")
        self.canceljob_button = self.window.findChild(QtWidgets.QPushButton, "canceljob_button")

    def delete_instance(self):
        if self.__class__.instance is not None:
            try:
                self.__class__.instance.deleteLater()
            except Exception as e:
                pass


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


class deadlineTemplateUtils(pathUtils):
    def __init__(self):
        super().__init__()
        self.set_farm_vars()
        self.deadline = boto3.client("deadline")

    def read_template_data(self, yaml_data) -> object:
        """
        Read template parameter file and output a data object
        :param yaml_data: str: parameter file
        :return: object: parameter data
        """
        with open(yaml_data, "r") as f:
            data = yaml.safe_load(f)
        return data

    def write_template_data(self, data, yaml_file) -> None:
        """
        Write the parameter data to a yaml file
        """
        with open(yaml_file, "w") as f:
            yaml.dump(data, f, Dumper=NoAliasDumper)
        f.close()

    def get_farm_info(self) -> list:
        """
        Get farm info
        :return: list: farm info
        """
        farm_list = []
        farm_dict = {}
        result = self.deadline.list_farms()
        for farm in result["farms"]:
            farm_dict["farmId"] = farm["farmId"]
            farm_dict["displayName"] = farm["displayName"]
            farm_list.append(deepcopy(farm_dict))
        return farm_list

    def get_queue_info(self, farm_id) -> list:
        """
        Get queue info
        :return: list: queue info
        """
        queue_list = []
        queue_dict = {}
        try:
            result = self.deadline.list_queues(farmId=farm_id)
            for queue in result["queues"]:
                queue_dict["queueId"] = queue["queueId"]
                queue_dict["displayName"] = queue["displayName"]
                queue_list.append(deepcopy(queue_dict))
        except:
            pass
        return queue_list

    def get_fleet_info(self, farm_id) -> list:
        """
        Get fleet info from the farm
        """
        attr_list = []
        attr_dict = {}
        deadline = boto3.client("deadline")
        try:
            result = deadline.list_fleets(farmId=farm_id)
            for fleet in result["fleets"]:
                try:
                    for custom_attr in fleet["configuration"]["customerManaged"]["workerCapabilities"][
                        "customAttributes"
                    ]:
                        attr_dict["attr_name"] = custom_attr["name"]
                        attr_dict["custom_attr"] = custom_attr["values"][0]
                        attr_list.append(deepcopy(attr_dict))
                except:
                    pass
        except:
            pass
        return attr_list

    def deadline_login(self) -> None:
        """
        Login to Deadline
        """
        login_command = f"deadline auth login"
        subprocess.Popen(f"{login_command}", shell=True)

    def deadline_submit(self, priority, job_retries, task_retries, template_file, farm_id, queue_id) -> str:
        """
        Submit to Deadline
        :param template_file: str: template file
        :return: str: submission status
        """
        submit_command = f"deadline bundle submit --yes --priority {priority} --max-failed-tasks-count {job_retries} --max-retries-per-task {task_retries} --farm-id {farm_id} --queue-id {queue_id} {template_file}"
        submit_status = subprocess.run(f"{submit_command}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        submit_status = submit_status.stdout.decode("utf-8").replace("\r", "")
        return submit_status

    def deadline_get_auth_status(self) -> bool:
        """
        Get the auth status
        :return: bool: auth status
        """
        auth_status = subprocess.Popen(f"deadline auth status", shell=True, stdout=subprocess.PIPE)
        auth_status = auth_status.stdout.read()
        if b"AUTHENTICATED" in auth_status:
            return True
        else:
            return False


def main():
    sui = mayaSubmitterUI(getMayaWindow())
    return sui


if __name__ == "__main__":
    main()
