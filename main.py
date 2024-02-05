"""
The LFS lock manager is an application which can be used to manage locking and unlocking of files
using a graphical user interface. It has built-in features which simplify transferring file lock
ownerships from one person to another.
"""
import os
import sys
from enum import Enum

import darkdetect
import qdarktheme
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPalette, QColor, QFontDatabase, QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, \
    QComboBox, QStackedWidget, QToolBar, QAction, QToolButton, QSizePolicy, QLabel
from PyQt5.QtWidgets import QMenu

import pyqt_helpers
import settings
import utility
from lfs_lock_parser import LfsLockParser
from locking_widgets import UnlockingWidget, LockingWidget
from settings import Settings


class ApplicationMode(Enum):
    """ All modes which the application supports """
    UNLOCK = 0
    LOCK = 1

    def __str__(self):
        return self.name.lower().capitalize() + " Mode"


class LfsLockManagerWindow(QMainWindow):
    # pylint: disable=too-many-instance-attributes
    """
    The application's main window.
    """

    def __init__(self):
        super().__init__()

        # Set up main window properties
        self.setWindowTitle("LFS Lock Manager")
        self.setGeometry(100, 100, 1200, 800)

        # Set window icon
        icon = QIcon(utility.resource_path("resources/icons/lock.ico"))
        self.setWindowIcon(icon)

        # Set initial theme
        self.is_dark_theme = darkdetect.isDark()
        if self.is_dark_theme:
            self._set_dark_theme()
        else:
            self._set_light_theme()

        # Flag for tracking if this window ever received data from the LfsLockParser
        self.has_lock_data = False

        # Create a central widget and a layout
        central_widget = QWidget(self)
        self.layout = QVBoxLayout()
        central_widget.setLayout(self.layout)
        self.setCentralWidget(central_widget)

        # Create widget for picking application mode
        self.application_mode_widget = self._create_application_mode_widget()

        # Create a toolbar
        self.tool_bar_widget = self._create_tool_bar_widget()
        self.addToolBar(self.tool_bar_widget)

        # Create stacked widget for each application mode
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        # Add each application mode to the stacked widget
        self.overlay_widget = pyqt_helpers.OverlayWidget()
        self.locking_widget = LockingWidget()
        self.unlocking_widget = UnlockingWidget()

        # Cache the project root directory
        root_directory = utility.get_project_root_directory()

        # Set initial message when launching the application
        success_text = "Loading LFS data of " + os.path.basename(root_directory[:-1]) + " ..."
        label_text = success_text

        # Possible errors
        if not utility.is_project_root_directory_valid():
            label_text = "Invalid root directory. Please modify 'settings.ini' accordingly."
        elif not utility.is_git_installed():
            label_text = ("Your system does not have Git installed. Please install Git and try "
                          "again.")
        elif not utility.is_git_lfs_installed():
            label_text = ("Your system does not have Git LFS installed. Please install Git LFS and"
                          " try again.")
        elif not utility.is_git_config_set():
            label_text = (
                "Your Git config has not been set properly. Please set 'git config user.name' and "
                "'git "
                "config user.email' and try again.")
        else:
            # Trigger async LFS lock parsing only if we made it through all checks
            LfsLockParser.subscribe_to_update(self)
            LfsLockParser.parse_locks_async()

        # Apply initial message to label
        self.overlay_widget.set_label(label_text)

        # Add widgets for each application mode to stacked widget
        self.stacked_widget.addWidget(self.locking_widget)
        self.stacked_widget.addWidget(self.unlocking_widget)
        self.stacked_widget.addWidget(self.overlay_widget)

        # Enter overlay widget by default (to display something while waiting for the LFS data to
        # be parsed)
        self.stacked_widget.setCurrentWidget(self.overlay_widget)

    def _create_application_mode_widget(self):
        # Create combo box widget
        application_mode_widget = QComboBox()

        # Add one item for each application mode
        application_mode_widget.addItem(str(ApplicationMode.UNLOCK))
        application_mode_widget.addItem(str(ApplicationMode.LOCK))

        # Set the current index of the combo box
        application_mode_widget.setCurrentIndex(0)
        application_mode_widget.currentIndexChanged.connect(self._on_application_mode_changed)

        return application_mode_widget

    def _create_tool_bar_widget(self):
        # Create toolbar widget
        tool_bar_widget = QToolBar()
        tool_bar_widget.setFloatable(False)
        tool_bar_widget.setMovable(False)

        # Disable the toolbar widget by default
        tool_bar_widget.setEnabled(False)

        branch_name_widget = QLabel(utility.get_git_branch().strip())
        branch_name_widget.setAlignment(Qt.AlignCenter)
        branch_name_widget.setWindowFlags(Qt.FramelessWindowHint)
        branch_name_widget.setAttribute(Qt.WA_TranslucentBackground)

        # Create a spacer for keeping all other buttons on the far right
        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left_spacer.setWindowFlags(Qt.FramelessWindowHint)
        left_spacer.setAttribute(Qt.WA_TranslucentBackground)

        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_spacer.setWindowFlags(Qt.FramelessWindowHint)
        right_spacer.setAttribute(Qt.WA_TranslucentBackground)

        # Create a button to manually trigger the LfsLockParser
        refresh_icon = QIcon(utility.resource_path("resources/icons/reload.png"))
        refresh_locks_action = QAction("", self)
        refresh_locks_action.setIcon(refresh_icon)
        refresh_locks_action.triggered.connect(self._on_refresh_locks_pressed)
        refresh_locks_action.setToolTip("Refresh LFS data")

        # Create a help menu
        help_menu = QMenu(self)
        help_menu.setTitle("Help")

        # Create actions for help menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about_dialog)
        tutorial_action = QAction("Tutorial", self)
        tutorial_action.triggered.connect(self._show_tutorial_dialog)

        # Add actions to the help menu
        help_menu.addAction(about_action)
        help_menu.addAction(tutorial_action)

        # Add a button for displaying the help menu
        help_button = QToolButton()
        help_button.setMenu(help_menu)
        help_button.setPopupMode(QToolButton.InstantPopup)
        help_button.setText("Help")

        # Add button for toggling the theme
        toggle_theme_action = QAction("", self)
        icon = QIcon(utility.resource_path("resources/icons/theme_toggle.png"))
        toggle_theme_action.setIcon(icon)
        toggle_theme_action.setToolTip("Toggle between dark and light theme")
        toggle_theme_action.triggered.connect(self._on_toggle_theme)

        # Populate toolbar
        tool_bar_widget.addWidget(self.application_mode_widget)
        tool_bar_widget.addWidget(left_spacer)
        tool_bar_widget.addWidget(branch_name_widget)
        tool_bar_widget.addWidget(right_spacer)
        tool_bar_widget.addAction(refresh_locks_action)
        tool_bar_widget.addWidget(help_button)
        tool_bar_widget.addAction(toggle_theme_action)

        return tool_bar_widget

    def _on_refresh_locks_pressed(self):
        self.setEnabled(False)
        LfsLockParser.parse_locks_async()

    def _on_toggle_theme(self):
        if self.is_dark_theme:
            self._set_light_theme()
        else:
            self._set_dark_theme()

    def _set_light_theme(self):
        new_stylesheet = qdarktheme.load_stylesheet("light")
        new_palette = qdarktheme.load_palette("light")

        self.setStyleSheet(new_stylesheet)
        self.setPalette(new_palette)

        self.is_dark_theme = False

    def _set_dark_theme(self):
        new_stylesheet = qdarktheme.load_stylesheet("dark")
        new_palette = qdarktheme.load_palette("dark")
        new_palette.setColor(QPalette.Link,
                             QColor(29, 212, 250))  # Fix for hyperlinks in dark theme

        self.setStyleSheet(new_stylesheet)
        self.setPalette(new_palette)

        self.is_dark_theme = True

    def _show_tutorial_dialog(self):
        pyqt_helpers.display_message_window(self, "A tutorial will be added later.", 300, 20)

    def _show_about_dialog(self):
        message = 'This application was developed for a video game called Marmortal.<br>' \
                  'If you like to play, please visit ' \
                  '<a href="https://www.marmortal.com">https://www.marmortal.com</a>.<br><br' \
                  '>Thank you for using this app.<br>Please report bugs on ' \
                  '<a href="https://github.com/chillpert/lfs-lock-manager">GitHub</a>.'
        pyqt_helpers.display_message_window(self, message, 300, 100)

    def _on_application_mode_changed(self, mode: int):
        app_mode = ApplicationMode(mode)
        self._change_application_mode(app_mode)

    def _change_application_mode(self, mode: ApplicationMode):
        if self.has_lock_data and utility.is_project_root_directory_valid():
            if mode == ApplicationMode.UNLOCK:
                self.stacked_widget.setCurrentWidget(self.unlocking_widget)
            elif mode == ApplicationMode.LOCK:
                self.stacked_widget.setCurrentWidget(self.locking_widget)

        value = mode.value
        self.application_mode_widget.setCurrentIndex(value)

    def on_lock_data_update(self):
        """
        This function gets called by the LFS lock parser once data was parsed and assuming this
        object subscribed to the parser beforehand.
        """
        print("LfsLockManagerWindow: Lock data was updated.")

        self.setEnabled(True)
        self.tool_bar_widget.setEnabled(True)
        self.locking_widget.setEnabled(True)
        self.unlocking_widget.setEnabled(True)
        QApplication.processEvents()

        # Make sure this only applies on application start
        if not self.has_lock_data:
            self.has_lock_data = True

            default_mode = Settings.default_mode
            mode = ApplicationMode[default_mode.upper()]
            self._change_application_mode(mode)


if __name__ == "__main__":
    settings.load_settings()

    print(f"Project root dir: '{utility.get_project_root_directory()}'")

    # Create the application instance
    lockManager = QApplication(sys.argv)

    # Load the fonts
    font_id = QFontDatabase.addApplicationFont(
        utility.resource_path("resources/fonts/M+1NerdFont-Medium.ttf"))

    # Check if the fonts were loaded successfully
    if font_id != -1:
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            # Set the fonts as the default application fonts
            default_font = QFont(font_families[0])
            default_font.setPointSize(10)
            lockManager.setFont(default_font)

    # Create the main window
    window = LfsLockManagerWindow()

    # Show the main window
    window.show()

    # Run the event loop
    sys.exit(lockManager.exec_())
