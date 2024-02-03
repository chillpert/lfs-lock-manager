import os
import subprocess
from abc import abstractmethod

import pyperclip
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QLineEdit, QComboBox, QHBoxLayout, \
    QSizePolicy

from file_tree_widgets import LockingFileTreeWidget, UnlockingFileTreeWidget
from lfs_lock_parser import LfsLockParser
from notification_widget import NotificationDialog
from settings import Settings
from utility import Utility
from worker_thread import WorkerThread


class LockingWidgetBase(QWidget):
    def __init__(self):
        super().__init__()

        # Data we are working with
        self.git_user = Utility.get_git_user()  # The current git user
        self.selected_git_user = self.git_user  # The currently selected git user

        self.sub_layout_width = 150
        self.sub_layout_height = 30
        self.sub_layout_text_size = 'font-size: 14px'

        # Subscribe to lock data updates
        LfsLockParser.subscribe_to_update(self)

    def exec_locking_operation_on_file_list(self, file_list):
        dialog = NotificationDialog("Locking %i files" % len(file_list), 400, 40)
        dialog.run(self.parent())

        worker = WorkerThread(self._exec_locking_operation_on_file_list, file_list, True)
        worker.exec(self._on_finished_locking_operation)

    def exec_unlocking_operation_on_file_list(self, file_list):
        dialog = NotificationDialog("Unlocking %i files" % len(file_list), 400, 40)
        dialog.run(self.parent())

        worker = WorkerThread(self._exec_locking_operation_on_file_list, file_list, False)
        worker.exec(self._on_finished_locking_operation)

    def _on_finished_locking_operation(self, result: bool):
        print("Finished LFS locking operation.")

        if result is True:
            # Only parse locks if a locking operation was performed
            LfsLockParser.parse_locks_async()
        else:
            # Re-enable the widget
            self.setEnabled(True)
            QApplication.processEvents()

    @staticmethod
    def _exec_locking_operation_on_file_list(file_list: [], should_lock: bool):
        """
        Perform a locking operation which can either execute lfs unlock or lock.
        :param file_list: A list of files to perform the action on
        :param should_lock: If true, the locking operation will be lfs lock. Otherwise, lfs unlock.
        :return: Return true if a locking operation was performed (either lock or unlock)
        """
        git_command = Utility.get_git_lfs_path()

        if should_lock:
            git_command += " lock "
        else:
            git_command += " unlock "

        project_root = Utility.get_project_root_directory()

        if not should_lock:
            non_owned_files = []
            owned_files = []

            if Utility.is_git_user_admin():
                for file in file_list:
                    # We only need to force unlock non-owning file locks
                    file_owner = LfsLockParser.get_lock_owner_of_file(file)
                    if file_owner != Utility.get_git_user():
                        print("Appending file '%s' to non-owning files (owner '%s')." % (file, file_owner))
                        non_owned_files.append(file)
                    else:
                        print("Appending file '%s' to owning files." % file)
                        owned_files.append(file)

                git_admin_command = git_command + "--force "
                admin_command = git_admin_command.split() + file_list
                print("Executing admin command (%i): %s" % (len(admin_command), admin_command))
                Utility.run_command(admin_command, project_root)

                # Filter all non-owning files from the file list
                if len(non_owned_files) > 0:
                    file_list.clear()
                    file_list = owned_files

        # Proceed with the remaining locks
        command = git_command.split() + file_list
        print("Executing command (%i): %s" % (len(command), command))
        Utility.run_command(command, project_root)

        return True

    @abstractmethod
    def on_lock_data_update(self):
        pass

    def _on_tree_selection_changed(self):
        pass

    def _create_tree_filter_widget(self):
        tree_filter_widget = QLineEdit()
        tree_filter_widget.textChanged.connect(self._on_tree_filter_text_changed)
        tree_filter_widget.setPlaceholderText("Search for files and folders ...")

        return tree_filter_widget

    @abstractmethod
    def _on_tree_filter_text_changed(self, text):
        pass

    def _create_apply_selection_from_clipboard_button_widget(self):
        apply_selection_from_clipboard_button_widget = QPushButton('Apply selection from Clipboard', self)
        apply_selection_from_clipboard_button_widget.clicked.connect(self._on_apply_selection_from_clipboard_pressed)
        apply_selection_from_clipboard_button_widget.setFixedSize(250, self.sub_layout_height)
        apply_selection_from_clipboard_button_widget.setStyleSheet(self.sub_layout_text_size)

        return apply_selection_from_clipboard_button_widget

    def _on_apply_selection_from_clipboard_pressed(self):
        clipboard_string = pyperclip.paste()
        items = clipboard_string.split()
        self.file_tree_widget.set_selected_items(items)

        dialog = NotificationDialog("Selected %i items from clipboard" % len(items), 500, 40)
        dialog.run(self.parent())


