# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Qt view helpers shared by the app's panes.

Every table and list keeps a fixed height and shows its loading or empty state as text
inside itself, so nothing on screen moves while data arrives or the selection changes.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

#: Rows every table and list shows; more rows scroll.
VISIBLE_ROWS = 5
#: Marks the placeholder row, so callers can tell it from a real one.
PLACEHOLDER_ROLE = QtCore.Qt.ItemDataRole.UserRole + 7


def fix_rows(view: QtWidgets.QAbstractItemView, rows: int = VISIBLE_ROWS) -> None:
    """Make ``view`` exactly ``rows`` rows tall (plus a table's header)."""
    frame = 2 * view.frameWidth()
    if isinstance(view, QtWidgets.QTableView):
        row_h = view.verticalHeader().defaultSectionSize()
        view.setFixedHeight(view.horizontalHeader().sizeHint().height() + rows * row_h + frame)
    else:
        row_h = max(view.sizeHintForRow(0), view.fontMetrics().height() + 8)
        view.setFixedHeight(rows * row_h + frame)


def show_message(view: QtWidgets.QAbstractItemView, text: str) -> None:
    """Replace a table's or list's rows with one unselectable row of dimmed ``text``
    ("Reading parameters...", "No jobs in this queue")."""
    off = QtCore.Qt.ItemFlag.NoItemFlags
    color = view.palette().color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text)
    if isinstance(view, QtWidgets.QTableWidget):
        view.clearSpans()
        view.setRowCount(1)
        for col in range(view.columnCount()):
            cell = QtWidgets.QTableWidgetItem(text if col == 0 else "")
            cell.setFlags(off)
            cell.setForeground(color)
            cell.setData(PLACEHOLDER_ROLE, True)
            view.setItem(0, col, cell)
        if view.columnCount() > 1:
            view.setSpan(0, 0, 1, view.columnCount())
    elif isinstance(view, QtWidgets.QListWidget):
        view.clear()
        entry = QtWidgets.QListWidgetItem(text)
        entry.setFlags(off)
        entry.setForeground(color)
        entry.setData(PLACEHOLDER_ROLE, True)
        view.addItem(entry)


def is_message(view: QtWidgets.QAbstractItemView) -> bool:
    """``view`` holds only a :func:`show_message` row."""
    if isinstance(view, QtWidgets.QTableWidget) and view.rowCount() == 1:
        cell = view.item(0, 0)
        return bool(cell is not None and cell.data(PLACEHOLDER_ROLE))
    if isinstance(view, QtWidgets.QListWidget) and view.count() == 1:
        entry = view.item(0)
        return bool(entry is not None and entry.data(PLACEHOLDER_ROLE))
    return False


def clear_message(view: QtWidgets.QAbstractItemView) -> None:
    """Undo :func:`show_message` before filling real rows."""
    if is_message(view):
        if isinstance(view, QtWidgets.QTableWidget):
            view.clearSpans()
            view.setRowCount(0)
        elif isinstance(view, QtWidgets.QListWidget):
            view.clear()
