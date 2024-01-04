from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel


class LabelDialog(QDialog):
    def __init__(self, parent, text, width, height):
        super().__init__(parent)

        self.setWindowTitle("About")
        self.setGeometry(0, 0, width, height)

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        label = QLabel(self)
        label.setText(text)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)

        layout.addWidget(label)

        self.center()

    def center(self):
        app_center_point = self.parent().geometry().center()
        self.move(app_center_point - self.rect().center())
