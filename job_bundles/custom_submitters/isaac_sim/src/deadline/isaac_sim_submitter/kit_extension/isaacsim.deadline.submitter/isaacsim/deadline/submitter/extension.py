# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Extension lifecycle: one menu item, the app child, and one update subscription.

**Tools > Deadline Cloud > Open Deadline Cloud** starts ``deadline-physical-ai gui
--bridge`` (or brings its window to the front when it is already running). The app does
everything that needs AWS; this extension answers its requests on Kit's main thread: the
open stage's file, trajectory replay, and USD references (:mod:`.bridge`, :mod:`.stage`).

The update subscription reads the app's messages and drives replay; it returns at once
when there is nothing to do.
"""

from __future__ import annotations

import gc
import os

import carb
import omni.ext
import omni.kit.actions.core
import omni.kit.app
from isaacsim.gui.components.menu import make_menu_item_description
from omni.kit.menu.utils import MenuItemDescription, add_menu_items, remove_menu_items

from . import procenv
from . import protocol as pr
from . import settings as st
from .bridge import AppProcess, Host
from .stage import (
    ReplaySession,
    add_reference,
    replay_prims,
    selected_prims,
    set_replay_prims,
    stage_file_path,
)

MENU_GROUP = "Tools"
SUBMENU = "Deadline Cloud"
OPEN_TITLE = "Open Deadline Cloud"
LOG = "[isaacsim.deadline.submitter]"

#: The pip distribution that ships this extension.
DISTRIBUTION = "deadline-cloud-for-isaac-sim"
PLACEHOLDER_VERSION = "0.0.0"


def resolve_version(manifest_version: str) -> str:
    """``manifest_version`` unless it is empty or the source placeholder; then the
    installed distribution's version, else ``manifest_version``."""
    if manifest_version and manifest_version != PLACEHOLDER_VERSION:
        return manifest_version
    try:
        from importlib.metadata import version

        return version(DISTRIBUTION)
    except Exception:  # noqa: BLE001
        return manifest_version


def subscribe_update(fn, name: str):
    """Call ``fn(event)`` every update. Kit's event dispatcher (``carb.eventdispatcher`` with
    ``omni.kit.app.GLOBAL_EVENT_UPDATE``) where Kit has it; else the older update event
    stream, which later Kit releases deprecate. Keep the returned object alive."""
    event = getattr(omni.kit.app, "GLOBAL_EVENT_UPDATE", None)
    if isinstance(event, str) and event:
        try:
            import importlib

            dispatcher = importlib.import_module("carb.eventdispatcher")
            return dispatcher.get_eventdispatcher().observe_event(
                event_name=event, on_event=fn, observer_name=name
            )
        except Exception as exc:  # noqa: BLE001
            carb.log_info(f"{LOG} event dispatcher unavailable, using the update stream: {exc}")
    return (
        omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(fn, name=name)
    )


