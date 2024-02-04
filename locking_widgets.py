"""
This module implements the widgets responsible for displaying the locking and unlocking
application modes.
"""
from abc import abstractmethod

import pyperclip
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QLineEdit, QComboBox, \
    QHBoxLayout, \
    QSizePolicy

import pyqt_helpers
import utility
from file_tree_widgets import LockingFileTreeWidget, UnlockingFileTreeWidget
from lfs_lock_parser import LfsLockParser
from settings import Settings
from worker_thread import WorkerThread


class LockingWidgetBase(QWidget):
    """
    This class implements shared functionality of the locking and unlocking widgets.
    """

    def __init__(self):
        super().__init__()

        # Data we are working with
        self.git_user = utility.get_git_user()  # The current git user
        self.selected_git_user = self.git_user  # The currently selected git user

        self.sub_layout_width = 150
        self.sub_layout_height = 30
        self.sub_layout_text_size = 'font-size: 14px'

        # Subscribe to lock data updates
        LfsLockParser.subscribe_to_update(self)

    def exec_locking_operation_on_file_list(self, file_list: [str]):
        """
        This function initiates a locking operation given a file list.
        :param file_list: The file list to operate on
        """
        dialog = pyqt_helpers.NotificationDialog(f"Locking {len(file_list)} files", 400, 40)
        dialog.run(self.parent())

        worker = WorkerThread(self._exec_locking_operation_on_file_list, file_list, True)
        worker.exec(self._on_finished_locking_operation)

    def exec_unlocking_operation_on_file_list(self, file_list: [str]):
        """
        This function initiates an unlocking operation given a file list.
        :param file_list: The file list to operate on
        """
        dialog = pyqt_helpers.NotificationDialog(f"Unlocking {len(file_list)} files", 400, 40)
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
        git_command = utility.get_git_lfs_path()

        if should_lock:
            git_command += " lock "
        else:
            git_command += " unlock "

        project_root = utility.get_project_root_directory()

        if not should_lock:
            non_owned_files = []
            owned_files = []

            if utility.is_git_user_admin():
                for file in file_list:
                    # We only need to force unlock non-owning file locks
                    file_owner = LfsLockParser.get_lock_owner_of_file(file)
                    if file_owner != utility.get_git_user():
                        print(
                            f"Appending file '{file}' to non-owning files (owner '{file_owner}').")
                        non_owned_files.append(file)
                    else:
                        print(f"Appending file '{file}' to owning files.")
                        owned_files.append(file)

                git_admin_command = git_command + "--force "
                admin_command = git_admin_command.split() + file_list
                print(f"Executing admin command ({len(admin_command)}): {admin_command}")
                utility.run_command(admin_command, project_root)

                # Filter all non-owning files from the file list
                if len(non_owned_files) > 0:
                    file_list.clear()
                    file_list = owned_files

        # Proceed with the remaining locks
        command = git_command.split() + file_list
        print(f"Executing command ({len(command)}): {command}")
        utility.run_command(command, project_root)

        return True

    @abstractmethod
    def on_lock_data_update(self):
        """
        This function gets called by the LFS lock parser once data was parsed and assuming this
        object subscribed to the parser beforehand.
        """

    def _on_tree_selection_changed(self):
        pass

    def _create_tree_filter_widget(self):
        tree_filter_widget = QLineEdit()
        tree_filter_widget.textChanged.connect(self._on_tree_filter_text_changed)
        tree_filter_widget.setPlaceholderText("Search for files and folders ...")

        return tree_filter_widget

    @abstractmethod
    def _on_tree_filter_text_changed(self, text: str):
        self.file_tree_widget.hide_empty_folders()

        should_expand = text != ""
        root_item = self.file_tree_widget.invisibleRootItem()

        self.file_tree_widget.set_expanded_recursively(should_expand, root_item)
        self.file_tree_widget.enforce_default_expansion_depth()

    def _create_apply_selection_from_clipboard_button_widget(self):
        apply_selection_from_clipboard_button_widget = QPushButton('Apply selection from Clipboard',
                                                                   self)
        apply_selection_from_clipboard_button_widget.clicked.connect(
            self._on_apply_selection_from_clipboard_pressed)
        apply_selection_from_clipboard_button_widget.setFixedSize(250, self.sub_layout_height)
        apply_selection_from_clipboard_button_widget.setStyleSheet(self.sub_layout_text_size)

        return apply_selection_from_clipboard_button_widget

    def _on_apply_selection_from_clipboard_pressed(self):
        # @TODO: It does not work in locking mode
        clipboard_string = pyperclip.paste()
        items = clipboard_string.split()
        self.file_tree_widget.set_selected_items(items)

        # @TODO: The number of selected files should be returned from the set_selected_items
        #  function since we might
        #  have unwanted substrings in our clipboard.
        dialog = pyqt_helpers.NotificationDialog(f"Selected {len(items)} items from clipboard",
                                                 500, 40)
        dialog.run(self.parent())


