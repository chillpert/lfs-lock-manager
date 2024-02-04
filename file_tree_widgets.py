import os
import re
from functools import partial

import pyperclip
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QMenu

from notification_widget import NotificationDialog
from settings import Settings
from utility import Utility


class FileTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent, data):
        super().__init__(parent, data)

        self.is_directory = None
        self.relative_path = None
        # self.was_selected = False

        self.first_run = True


class LockDataFileTreeWidgetItem(FileTreeWidgetItem):
    def __init__(self, parent, data):
        super().__init__(parent, data)

        self.lock_data = None


class FileTreeWidgetBase(QTreeWidget):
    def __init__(self):
        super().__init__()

        self.current_selection = []

    def notify_copy_transaction(self, num_selected_files):
        dialog = NotificationDialog("Copied %i selected files to clipboard" % num_selected_files, 500, 40)
        dialog.run(self.parent())

    def cache_current_selection(self):
        selected_items = self.get_selected_items()

        if len(selected_items) > 0:
            self.current_selection = selected_items

        # # Remove all previously cached selections that are no longer selected
        # for item in self.current_selection:
        #     if item not in selected_items:
        #         # print("Removed ")
        #         self.current_selection.remove(item)
        #
        # # If the selected item is not already in the current selection, add it
        # for item in selected_items:
        #     if item not in self.current_selection:
        #         self.current_selection.append(item)

    def get_selected_items(self):
        result = []

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if not item.is_directory and item.checkState(0) == Qt.CheckState.Checked:
                result.append(item)

            iterator += 1

        return result

    def set_selected_items(self, items_to_select):
        if len(items_to_select) > 0:
            iterator = QTreeWidgetItemIterator(self)
            while iterator.value():
                item = iterator.value()
                if isinstance(item, LockDataFileTreeWidgetItem):
                    needs_selection = (item.lock_data.lock_id in items_to_select or
                                       item.lock_data.relative_path in items_to_select)
                    if needs_selection:
                        item.setCheckState(0, Qt.CheckState.Checked)
                    else:
                        item.setCheckState(0, Qt.CheckState.Unchecked)

                iterator += 1
            pass

    def unselect_all_items(self):
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            item.setCheckState(0, Qt.CheckState.Unchecked)

    def get_selected_file_paths(self):
        result = []

        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if not item.is_directory and item.checkState(0) == Qt.CheckState.Checked:
                result.append(item.relative_path)

            iterator += 1

        return result

    def copy_relative_file_path_of_tree_selection(self):
        selected_files = self.get_selected_file_paths()
        string_to_copy = " ".join(selected_files)

        if string_to_copy != "":
            pyperclip.copy(string_to_copy.strip())
            self.notify_copy_transaction(len(selected_files))

        return string_to_copy

    def has_non_directory_child(self, item):
        # Check if the item has any children
        if item.childCount() > 0:
            # Iterate over the item's children
            for i in range(item.childCount()):
                child_item = item.child(i)
                if not child_item.is_directory:
                    # Found a non-directory child
                    return True
                else:
                    # Recursively check the child item's children
                    if self.has_non_directory_child(child_item):
                        return True
        return False

    def hide_empty_folders(self):
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            # print("Iterating over " + item.relative_path)
            if not item.isHidden():
                if isinstance(item, FileTreeWidgetItem):
                    if item.is_directory:
                        # print(item.relative_path + " is a directory")
                        if not self.has_non_directory_child(item):
                            # print("❌ " + item.relative_path + " contains no files")
                            item.setHidden(True)
                        else:
                            # print("✅" + item.relative_path + " contains files")
                            pass

            iterator += 1

    def expand_tree_selection(self):
        self.set_expanded_recursively(True, self.currentItem())

    def collapse_tree_selection(self):
        self.set_expanded_recursively(False, self.currentItem())

    def set_expanded_recursively(self, should_expand, item):
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
        selected_items = self.get_selected_file_paths()

        # @TODO: How should we deal with slashes here? In Git Bash we must use forward slashes to run a custom LFS
        #  executable. However, in CMD we need backward slash.
        git_lfs_command = os.path.relpath(Utility.get_git_lfs_path(), Utility.get_project_root_directory())
        git_lfs_command = git_lfs_command.replace('\\', '/')

        git_lfs_operation_type = " lock " if should_lock is True else " unlock "
        command_to_copy = git_lfs_command + git_lfs_operation_type + " ".join(selected_items)

        pyperclip.copy(command_to_copy)
        self.notify_copy_transaction(len(selected_items))

        dialog = NotificationDialog("Copied unlocking command for %i files to clipboard" % len(selected_items), 500, 40)
        dialog.run(self.parent())


class LockingFileTreeWidget(FileTreeWidgetBase):
    def __init__(self):
        super().__init__()

        self.setColumnCount(1)
        self.setColumnWidth(0, 600)
        self.setHeaderLabels(["Files"])

        self.locked_files = []
        self.base_name = ""

    def populate(self, lock_data, default_expansion_depth, filter_string=""):
        self.cache_current_selection()

        path_map = {}

        lfs_tracked_files = Utility.get_git_lfs_tracked_files()
        regex = Settings.lock_mode_file_filter
        lfs_tracked_files = [s for s in lfs_tracked_files if re.match(regex, s)]

        self.clear()

        project_root = Utility.get_project_root_directory()

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

                    item = None

                    if is_directory:
                        item = FileTreeWidgetItem(parent_item, [part])
                        item.setFlags(item.flags() | Qt.ItemIsTristate)
                        item.is_directory = True
                        item.relative_path = path_so_far
                        # print("📁 Directory: '%s'" % path_so_far)
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
                            # print("💿 File: '%s'" % item.relative_path)
                        else:
                            continue

                    assert item
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)

                    if item.relative_path in [selected_item.relative_path for selected_item in self.current_selection]:
                        item.setCheckState(0, Qt.CheckState.Checked)

                    # Expand first
                    depth = path_so_far.count("/")
                    if depth < default_expansion_depth:
                        item.setExpanded(True)

                    path_map[path_so_far] = item
                    parent_item = item
                else:
                    parent_item = path_map[path_so_far]

                path_so_far += "/"

    def contextMenuEvent(self, event):
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
            copy_relative_file_path_action.triggered.connect(self.copy_relative_file_path_of_tree_selection)

            request_unlock_action = menu.addAction("Copy locking command")
            request_unlock_action.triggered.connect(partial(self.request_locking_operation, True))

            action = menu.exec_(self.mapToGlobal(event.pos()))