class LockingWidget(LockingWidgetBase):
    def __init__(self):
        super().__init__()

        base_layout = QVBoxLayout()
        base_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout = QHBoxLayout()
        sub_layout.setAlignment(Qt.AlignLeft)
        base_layout.addLayout(sub_layout)

        # Widgets for sub-layout
        self.lock_button_widget = self.create_lock_button_widget()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.apply_selection_from_clipboard_button_widget = self._create_apply_selection_from_clipboard_button_widget()

        sub_layout.addWidget(self.lock_button_widget)
        sub_layout.addWidget(spacer)
        sub_layout.addWidget(self.apply_selection_from_clipboard_button_widget)

        # Widgets for main layout
        self.tree_filter_widget = self._create_tree_filter_widget()
        self.file_tree_widget = self.create_file_tree_widget()

        base_layout.addWidget(self.tree_filter_widget)
        base_layout.addWidget(self.file_tree_widget)

        self.setLayout(base_layout)

    def _on_tree_filter_text_changed(self, text):
        self.file_tree_widget.populate(LfsLockParser.lock_data, Settings.default_expansion_depth, text)

        self.file_tree_widget.hide_empty_folders()

        should_expand = True if text != "" else False
        root_item = self.file_tree_widget.invisibleRootItem()

        # print("Text: '%s' expanding: %i" % (text, should_expand))
        self.file_tree_widget.set_expanded_recursively(should_expand, root_item)
        self.file_tree_widget.enforce_default_expansion_depth()

    def on_lock_data_update(self):
        print("Locking widget: Lock data was updated. Re-populating tree ...")
        self.file_tree_widget.populate(LfsLockParser.lock_data, Settings.default_expansion_depth)

    def create_file_tree_widget(self):
        tree_widget = LockingFileTreeWidget()
        tree_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)
        # tree_widget.populate(LfsLockParser.lock_data, Settings.default_expansion_depth)

        return tree_widget

    def create_lock_button_widget(self):
        lock_button_widget = QPushButton('Lock', self)
        lock_button_widget.clicked.connect(self.on_locked_pressed)
        lock_button_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)
        lock_button_widget.setStyleSheet(self.sub_layout_text_size)

        return lock_button_widget

    def on_locked_pressed(self):
        self.setEnabled(False)
        QApplication.processEvents()

        # Extract lock Ids
        selected_files = self.file_tree_widget.get_selected_file_paths()
        file_list = [str(data) for data in selected_files]

        self.exec_locking_operation_on_file_list(file_list)