def notify(text: str) -> None:
    """Log ``text`` as an error and, when Kit's notification manager is loaded, show it."""
    carb.log_error(f"{LOG} {text}")
    try:
        import omni.kit.notification_manager as nm

        nm.post_notification(text, status=nm.NotificationStatus.WARNING)
    except Exception as exc:  # noqa: BLE001 - the console has it
        carb.log_info(f"{LOG} no notification shown: {exc!r}")


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str) -> None:
        self._ext_id = ext_id
        self._ext_name = omni.ext.get_extension_name(ext_id)
        self.replay = ReplaySession()
        self._app: AppProcess | None = None
        self._host: Host | None = None
        self._actions, self._menu_items = [], []
        item = make_menu_item_description(self._ext_name, OPEN_TITLE, self.open_app)
        action = getattr(item, "onclick_action", None)
        if action and len(action) == 2:
            self._actions.append(action[1])
        # Tools > Deadline Cloud > Open Deadline Cloud. Keep references, or Python collects
        # the menu.
        self._menu_items = [MenuItemDescription(name=SUBMENU, sub_menu=[item])]
        add_menu_items(self._menu_items, MENU_GROUP)
        self._sub = subscribe_update(self._on_update, "isaacsim.deadline.submitter.poll")

    def on_shutdown(self) -> None:
        if self._menu_items:
            remove_menu_items(self._menu_items, MENU_GROUP)
            self._menu_items = []
        registry = omni.kit.actions.core.get_action_registry()
        for a in self._actions:
            try:
                registry.deregister_action(self._ext_name, a)
            except Exception as exc:  # noqa: BLE001  # pragma: no cover
                carb.log_warn(f"{LOG} deregister_action failed: {exc}")
        self._actions = []
        self._sub = None
        app, self._app, self._host = self._app, None, None
        if app is not None:
            app.close(timeout_s=2.0)  # the app exits on EOF; killed if it does not
        self.replay.traj = None
        gc.collect()

    # -- the app --
    def open_app(self) -> None:
        """Bring the app to the front, starting it first if it is not running."""
        if self._app is not None and self._app.alive:
            self._app.allow_foreground()
            self._app.send(pr.focus())
            return
        if self._app is not None:
            self._app_exited()
        exe, how = procenv.resolve("deadline-physical-ai", st.get_str(st.PHYSICAL_AI_EXECUTABLE))
        if not exe:
            notify(
                f"deadline-physical-ai not found ({how}). Install deadline-cloud-for-isaac-sim[gui] "
                f"or set {st.ROOT}{st.PHYSICAL_AI_EXECUTABLE}."
            )
            return
        try:
            app = AppProcess([exe, "gui", "--bridge"], env=procenv.child_env(exe), log=self._log)
        except OSError as exc:
            notify(f"Could not start {exe}: {exc}")
            return
        self._host = Host(
            self._app_version(),
            self._ext_version(),
            stage_path=stage_file_path,
            load=self._load,
            replay_control=self._replay_control,
            log=self._log,
            replay_prims=replay_prims,
            set_replay_prims=set_replay_prims,
            selection=selected_prims,
        )
        self._app = app
        app.allow_foreground()
        app.send(self._host.hello())

    def _app_exited(self) -> None:
        app, self._app, self._host = self._app, None, None
        if app is not None and app.returncode not in (0, None):
            tail = app.stderr_tail().strip().splitlines()
            notify(
                f"The Deadline Cloud app exited with code {app.returncode}"
                + (f": {tail[-1]}" if tail else "")
            )
            if tail:
                carb.log_warn(f"{LOG} app output:\n" + "\n".join(tail))

    def _log(self, text: str) -> None:
        carb.log_warn(f"{LOG} {text}")

    # -- requests from the app (Kit's main thread) --
    def _load(self, kind: str, path: str) -> str:
        if kind == "trajectory":
            msg = self.replay.load(path)
            self.replay.play()
            return msg + ". Playing; Play and Stop replay it again."
        prim = add_reference(path)
        return f"Added {os.path.basename(path)} to the stage at {prim}."

    def _replay_control(self, action: str) -> str:
        if self.replay.traj is None:
            raise ValueError("Load a trajectory first.")
        if action == "play":
            self.replay.play()
            return "Playing."
        self.replay.stop()
        return "Stopped."

    def _on_update(self, _event) -> None:
        app, host = self._app, self._host
        if app is not None and host is not None:
            for msg in app.poll():
                reply = host.handle(msg)
                if reply is not None:
                    app.send(reply)
            if not app.alive:
                for msg in app.poll():  # anything written just before it exited
                    host.handle(msg)
                self._app_exited()
        try:
            self.replay.on_update()
        except Exception as exc:  # noqa: BLE001 - a broken replay stops; Kit keeps running
            carb.log_warn(f"{LOG} replay: {exc}")
            self.replay.traj = None

    def _ext_version(self) -> str:
        """The ``[package] version`` from extension.toml, which a wheel build stamps with
        the package version. A source checkout keeps the ``0.0.0`` placeholder; then the
        installed distribution's version is used when Kit's Python can see it."""
        try:
            mgr = omni.kit.app.get_app().get_extension_manager()
            version = str(mgr.get_extension_dict(self._ext_id)["package"]["version"] or "")
        except Exception:  # noqa: BLE001  # pragma: no cover
            version = ""
        return resolve_version(version)

    @staticmethod
    def _app_version() -> str:
        try:
            v = carb.settings.get_settings().get("/app/version")
            if v:
                return str(v)
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            carb.log_info(f"{LOG} /app/version unreadable, asking the app: {exc}")
        try:
            return str(omni.kit.app.get_app().get_app_version() or "")
        except Exception:  # noqa: BLE001  # pragma: no cover
            return ""
