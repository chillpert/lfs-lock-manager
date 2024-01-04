import darkdetect
import qdarktheme
from PyQt5.QtGui import QPalette, QColor, QFontDatabase, QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, \
    QComboBox, QStackedWidget, QLabel, QToolBar, QAction, QToolButton, QSizePolicy

import custom_dialogs
from file_tree_widgets import *
from lfs_lock_parser import LfsLockParser
from locking_widgets import UnlockingWidget, LockingWidget
from utility import *


class ApplicationMode(Enum):
    Unlock = 0
    Lock = 1

    def __str__(self):
        return self.name + " Mode"


class LfsLockManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set up main window properties
        self.setWindowTitle("LFS Lock Manager")
        self.setGeometry(100, 100, 1200, 800)

        # Set window icon
        icon = QIcon(Utility.resource_path("resources/icons/lock.ico"))
        self.setWindowIcon(icon)

        # Set initial theme
        self.is_dark_theme = darkdetect.isDark()
        if self.is_dark_theme:
            self.set_dark_theme()
        else:
            self.set_light_theme()

        # Flag for tracking if this window ever received data from the LfsLockParser
        self.has_lock_data = False

        # Create a central widget and a layout
        central_widget = QWidget(self)
        self.layout = QVBoxLayout()
        central_widget.setLayout(self.layout)
        self.setCentralWidget(central_widget)

        # Create widget for picking application mode
        self.application_mode_widget = self.create_application_mode_widget()

        # Create a toolbar
        self.tool_bar_widget = self.create_tool_bar_widget()
        self.addToolBar(self.tool_bar_widget)

        # Create stacked widget for each application mode
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        # Add each application mode to the stacked widget
        self.overlay_widget = OverlayWidget()
        self.locking_widget = LockingWidget()
        self.unlocking_widget = UnlockingWidget()

        # Cache the project root directory
        root_directory = Utility.get_project_root_directory()

        # Set initial message when launching the application
        success_text = "Loading LFS data of " + os.path.basename(root_directory[:-1]) + " ..."
        label_text = success_text

        # Possible errors
        if not Utility.is_project_root_directory_valid():
            label_text = "Invalid root directory. Please modify 'settings.ini' accordingly."
        elif not Utility.is_git_installed():
            label_text = "Your system does not have Git installed. Please install Git and try again."
        elif not Utility.is_git_lfs_installed():
            label_text = "Your system does not have Git LFS installed. Please install Git LFS and try again."
        elif not Utility.is_git_config_set():
            label_text = ("Your Git config has not been set properly. Please set 'git config user.name' and 'git "
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

        # Enter overlay widget by default (to display something while waiting for the LFS data to be parsed)
        self.stacked_widget.setCurrentWidget(self.overlay_widget)

    def create_application_mode_widget(self):
        # Create combo box widget
        application_mode_widget = QComboBox()

        # Add one item for each application mode
        application_mode_widget.addItem(str(ApplicationMode.Unlock))
        application_mode_widget.addItem(str(ApplicationMode.Lock))

        # Set the current index of the combo box
        application_mode_widget.setCurrentIndex(0)
        application_mode_widget.currentIndexChanged.connect(self.on_application_mode_changed)

        return application_mode_widget

    def create_tool_bar_widget(self):
        # Create toolbar widget
        tool_bar_widget = QToolBar()
        tool_bar_widget.setFloatable(False)
        tool_bar_widget.setMovable(False)

        # Disable the toolbar widget by default
        tool_bar_widget.setEnabled(False)

        # Create a spacer for keeping all other buttons on the far right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Create a button to manually trigger the LfsLockParser
        refresh_icon = QIcon(Utility.resource_path("resources/icons/reload.png"))
        refresh_locks_action = QAction("", self)
        refresh_locks_action.setIcon(refresh_icon)
        refresh_locks_action.triggered.connect(self.on_refresh_locks_pressed)
        refresh_locks_action.setToolTip("Refresh LFS data")

        # Create a help menu
        help_menu = QMenu(self)
        help_menu.setTitle("Help")

        # Create actions for help menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        tutorial_action = QAction("Tutorial", self)
        tutorial_action.triggered.connect(self.show_tutorial_dialog)

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
        icon = QIcon(Utility.resource_path("resources/icons/theme_toggle.png"))
        toggle_theme_action.setIcon(icon)
        toggle_theme_action.setToolTip("Toggle between dark and light theme")
        toggle_theme_action.triggered.connect(self.on_toggle_theme)

        # Populate toolbar
        tool_bar_widget.addWidget(self.application_mode_widget)
        tool_bar_widget.addWidget(spacer)
        tool_bar_widget.addAction(refresh_locks_action)
        tool_bar_widget.addWidget(help_button)
        tool_bar_widget.addAction(toggle_theme_action)

        return tool_bar_widget

    def on_refresh_locks_pressed(self):
        self.setEnabled(False)
        LfsLockParser.parse_locks_async()

    def on_toggle_theme(self):
        if self.is_dark_theme:
            self.set_light_theme()
        else:
            self.set_dark_theme()

    def set_light_theme(self):
        new_stylesheet = qdarktheme.load_stylesheet("light")
        new_palette = qdarktheme.load_palette("light")

        self.setStyleSheet(new_stylesheet)
        self.setPalette(new_palette)

        self.is_dark_theme = False

    def set_dark_theme(self):
        new_stylesheet = qdarktheme.load_stylesheet("dark")
        new_palette = qdarktheme.load_palette("dark")
        new_palette.setColor(QPalette.Link, QColor(29, 212, 250))  # Fix for hyperlinks in dark theme

        self.setStyleSheet(new_stylesheet)
        self.setPalette(new_palette)

        self.is_dark_theme = True

    def show_tutorial_dialog(self):
        dialog = custom_dialogs.LabelDialog(self, "A tutorial will be added later.", 300, 20)
        dialog.exec_()
        pass

    def show_about_dialog(self):
        dialog = custom_dialogs.LabelDialog(self,
                                            'This application was developed for a video game called Marmortal.<br>If '
                                            'you like to'
                                            'play, please visit <a '
                                            'href="https://www.marmortal.com">https://www.marmortal.com</a>.<br><br'
                                            '>Thank you for'
                                            'using this app.<br>Please report bugs on GitHub.', 300, 100)
        dialog.exec_()

    def on_application_mode_changed(self, mode):
        self.change_application_mode(mode)

    def change_application_mode(self, mode):
        if self.has_lock_data and Utility.is_project_root_directory_valid():
            if mode == ApplicationMode.Unlock.value:
                self.stacked_widget.setCurrentWidget(self.unlocking_widget)
            elif mode == ApplicationMode.Lock.value:
                self.stacked_widget.setCurrentWidget(self.locking_widget)

        self.application_mode_widget.setCurrentIndex(mode)

    def on_lock_data_update(self):
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
            mode = ApplicationMode[default_mode]
            self.change_application_mode(mode.value)


class OverlayWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        # Create a QLabel widget
        self.label = QLabel()

        # Set the alignment of the text within the QLabel
        self.label.setAlignment(Qt.AlignCenter)

        # Add the QLabel to the layout
        layout.addWidget(self.label)
        self.setLayout(layout)

    def set_label(self, text):
        self.label.setText(text)


if __name__ == "__main__":
    Settings.load_from_file("settings.ini")

    print("Project root dir: '%s'" % Utility.get_project_root_directory())

    # Create the application instance
    lockManager = QApplication(sys.argv)

    # Load the fonts
    font_id = QFontDatabase.addApplicationFont(Utility.resource_path("resources/fonts/M+1NerdFont-Medium.ttf"))

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