class UnlockingFileTreeWidget(FileTreeWidgetBase):
    def __init__(self):
        super().__init__()

        self.setColumnCount(3)
        self.setColumnWidth(0, 600)
        self.setHeaderLabels(["Files", "Owner", "Id"])

        self.selected_git_user = ""

    def populate(self, lock_data, selected_git_user, default_expansion_depth, filter_string=""):
        # Memorize current selection so we can restore it when filtering
        self.cache_current_selection()
        # print("💾 cached %i selected items" % len(self.current_selection))
        # if len(self.current_selection) > 0:
        #     print("we got some in the cache")

        self.selected_git_user = selected_git_user
        self.clear()

        project_root = Utility.get_project_root_directory()
        is_admin = Utility.is_git_user_admin()

        path_map = {}

        for data in lock_data:
            file_path = data.relative_path
            path_parts = file_path.split("/")

            parent_item = self.invisibleRootItem()
            path_so_far = ""

            for part in path_parts:
                path_so_far += part
                if path_so_far not in path_map:
                    # Only display content that is matching the selected user
                    if data.lock_owner != selected_git_user and selected_git_user != "All":
                        continue

                    # Do not populate meta-data fields if this is a directory
                    is_directory = os.path.isdir(project_root + path_so_far)
                    is_file = os.path.isfile(project_root + path_so_far)

                    # Assuming files all have a file ending
                    is_non_local_directory = not is_directory and not is_file and path_so_far.count(".") == 0

                    # Making sure that no directories ever display meta-data
                    show_meta_data = ((is_file or not data.is_local_file)
                                      and not is_non_local_directory and not is_directory)

                    # text = "\uf071 " + part if show_meta_data and not data.is_local_file else part
                    text = part
                    owner = data.lock_owner if show_meta_data else ""
                    lock_id = str(data.lock_id) if show_meta_data else ""

                    if show_meta_data:
                        matched_filter = False
                        requires_filter = filter_string != ""
                        if requires_filter:
                            # match_score = fuzz.partial_ratio(filter_string.lower(), file_path.lower())
                            # if match_score > 10:
                            if filter_string.lower() in file_path.lower():
                                # print("✅ Matched: '%s' with '%s'" % (filter_string.lower(), file_path.lower()))
                                matched_filter = True

                        if not requires_filter or (requires_filter and matched_filter):
                            item = LockDataFileTreeWidgetItem(parent_item, [text, owner, lock_id])
                            item.lock_data = data
                            item.is_directory = False
                            item.relative_path = file_path

                            if show_meta_data and not data.is_local_file:
                                icon = QIcon(Utility.resource_path("resources/icons/warning.png"))
                                item.setIcon(0, icon)

                            if requires_filter:
                                item.setExpanded(True)
                            # print("Registered '%s' as file item with relative path '%s'" % (part, file_path))
                    else:
                        item = FileTreeWidgetItem(parent_item, [text])
                        item.setFlags(item.flags() | Qt.ItemIsTristate)
                        item.is_directory = True
                        item.relative_path = path_so_far
                        # print("Registered '%s' as directory item with relative path '%s'" % (part, path_so_far))

                    if show_meta_data and not data.is_local_file:
                        item.setToolTip(0, "Warning: File does not exist locally")

                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Unchecked)

                    # for thing in self.current_selection:
                    #     print("here: " + thing.relative_path)

                    # THIS IS NEVER REACHED BECAUSE WE FILTERED ALL FILES, THUS WE CANNOT RESTORE
                    """
                    Turns out every time I add anything to the filter the selection is halved with the next population.
                    This is with the more sophisticated approach to caching.
                    
                    With the simplest caching, we receive 
                    """
                    # assert False
                    if item.relative_path in [selected_item.relative_path for selected_item in self.current_selection]:
                        item.setCheckState(0, Qt.CheckState.Checked)

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
            pass
            # print("huh?")
            # self.current_selection.clear()

    def get_selected_file_paths(self):
        selected_items = self.get_selected_items()
        return [item.lock_data.relative_path for item in selected_items]

    def contextMenuEvent(self, event):
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
                copy_relative_file_path_action.triggered.connect(self.copy_relative_file_path_of_tree_selection)

                request_unlock_action = menu.addAction("Copy unlocking command")
                request_unlock_action.triggered.connect(partial(self.request_locking_operation, False))

                request_lock_action = menu.addAction("Copy locking command")
                request_lock_action.triggered.connect(partial(self.request_locking_operation, True))

            action = menu.exec_(self.mapToGlobal(event.pos()))

    def copy_lock_id_of_tree_selection(self):
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
            self.notify_copy_transaction(len(selected_items))

        return string_to_copy
