from PySide2.QtWidgets import*
from PySide2.QtGui import QPixmap, QIcon
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile, Slot

class MsgBox(QWidget):
    def __init__(self, msg):
        QWidget.__init__(self)
        ui_file = QFile('msg_box.ui')
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.ui = loader.load(ui_file, self)
        self.setFixedSize(400, 300)
        ui_file.close()
        self.ui.msg_label.setText(msg)
        self.ui.exclamation_label.setPixmap(QPixmap('images/exclamation_red.png'))
        self.setWindowTitle('msg')
        self.setWindowIcon(QIcon('images/logo.png'))
        self.ui.close_button.clicked.connect(self.close_widget)

    @Slot()
    def close_widget(self):
        self.close()