class LockingWidget(LockingWidgetBase):
    """
    This widget is responsible for displaying the application's locking mode.
    """

    def __init__(self):
        super().__init__()

        base_layout = QVBoxLayout()
        base_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout = QHBoxLayout()
        sub_layout.setAlignment(Qt.AlignLeft)
        base_layout.addLayout(sub_layout)

        # Widgets for sub-layout
        self.lock_button_widget = self._create_lock_button_widget()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.apply_selection_from_clipboard_button_widget = (
            self._create_apply_selection_from_clipboard_button_widget())

        sub_layout.addWidget(self.lock_button_widget)
        sub_layout.addWidget(spacer)
        sub_layout.addWidget(self.apply_selection_from_clipboard_button_widget)

        # Widgets for main layout
        self.tree_filter_widget = self._create_tree_filter_widget()
        self.file_tree_widget = self._create_file_tree_widget()

        base_layout.addWidget(self.tree_filter_widget)
        base_layout.addWidget(self.file_tree_widget)

        self.setLayout(base_layout)

    def _on_tree_filter_text_changed(self, text: str):
        self.file_tree_widget.populate(LfsLockParser.lock_data, Settings.default_expansion_depth,
                                       text)

        super()._on_tree_filter_text_changed(text)

    def on_lock_data_update(self):
        print("Locking widget: Lock data was updated. Re-populating tree ...")
        self.file_tree_widget.populate(LfsLockParser.lock_data, Settings.default_expansion_depth)

    def _create_file_tree_widget(self):
        tree_widget = LockingFileTreeWidget()
        tree_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)
        # tree_widget.populate(LfsLockParser.lock_data, Settings.default_expansion_depth)

        return tree_widget

    def _create_lock_button_widget(self):
        lock_button_widget = QPushButton('Lock', self)
        lock_button_widget.clicked.connect(self._on_locked_pressed)
        lock_button_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)
        lock_button_widget.setStyleSheet(self.sub_layout_text_size)

        return lock_button_widget

    def _on_locked_pressed(self):
        self.setEnabled(False)
        QApplication.processEvents()

        # Extract lock Ids
        selected_files = self.file_tree_widget.get_selected_file_paths()
        file_list = [str(data) for data in selected_files]

        self.exec_locking_operation_on_file_list(file_list)


class UnlockingWidget(LockingWidgetBase):
    """
    This widget is responsible for displaying the application's unlocking mode.
    """

    def __init__(self):
        super().__init__()

        base_layout = QVBoxLayout()
        base_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout = QHBoxLayout()
        sub_layout.setAlignment(Qt.AlignLeft)
        base_layout.addLayout(sub_layout)

        # Widgets for sub-layout
        self.unlock_button_widget = self._create_unlock_button_widget()
        self.lock_owner_selection_widget = self._create_lock_owner_selection_widget()
        self.apply_selection_from_clipboard_button_widget = (
            self._create_apply_selection_from_clipboard_button_widget())
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        sub_layout.addWidget(self.unlock_button_widget)
        sub_layout.addWidget(self.lock_owner_selection_widget)
        sub_layout.addWidget(spacer)
        sub_layout.addWidget(self.apply_selection_from_clipboard_button_widget)

        # Widgets for main layout
        self.tree_filter_widget = self._create_tree_filter_widget()
        self.file_tree_widget = self._create_file_tree_widget()

        base_layout.addWidget(self.tree_filter_widget)
        base_layout.addWidget(self.file_tree_widget)

        self.setLayout(base_layout)

    def _on_tree_filter_text_changed(self, text: str):
        self.file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                       Settings.default_expansion_depth, text)

        super()._on_tree_filter_text_changed(text)

    def on_lock_data_update(self):
        print("Unlock widget: Lock data was updated. Re-populating tree ...")
        self.file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                       Settings.default_expansion_depth)

        self._populate_lock_owner_selection_widget(self.lock_owner_selection_widget)

    def _create_lock_owner_selection_widget(self):
        lock_owner_selection_widget = QComboBox()
        lock_owner_selection_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)
        lock_owner_selection_widget.setStyleSheet(self.sub_layout_text_size)

        self._populate_lock_owner_selection_widget(lock_owner_selection_widget)

        return lock_owner_selection_widget

    def _populate_lock_owner_selection_widget(self, lock_owner_selection_widget):
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
        lock_owner_selection_widget.currentTextChanged.connect(
            self._on_lock_owner_selection_changed)

    def _create_file_tree_widget(self):
        file_tree_widget = UnlockingFileTreeWidget()
        file_tree_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)
        # file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
        #                           Settings.default_expansion_depth)

        return file_tree_widget

    def _create_unlock_button_widget(self):
        unlock_button_widget = QPushButton('Unlock', self)
        unlock_button_widget.clicked.connect(self._on_unlocked_pressed)
        # unlock_button_widget.setGeometry(50, 50, 100, 30)  # Set button position and size
        unlock_button_widget.setFixedSize(self.sub_layout_width, self.sub_layout_height)
        unlock_button_widget.setStyleSheet(self.sub_layout_text_size)

        return unlock_button_widget

    def _on_lock_owner_selection_changed(self, text: str):
        self.selected_git_user = text
        self.file_tree_widget.populate(LfsLockParser.lock_data, self.selected_git_user,
                                       Settings.default_expansion_depth)

        is_admin = utility.is_git_user_admin()
        if is_admin or self.selected_git_user == self.git_user:
            self.unlock_button_widget.setEnabled(True)
            QApplication.processEvents()
        else:
            self.unlock_button_widget.setEnabled(False)
            QApplication.processEvents()

    def _on_unlocked_pressed(self):
        self.setEnabled(False)
        QApplication.processEvents()

        # Extract lock Ids
        selected_files = self.file_tree_widget.get_selected_file_paths()
        file_list = [str(data) for data in selected_files]

        self.exec_unlocking_operation_on_file_list(file_list)
