"""
This module implements QTreeWidget-based file tree widgets for displaying lockable or locked
files.
"""
import os
import re
from functools import partial
from typing import override

import pyperclip
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QMenu

import lfs_lock_parser
import pyqt_helpers
from settings import Settings
import utility


class FileTreeWidgetItem(QTreeWidgetItem):
    # pylint: disable=too-few-public-methods
    """
    A QTreeWidgetItem-derivative for generic files and folders
    """

    def __init__(self, parent, data):
        super().__init__(parent, data)

        self.is_directory: bool
        self.relative_path: str


class LockDataFileTreeWidgetItem(FileTreeWidgetItem):
    # pylint: disable=too-few-public-methods
    """
    A further specialized QTreeWidgetItem for locked files.
    """

    def __init__(self, parent, data):
        super().__init__(parent, data)

        self.lock_data: lfs_lock_parser.LfsLockData


class FileTreeWidgetBase(QTreeWidget):
    """
    A base class to implement common functionality and data for specialised file tree widgets,
    i.e. file tree widgets for handling files to lock or files to unlock.
    """

    def __init__(self):
        super().__init__()

        self.current_selection = []

    def _notify_copy_transaction(self, num_selected_files: int):
        dialog = pyqt_helpers.NotificationDialog(
            f"Copied {num_selected_files} selected files to clipboard", 500, 40)
        dialog.run(self.parent())

    def _cache_current_selection(self):
        selected_items = self.get_selected_items()

        if len(selected_items) > 0:
            self.current_selection = selected_items

    def get_selected_items(self):
        """
        This function retrieves all checked items, except directories.
        :return: All checked non-directory QTreeWidgetItems
        """
        result = []

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if not item.is_directory and item.checkState(0) == Qt.Checked:
                result.append(item)

            iterator += 1

        return result

    def set_selected_items(self, items_to_select: list):
        """
        This function allows the current selection to be overwritten.
        :param items_to_select: A list of items to select which can either be a list of relative
        file paths or a list of LockDataFileTreeWidgetItems
        """
        if len(items_to_select) > 0:
            iterator = QTreeWidgetItemIterator(self)
            while iterator.value():
                item = iterator.value()

                needs_selection = False

                # For applying selections in unlocking mode
                if isinstance(item, LockDataFileTreeWidgetItem):
                    needs_selection = (item.lock_data.lock_id in items_to_select or
                                       item.lock_data.relative_path in items_to_select)
                # For applying selections in locking mode
                elif isinstance(item, FileTreeWidgetItem):
                    needs_selection = item.relative_path in items_to_select

                # Update check state
                item.setCheckState(0,
                                   Qt.Checked if needs_selection else
                                   Qt.Unchecked)

                iterator += 1

    def unselect_all_items(self):
        """
        This function allows to clear the current selection.
        """
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, Qt.Unchecked)

    def get_selected_file_paths(self):
        """
        This function retrieves the relative file paths of all selected files.
        :return: All relative file paths
        """
        result = []

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if not item.is_directory and item.checkState(0) == Qt.Checked:
                result.append(item.relative_path)

            iterator += 1

        return result

    def copy_relative_file_path_of_tree_selection(self):
        """
        This function copies all selected relative file paths to the clipboard.
        :return: Returns the string that was copied
        """
        selected_files = self.get_selected_file_paths()
        string_to_copy = " ".join(selected_files)

        if string_to_copy != "":
            pyperclip.copy(string_to_copy.strip())
            self._notify_copy_transaction(len(selected_files))

        return string_to_copy

    def _has_non_directory_child(self, item: QTreeWidgetItem):
        # Check if the item has any children
        if item.childCount() > 0:
            # Iterate over the item's children
            for i in range(item.childCount()):
                child_item = item.child(i)
                if not child_item.is_directory:
                    # Found a non-directory child
                    return True

                # Recursively check the child item's children
                if self._has_non_directory_child(child_item):
                    return True
        return False

    def hide_empty_folders(self):
        """
        This function hides all empty folders in the file tree widget.
        """
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if not item.isHidden():
                if isinstance(item, FileTreeWidgetItem):
                    if item.is_directory:
                        if not self._has_non_directory_child(item):
                            item.setHidden(True)

            iterator += 1

    def expand_tree_selection(self):
        """
        This function can be used to recursively expand the file tree relative to the element
        that was selected.
        """
        FileTreeWidgetBase.set_expanded_recursively(True, self.currentItem())

    def collapse_tree_selection(self):
        """
        This function can be used to recursively collapse the file tree relative to the element
        that was selected.
        """
        FileTreeWidgetBase.set_expanded_recursively(False, self.currentItem())

    @staticmethod
    def set_expanded_recursively(should_expand, item: QTreeWidgetItem):
        """
        This function can expand or collapse all children of the given item recursively.
        :param should_expand: If true, all children will expand
        :param item: The item whose children are considered
        """
        stack = []
        selected_item = item
        stack.append(selected_item)

        selected_item.setExpanded(should_expand)

        while stack:
            item = stack.pop()
            item.setExpanded(should_expand)

            for index in range(item.childCount()):
                child_item = item.child(index)
                stack.append(child_item)

    def enforce_default_expansion_depth(self):
        """
        This function sets the current expansion of the entire tree to the default value
        specified in the Settings module.
        """
        if Settings.default_expansion_depth <= 0:
            return

        root_item = self.invisibleRootItem()
        stack = [(root_item, 0)]

        root_item.setExpanded(True)

        while stack:
            item, current_depth = stack.pop()
            item.setExpanded(True)

            if current_depth < Settings.default_expansion_depth:
                for i in range(item.childCount()):
                    child_item = item.child(i)
                    stack.append((child_item, current_depth + 1))

    def request_locking_operation(self, should_lock: bool):
        """
        This function generates an LFS locking or unlocking command by combining the desired
        Git-LFS executable with the relative file path of all selected items in the tree.
        :param should_lock:
        """
        selected_items = self.get_selected_file_paths()

        # @TODO: How should we deal with slashes here? In Git Bash we must use forward slashes to
        # run a custom LFS executable. However, in CMD we need backward slash.
        git_lfs_command = os.path.relpath(utility.get_git_lfs_path(),
                                          utility.get_project_root_directory())
        git_lfs_command = git_lfs_command.replace('\\', '/')

        git_lfs_operation_type = " lock " if should_lock is True else " unlock "
        command_to_copy = git_lfs_command + git_lfs_operation_type + " ".join(selected_items)

        pyperclip.copy(command_to_copy)
        self._notify_copy_transaction(len(selected_items))

        dialog = pyqt_helpers.NotificationDialog(
            f"Copied unlocking command for {len(selected_items)} files to clipboard", 500, 40)
        dialog.run(self.parent())