class UnlockingWidget(LockingWidgetBase):
    def __init__(self):
        super().__init__()

        base_layout = QVBoxLayout()
        base_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout = QHBoxLayout()
        sub_layout.setAlignment(Qt.AlignLeft)
        base_layout.addLayout(sub_layout)

        # Widgets for sub-layout
        self.unlock_button_widget = self.create_unlock_button_widget()
        self.lock_owner_selection_widget = self.create_lock_owner_selection_widget()
        self.apply_selection_from_clipboard_button_widget = self._create_apply_selection_from_clipboard_button_widget()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        sub_layout.addWidget(self.unlock_button_widget)
        sub_layout.addWidget(self.lock_owner_selection_widget)
        sub_layout.addWidget(spacer)
        sub_layout.addWidget(self.apply_selection_from_clipboard_button_widget)

        # Widgets for main layout
        self.tree_filter_widget = self._create_tree_filter_widget()
        self.file_tree_widget = self.create_file_tree_widget()

        base_layout.addWidget(self.tree_filter_widget)
        base_layout.addWidget(self.file_tree_widget)

        self.setLayout(base_layout)

    def _on_tree_filter_text_changed(self, text):
        self.file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                       Settings.default_expansion_depth, text)

        self.file_tree_widget.hide_empty_folders()

        should_expand = True if text != "" else False
        root_item = self.file_tree_widget.invisibleRootItem()

        # print("Text: '%s' expanding: %i" % (text, should_expand))
        self.file_tree_widget.set_expanded_recursively(should_expand, root_item)
        self.file_tree_widget.enforce_default_expansion_depth()

    def on_lock_data_update(self):
        print("Unlock widget: Lock data was updated. Re-populating tree ...")
        self.file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                       Settings.default_expansion_depth)

        self.populate_lock_owner_selection_widget(self.lock_owner_selection_widget)

    def register_file_tree_widget(self):
        file_tree_widget = UnlockingFileTreeWidget()
        file_tree_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)
        file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                  Settings.default_expansion_depth)

        return file_tree_widget

    def create_lock_owner_selection_widget(self):
        lock_owner_selection_widget = QComboBox()
        lock_owner_selection_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)
        lock_owner_selection_widget.setStyleSheet(self.sub_layout_text_size)

        self.populate_lock_owner_selection_widget(lock_owner_selection_widget)

        return lock_owner_selection_widget

    def populate_lock_owner_selection_widget(self, lock_owner_selection_widget):
        lock_owner_selection_widget.clear()
        lock_owner_selection_widget.addItem("All")
        lock_owner_selection_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)

        self_index = 0

        for index, owner in enumerate(LfsLockParser.lock_owners):
            # We want to select the current user by default
            if owner == self.git_user:
                self_index = index

            lock_owner_selection_widget.addItem(owner)

        lock_owner_selection_widget.setCurrentIndex(self_index + 1)
        lock_owner_selection_widget.currentTextChanged.connect(self.on_lock_owner_selection_changed)

    def create_file_tree_widget(self):
        file_tree_widget = UnlockingFileTreeWidget()
        file_tree_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)
        # file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
        #                           Settings.default_expansion_depth)

        return file_tree_widget

    def create_unlock_button_widget(self):
        unlock_button_widget = QPushButton('Unlock', self)
        unlock_button_widget.clicked.connect(self.on_unlocked_pressed)
        # unlock_button_widget.setGeometry(50, 50, 100, 30)  # Set button position and size
        unlock_button_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)
        unlock_button_widget.setStyleSheet(self.sub_layout_text_size)

        return unlock_button_widget

    def on_lock_owner_selection_changed(self, text):
        self.selected_git_user = text
        self.file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                       Settings.default_expansion_depth)

        is_admin = Utility.is_git_user_admin()
        if is_admin or self.selected_git_user == self.git_user:
            self.unlock_button_widget.setEnabled(True)
            QApplication.processEvents()
        else:
            self.unlock_button_widget.setEnabled(False)
            QApplication.processEvents()

    flag = True

    def on_unlocked_pressed(self):
        self.setEnabled(False)
        QApplication.processEvents()

        # Extract lock Ids
        selected_files = self.file_tree_widget.get_selected_file_paths()
        file_list = [str(data) for data in selected_files]

        self.exec_unlocking_operation_on_file_list(file_list)
