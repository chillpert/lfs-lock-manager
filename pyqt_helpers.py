""" This module implements a wrapper for conveniently displaying QDialogs. """
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget


def display_message_window(parent_widget: QWidget, message: str, width: int, height: int,
                           window_title="About"):
    """
    Function to display a simple window with text
    :param parent_widget: The widget the new window will be relative to
    :param message: The message the new windows will display
    :param width: The width of the new window
    :param height: The height of the new window
    :param window_title: The title of the new window
    """
    dialog = QDialog(parent_widget)

    dialog.setWindowTitle(window_title)
    dialog.setGeometry(0, 0, width, height)

    layout = QVBoxLayout()
    dialog.setLayout(layout)
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    label = QLabel(dialog)
    label.setText(message)
    label.setOpenExternalLinks(True)
    label.setTextInteractionFlags(Qt.TextBrowserInteraction)

    layout.addWidget(label)

    app_center_point = dialog.parent().geometry().center()
    dialog.move(app_center_point - dialog.rect().center())

    dialog.exec_()


class OverlayWidget(QWidget):
    """
    This widget wrapper displays a maximized blank widget with a centered message.
    """

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

    def set_label(self, message: str):
        """
        This function can be used to set this widgets label.
        :param message: The desired label message
        """
        self.label.setText(message)


class NotificationDialog(QDialog):
    """
    A helper class for easily displaying notifications which automatically disappear after a few
    seconds.
    """

    def __init__(self, message: str, width: int, height: int):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(width, height)
        self.setStyleSheet(
            'background-color: #333333; color: white; font-size: 16px; border-radius: 10px;')

        layout = QVBoxLayout(self)
        self.label = QLabel(message, self)
        layout.setAlignment(Qt.AlignBottom | Qt.AlignCenter)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(3000)  # Close after 3000 milliseconds (3 seconds)

    def showEvent(self, event):
        # pylint: disable=invalid-name
        """
        This function modifies the window's location to be in the bottom center relative to the
        provided parent widget.
        :param event:
        """
        # Calculate the position relative to the application window
        parent_window = self.parent()
        if parent_window:
            parent_geometry = parent_window.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + parent_geometry.height() - self.height() - 10
            self.move(x, y)

        super().showEvent(event)

    def run(self, parent: QWidget):
        """
        This function is used to display the window.
        :param parent: The parent widget this window will be relative to.
        """
        self.setParent(parent)
        self.exec_()