class LockingFileTreeWidget(FileTreeWidgetBase):
    """
    This file tree widget is specialised for displaying non-locked files and handle their
    selection by the user.
    """

    def __init__(self):
        super().__init__()

        self.setColumnCount(1)
        self.setColumnWidth(0, 600)
        self.setHeaderLabels(["Files"])

        self.locked_files = []
        self.base_name: str

    def populate(self, lock_data: [lfs_lock_parser.LfsLockData], default_expansion_depth: int,
                 filter_string=""):
        # pylint: disable=too-many-locals,too-many-branches
        """
        This function populates the tree, i.e. it parses the non-locked files, so that it can be
        displayed in the tree widget.
        :param lock_data: The LFS lock data to make sure all files are not locked
        :param default_expansion_depth: The tree's default expansion depth which will be enforced
        everytime this function is called
        :param filter_string: A string to filter the tree by which is used by another search
        field widget
        """
        self._cache_current_selection()

        path_map = {}

        lfs_tracked_files = utility.get_git_lfs_tracked_files()
        regex = Settings.lock_mode_file_filter
        lfs_tracked_files = [s for s in lfs_tracked_files if re.match(regex, s)]

        self.clear()

        project_root = utility.get_project_root_directory()

        # pylint: disable=too-many-nested-blocks
        for tracked_file in lfs_tracked_files:
            file_path = tracked_file
            path_parts = file_path.split("/")

            parent_item = self.invisibleRootItem()
            path_so_far = ""

            for part in path_parts:
                path_so_far += part
                if path_so_far not in path_map:
                    is_directory = os.path.isdir(project_root + path_so_far)

                    # Skip already locked files
                    # @NOTE: This also prevents displaying empty directories
                    if file_path in [data.relative_path for data in lock_data]:
                        continue

                    item: FileTreeWidgetItem

                    if is_directory:
                        item = FileTreeWidgetItem(parent_item, [part])
                        item.setFlags(item.flags() | Qt.ItemIsTristate)
                        item.is_directory = True
                        item.relative_path = path_so_far
                    else:
                        matched_filter = False
                        requires_filter = filter_string != ""
                        if requires_filter:
                            if filter_string.lower() in file_path.lower():
                                matched_filter = True

                        if not requires_filter or (requires_filter and matched_filter):
                            item = FileTreeWidgetItem(parent_item, [part])
                            item.is_directory = False
                            item.relative_path = file_path
                        else:
                            continue

                    assert item
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)

                    if item.relative_path in [selected_item.relative_path for selected_item in
                                              self.current_selection]:
                        item.setCheckState(0, Qt.Checked)

                    # Expand first
                    depth = path_so_far.count("/")
                    if depth < default_expansion_depth:
                        item.setExpanded(True)

                    path_map[path_so_far] = item
                    parent_item = item
                else:
                    parent_item = path_map[path_so_far]

                path_so_far += "/"

    @override
    def contextMenuEvent(self, event):
        # pylint: disable=invalid-name
        """
        This function defines the context menu options and sets up callbacks.
        :param event: The Qt event
        """
        item = self.currentItem()
        if item is not None:
            is_directory = item.is_directory

            menu = QMenu(self)
            if is_directory:
                expand_action = menu.addAction("Expand children")
                expand_action.triggered.connect(self.expand_tree_selection)

                collapse_action = menu.addAction("Collapse children")
                collapse_action.triggered.connect(self.collapse_tree_selection)
            else:
                pass

            copy_relative_file_path_action = menu.addAction("Copy relative file path")
            copy_relative_file_path_action.triggered.connect(
                self.copy_relative_file_path_of_tree_selection)

            request_unlock_action = menu.addAction("Copy locking command")
            request_unlock_action.triggered.connect(partial(self.request_locking_operation, True))

            menu.exec_(self.mapToGlobal(event.pos()))


