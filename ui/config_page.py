import os

from PySide2.QtWidgets import*
from PySide2.QtGui import QPixmap, QIcon
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile, Slot

from label_page import LabelWidget
from msg_box import MsgBox


class ConfigWidget(QWidget):

    def __init__(self):
        self.config = {'file': None, 'tag': False, 'date': False,
                       'noshow_kpi': None, 'data_root': '../data',
                       'label_dir': '../label', 'time_interval': None}
        self.dir_button = None
        QWidget.__init__(self)

        ui_file = QFile("configure_page.ui")
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.ui = loader.load(ui_file, self)
        ui_file.close()
        self.setFixedSize(1270, 800)
        self.setWindowTitle("Label Tool")
        self.setWindowIcon(QIcon('images/logo.png'))
        self.ui.data_label.setPixmap(QPixmap('images/data1.png'))
        #self.ui.fileType_comboBox.setStyleSheet("QComboBox::drop-down {width: 30px;}")
        self.ui.fileType_comboBox.setStyleSheet("QComboBox {border:2px groove gray; border-radius:3px; }"
        "QComboBox::down-arrow {image: url(./images/arrow_black.png);}"
        "QComboBox::drop-down {width: 30px;}")
        #self.ui.fileType_comboBox.setStyleSheet("QComboBox::down-arrow {image: url(./images/arrow.png);}")
        
        all_machine = self.read_dir()
        self.all_machine = all_machine
        set_layout = QVBoxLayout()
        set_layout.setSpacing(10)
        button_list = [QPushButton(set_) for set_ in all_machine]
        icon = QIcon(QPixmap('images/folder.png'))
        for button in button_list:
            button.setFixedSize(205, 40)
            button.setIcon(icon)
            button.setStyleSheet("QPushButton{font-family:'Calibri';font-size:20px;color:white;}")
            button.clicked.connect(self.choose_set)
            set_layout.addWidget(button)
        set_layout.addStretch()
        self.ui.scrollAreaWidgetContents.setLayout(set_layout)
        self.ui.remove_lineEdit.setPlaceholderText('Please enter the KPIs to be removed separated by commas. e.g. 1,3,5')
        self.ui.start_button.clicked.connect(self.plot_figure)

    @Slot()
    def choose_set(self):
        button = self.sender()
        button.setIcon(QIcon(QPixmap('images/folder_blue.png')))
        button.setStyleSheet("QPushButton{background-color:rgb(2,34,63);font-family:'Calibri';font-size:20px;color:rgb(24,144,255);}")        
        if self.dir_button:
            self.dir_button.setIcon(QIcon(QPixmap('images/folder.png')))
            self.dir_button.setStyleSheet("QPushButton{font-family:'Calibri';font-size:20px;color:white;}")
        self.dir_button = button

    @Slot()
    def plot_figure(self):
        self.config['file'] = self.ui.fileType_comboBox.currentText()
        self.config['time_interval'] = self.ui.timeInterval_lineEdit.text()
        self.config['date'] = self.ui.dateTime_button.isChecked()
        self.config['tag'] = self.ui.display_button.isChecked()
        noshow_kpi = self.ui.remove_lineEdit.text()
        if not self.check_config():
            return
        dir_ = self.dir_button.text()
        machine_list = self.all_machine[dir_]
        self.label_widget = LabelWidget(self.config, dir_, machine_list)
        self.label_widget.show()

    def check_config(self):
        if not self.dir_button:
            self.msg_box = MsgBox('Please select the directory where the data you want to label is stored')
            self.msg_box.show()
            return False
        dir_ = self.dir_button.text()
        files = os.listdir(os.path.join(self.config['data_root'], dir_))
        types = [f.split('.')[1] for f in files if not f.startswith('.')]
        types = list(set(types))
        if len(types) != 1 or types[0] != self.config['file']:
            self.msg_box = MsgBox('The file type of data does not match the selected one')
            self.msg_box.show()
            return False
        if not self.ui.timeInterval_lineEdit.text().strip():
            self.msg_box = MsgBox('Please enter the time interval of your data')
            self.msg_box.show()
            return False
        if (not self.ui.dateTime_button.isChecked()) and (not self.ui.sequence_button.isChecked()):
            self.msg_box = MsgBox('Please select the unit of X-Axis')
            self.msg_box.show()
            return False
        if (not self.ui.display_button.isChecked()) and (not self.ui.notDisplay_button.isChecked()):
            self.msg_box = MsgBox('Please select whether to display tag or not')
            self.msg_box.show()
            return False
        noshow_kpi = self.ui.remove_lineEdit.text()
        if noshow_kpi:
            try:
                self.config['noshow_kpi'] = [int(kpi) for kpi in noshow_kpi.split(',')]  
            except:
                self.msg_box = MsgBox('The format of the KPIs you entered is incorrect')
                self.msg_box.show()
                return False
        return True

    def read_dir(self):
        all_machine = {}
        root = self.config['data_root']
        dir_list = os.listdir(root)
        for dir_ in dir_list:
            ip_files = os.listdir(os.path.join(root, dir_))
            if ip_files:
                all_machine[dir_] = [f.split('.')[0] for f in ip_files if not f.startswith('.')]
        return all_machine

if __name__ == '__main__':
    app = QApplication([])
    window = ConfigWidget()
    window.show()
    app.exec_()
