from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel


class NotificationDialog(QDialog):
    def __init__(self, message, width, height):
        super(NotificationDialog, self).__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(width, height)
        self.setStyleSheet('background-color: #333333; color: white; font-size: 16px; border-radius: 10px;')

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
        # Calculate the position relative to the application window
        parent_window = self.parent()
        if parent_window:
            parent_geometry = parent_window.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + parent_geometry.height() - self.height() - 10
            self.move(x, y)

        super(NotificationDialog, self).showEvent(event)

    def run(self, parent):
        self.setParent(parent)
        self.exec_()