class UnlockingFileTreeWidget(FileTreeWidgetBase):
    """
    This file tree widget is specialised for displaying file locks and their associated
    information and handling user selection.
    """

    def __init__(self):
        super().__init__()

        self.setColumnCount(3)
        self.setColumnWidth(0, 600)
        self.setHeaderLabels(["Files", "Owner", "Id"])

        self.selected_git_user = ""

    def populate(self, lock_data: [lfs_lock_parser.LfsLockData], selected_git_user: str,
                 default_expansion_depth: int, filter_string=""):
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        This function populates the tree, i.e. it parses the file locks, so that it can be 
        displayed in the tree widget. The function only displays locks of the specified Git user.
        :param lock_data: The LFS lock data to display
        :param selected_git_user: The currently selected Git user
        :param default_expansion_depth: The tree's default expansion depth which will be enforced 
        everytime this function is called.
        :param filter_string: A string to filter the tree by which is used by another search 
        field widget.
        """

        # Memorize current selection so we can restore it when filtering
        self._cache_current_selection()

        self.selected_git_user = selected_git_user
        self.clear()

        project_root = utility.get_project_root_directory()

        path_map = {}

        # pylint: disable=too-many-nested-blocks
        for data in lock_data:
            file_path = data.relative_path
            path_parts = file_path.split("/")

            parent_item = self.invisibleRootItem()
            path_so_far = ""

            for part in path_parts:
                path_so_far += part
                if path_so_far not in path_map:
                    # Only display content that is matching the selected user
                    if selected_git_user not in (data.lock_owner, 'All'):
                        continue

                    # Do not populate meta-data fields if this is a directory
                    is_directory = os.path.isdir(project_root + path_so_far)
                    is_file = os.path.isfile(project_root + path_so_far)

                    # Assuming files all have a file ending
                    is_non_local_directory = not is_directory and not is_file and path_so_far.count(
                        ".") == 0

                    # Making sure that no directories ever display meta-data
                    show_meta_data = ((is_file or not data.is_local_file)
                                      and not is_non_local_directory and not is_directory)

                    text = part
                    owner = data.lock_owner if show_meta_data else ""
                    lock_id = str(data.lock_id) if show_meta_data else ""

                    item = None

                    if show_meta_data:
                        matched_filter = False
                        requires_filter = filter_string != ""
                        if requires_filter:
                            if filter_string.lower() in file_path.lower():
                                matched_filter = True

                        if not requires_filter or (requires_filter and matched_filter):
                            item = LockDataFileTreeWidgetItem(parent_item, [text, owner, lock_id])
                            item.lock_data = data
                            item.is_directory = False
                            item.relative_path = file_path

                            if show_meta_data and not data.is_local_file:
                                icon = QIcon(utility.resource_path("resources/icons/warning.png"))
                                item.setIcon(0, icon)

                            if requires_filter:
                                item.setExpanded(True)
                    else:
                        item = FileTreeWidgetItem(parent_item, [text])
                        item.setFlags(item.flags() | Qt.ItemIsTristate)
                        item.is_directory = True
                        item.relative_path = path_so_far

                    if isinstance(item, QTreeWidgetItem):
                        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                        item.setCheckState(0, Qt.Unchecked)

                        if show_meta_data and not data.is_local_file:
                            item.setToolTip(0, "Warning: File does not exist locally")

                        if item.relative_path in [selected_item.relative_path for selected_item in
                                                  self.current_selection]:
                            item.setCheckState(0, Qt.Checked)

                    # Expand first
                    depth = path_so_far.count("/")
                    if depth < default_expansion_depth:
                        item.setExpanded(True)

                    path_map[path_so_far] = item
                    parent_item = item
                else:
                    parent_item = path_map[path_so_far]

                path_so_far += "/"

        selected_items_after_populating = self.get_selected_items()
        if len(selected_items_after_populating) == 0 and len(self.current_selection) > 0:
            # self.current_selection.clear()
            pass

    def get_selected_file_paths(self):
        selected_items = self.get_selected_items()
        return [item.lock_data.relative_path for item in selected_items]

    @override
    def contextMenuEvent(self, event):
        # pylint: disable=invalid-name
        """
        This function defines the context menu options and sets up callbacks.
        :param event: The Qt event
        """
        item = self.currentItem()
        if item is not None:
            is_directory = item.is_directory

            menu = QMenu(self)
            if is_directory:
                expand_action = menu.addAction("Expand children")
                expand_action.triggered.connect(self.expand_tree_selection)

                collapse_action = menu.addAction("Collapse children")
                collapse_action.triggered.connect(self.collapse_tree_selection)
            else:
                pass

            selected_items = self.get_selected_items()
            if len(selected_items) > 0:
                copy_lock_id_action = menu.addAction("Copy lock ID")
                copy_lock_id_action.triggered.connect(self.copy_lock_id_of_tree_selection)

                copy_relative_file_path_action = menu.addAction("Copy relative file path")
                copy_relative_file_path_action.triggered.connect(
                    self.copy_relative_file_path_of_tree_selection)

                request_unlock_action = menu.addAction("Copy unlocking command")
                request_unlock_action.triggered.connect(
                    partial(self.request_locking_operation, False))

                request_lock_action = menu.addAction("Copy locking command")
                request_lock_action.triggered.connect(partial(self.request_locking_operation, True))

            menu.exec_(self.mapToGlobal(event.pos()))

    def copy_lock_id_of_tree_selection(self):
        """
        This function retrieves all Git LFS lock IDs of all selected files and copies them to the
        clipboard.
        :return: Returns the string that was copied
        """
        string_to_copy = ""

        selected_items = self.get_selected_items()
        if len(selected_items) > 0:
            for item in selected_items:
                if isinstance(item, LockDataFileTreeWidgetItem):
                    string_to_copy += " " + str(item.lock_data.lock_id)
        else:
            item = self.currentItem()
            if isinstance(item, LockDataFileTreeWidgetItem):
                if not item.is_directory:
                    string_to_copy = item.lock_data.lock_id

        if string_to_copy != "":
            pyperclip.copy(string_to_copy)
            self._notify_copy_transaction(len(selected_items))

        return string_to_copy
