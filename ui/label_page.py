import os
import math
import time
import pickle
import pandas as pd
import numpy as np

from PySide2.QtWidgets import*
from PySide2.QtGui import QPixmap, QIcon
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile, Slot

import matplotlib as mpl
import matplotlib.ticker as ticker
from matplotlib.figure import Figure
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)


class CustomedToolbar(NavigationToolbar):
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar.toolitems if t[0] == 'Pan']

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.canvas = FigureCanvas(Figure(facecolor='white'))
        #self.canvas.margins(0,0,0,0)
        vertical_layout = QVBoxLayout()
        vertical_layout.addWidget(self.canvas)
        #vertical_layout.addWidget(CustomedToolbar(self.canvas, self.canvas))
        self.setLayout(vertical_layout)



class LabelWidget(QWidget):

    def __init__(self, config, dir_, machine_list):
        QWidget.__init__(self)
        self.dir_ = dir_
        self.config = config
        self.machine_list = machine_list
        self.ind = 0
        self.tag_quantile = 0
        self.data = None
        self.lr = -1
        self.lr_list = []
        self.x_list = []
        self.segments = 0
        self.anomaly_length = 0
        self.lines = []
        self.data_button = None
        ui_file = QFile('label_page.ui')
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        loader.registerCustomWidget(PlotWidget)
        self.ui = loader.load(ui_file, self)
        self.setFixedSize(1450, 900)
        self.ui.machine_label.setPixmap(QPixmap('images/machine1.png'))
        ui_file.close()
        self.setWindowTitle('Label Tool')
        machine_layout = QVBoxLayout()
        machine_layout.setSpacing(10)
        button_list = [QPushButton(machine) for machine in machine_list]
        for i, button in enumerate(button_list):
            button.setFixedSize(205, 40)
            if i == 0:
                button.setIcon(QIcon(QPixmap('images/line_blue.png')))
                button.setStyleSheet("QPushButton{background-color:rgb(2,34,63);font-family:'Calibri';font-size:20px;color:rgb(24,144,255);}")
                self.data_button = button
            else:
                button.setIcon(QIcon(QPixmap('images/line.png')))
                button.setStyleSheet("QPushButton{font-family:'Calibri';font-size:20px;color:white;}")
            button.clicked.connect(self.jump)
            machine_layout.addWidget(button)
        machine_layout.addStretch()
        self.ui.scrollAreaWidgetContents.setLayout(machine_layout)
        self.ui.finish_button.clicked.connect(self.finish)

        machine = self.machine_list[self.ind]
        data = self._read_data(machine)
        self.data = data
        self.init_figure(data)
        self.canvas = self.ui.plot_widget.canvas
        CustomedToolbar(self.canvas, self.ui.toolBar_widget)
        self.draw(data, machine)
        self.canvas.mpl_connect('scroll_event', self._zoom)
        self.canvas.mpl_connect('button_press_event', self._zoom)
        self.canvas.mpl_connect('button_press_event', self._label)
        self.ui.timeInterval_button.setText(self.config['time_interval'])
        if self.config['date']:
            start = time.localtime(data['timestamp'][0])
            start = time.strftime("%Y-%m-%d %H:%M:%S", start)
            end = time.localtime(data['timestamp'][len(data['timestamp'])-1])
            end = time.strftime("%Y-%m-%d %H:%M:%S", end)
        else:
            start = '0'
            end = str(data['value'].shape[0] - 1)
        info = 'Start Index: ' + start + '  —  End Index: ' + end
        self.ui.info_label.setText('| '+info)
        self.setWindowIcon(QIcon('images/logo.png'))
        #self.canvas.mpl_connect('key_press_event', self._zoom_score)

    def init_figure(self, data):
        figure = self.ui.plot_widget.canvas.figure
        config = self.config
        kpi_num = data['value'].shape[1]
        if config['noshow_kpi'] is None:
            kpi_list = list(range(kpi_num))
            self.kpi_num = kpi_num
        else:
            kpi_list = [i for i in range(kpi_num) if i not in config['noshow_kpi']]
            self.kpi_num = len(kpi_list)
        value = data['value'][:, kpi_list]
        row_num = value.shape[1]  
        if config['tag']:
            row_num += 3
            # TODO: 更换数据中的score
            tag = data['tag']
        grid = figure.add_gridspec(row_num, 1, left=0.08, bottom=0.04, right=0.99, top=1.0, wspace=0.2, hspace=0.2)
        if config['tag']:
            kpi_plt = figure.add_subplot(grid[:row_num-3, 0])
            tag_plt = figure.add_subplot(grid[row_num-3:row_num, 0], sharex=kpi_plt.axes)
            tag_plt.set_ylabel('tag', size=8)
            tag_plt.tick_params(axis="y", labelsize=5)
            tag_plt.tick_params(axis="x", labelsize=6)
            tag_plt.set_title('tag', fontsize=1)
            self.tag_plt = tag_plt
        else:
            kpi_plt = figure.add_subplot(grid[:row_num, 0])
        # TODO
        #figure.axis('off')
        #figure.text(0, 0, f'dir {self.dir_}', fontdict={'size': 10})
        kpi_plt.set_title('kpi', fontsize=1)
        kpi_plt.tick_params(axis="x", labelsize=6)
        kpi_plt.set_yticks(range(0, len(kpi_list)))
        kpi_plt.grid(linestyle="-.", color='black', linewidth=0.05)
        if config['date']:
            def ts2dt(x, pos):
                time_local = time.localtime(x)
                dt = time.strftime("%Y/%m/%d %H:%M:%S", time_local)
                return dt
            formatter = ticker.FuncFormatter(ts2dt)
            kpi_plt.xaxis.set_major_formatter(formatter)
            kpi_plt.xaxis.set_visible(False)
        #if config['tag']:
        #    tag_plt.set_ylabel('tag', size=8)
        #    tag_plt.tick_params(axis='y', labelsize=5)
        #    tag_plt.set_title('tag', fontsize=1)
        #    self.tag_plt = tag_plt
        kpi_plt.set_title('kpi', fontsize=1)
        self.kpi_plt = kpi_plt
        #plt.subplots_adjust(top=1,bottom=0.5,left=0.5,right=1,hspace=0,wspace=0)
        #plt.margins(0, 0)


    def draw(self, data, machine):
        for line in self.lines:
            line.remove()
        self.lines = []
        config = self.config
        kpi_num = data['value'].shape[1]
        if config['noshow_kpi'] is None:
            kpi_list = list(range(kpi_num))
        else:
            kpi_list = [i for i in range(kpi_num) if i not in config['noshow_kpi']]
        value = data['value'][:, kpi_list]
        row_num = value.shape[1]  
        if config['tag']:
            row_num += 3
            # TODO: 更换数据中的score
            tag = data['tag']
        self.kpi_plt.set_ylabel(machine, size=10)
        if config['date']:
            dates = data['timestamp']
            xs = [int(date) for date in dates]
        else:
            xs = list(range(value.shape[0]))
        for index in range(len(kpi_list)):
            value[:, index] += index
        lines = self.kpi_plt.plot(xs, value, linewidth=1)
        self.lines.extend(lines)
        if config['tag']:
            lines = self.tag_plt.plot(xs, tag, color='blue')
            self.lines.extend(lines)
        self.canvas.draw_idle()

    def _read_data(self, machine):
        config = self.config
        path = config['data_root'] + '/'+self.dir_+'/'+machine+'.'+config['file']
        #path = f"{config['data_root']}/{self.dir_}/{ip}.{config['file']}"
        if not os.path.exists(path):
            raise SystemError('File in \"'+path+'\" does not exist!')
        dict_ = {'timestamp': None, 'value': None, 'tag':None}
        if config['file'] == 'csv':
            df = pd.read_csv(path)
            dict_ = {'timestamp': df['timestamp']}
            #print('timestamp', dict_['timestamp'].shape)
            num = len(df.columns)
            #print('num', num)
            if 'tag' in df.columns:
                dict_['tag'] = df['tag']
                dict_['value'] = df.values[:, 1:num-1]
            else:
                dict_['value'] = df.values[:, 1:num]
            #print('tag', dict_['tag'].shape)
            #print('value', dict_['value'].shape)
        elif config['file'] == 'pkl':
            with open(path, 'rb') as f:
                dict_ = pickle.load(f)
        elif config['file'] == 'npz':
            data = np.load(path)
            dict_ = {}
            for key in data.files:
                dict_[key] = data[key]

        if config['tag'] is False:
            dict_['tag'] = None
        if config['date'] is False:
            dict_['timestamp'] = None
        return dict_

    def _zoom(self, event):
        axtemp = event.inaxes
        x_min, x_max = axtemp.get_xlim()
        scale = (x_max - x_min) / 10
        if event.button == 'up':
            axtemp.set(xlim=(x_min + scale, x_max - scale))
        elif event.button == 'down':
            axtemp.set(xlim=(x_min - scale, x_max + scale))
        self.canvas.draw_idle()

    def _label(self, event):
        machine = self.machine_list[self.ind]
        axtemp = event.inaxes
        if axtemp.get_title() not in ['kpi', 'tag']:
            return
        path = self.config['label_dir']+'/'+self.dir_+'_'+machine+'_label_result.txt'
        if self.config['date']:
            x_data = (event.xdata - self.data['timestamp'][0]) / (self.data['timestamp'][1] - self.data['timestamp'][0])
        else:
            x_data = event.xdata
        x_data = math.ceil(x_data)

        with open(path, 'a') as f:
            f.writelines('%s click: button=%d, x=%f \n' %
                            ('double' if event.dblclick else 'single', event.button, x_data))
            if event.button == 2:
                if event.dblclick:
                    if len(self.x_list) > 1:
                        self.x_list.pop()
                        self.x_list.pop()
                        self.anomaly_length -= 1
                        percent = ('%.2f%%' % (self.anomaly_length/self.data['value'].shape[0]*100))
                        self.ui.percent_button.setText(str(percent))
                        self.draw(self.data, machine)
                elif not event.dblclick:
                    self.x_list.append(x_data)
                    self.anomaly_length += 1
                    percent = ('%.2f%%' % (self.anomaly_length/self.data['value'].shape[0]*100))
                    self.ui.percent_button.setText(str(percent))
            elif event.button == 3:
                if event.dblclick and self.lr > 0:
                    if len(self.lr_list) > 2:
                        self.lr_list.pop()
                        right = self.lr_list.pop()
                        left = self.lr_list.pop()
                        self.segments -= 1
                        self.anomaly_length -= (right - left + 1)
                        percent = ('%.2f%%' % (self.anomaly_length/self.data['value'].shape[0]*100))
                        self.ui.segment_button.setText(str(self.segments))
                        self.ui.percent_button.setText(str(percent))
                        self.lr *= -1
                        self.draw(self.data, machine)
                elif not event.dblclick:
                    self.lr_list.append(x_data)
                    self.lr *= -1
                    if self.lr == -1:
                        self.segments += 1
                        self.anomaly_length += (self.lr_list[-1] - self.lr_list[-2] + 1)
                        percent = ('%.2f%%' % (self.anomaly_length/self.data['value'].shape[0]*100))
                        self.ui.segment_button.setText(str(self.segments))
                        self.ui.percent_button.setText(str(percent))
            axtemp = event.inaxes
            if not self.config['date']:
                self.lines.append(axtemp.vlines(self.x_list, ymin=[0 for _ in range(len(self.x_list))], 
                    ymax=[self.kpi_num for _ in range(len(self.x_list))], colors='r',linestyles='-',linewidth=1))
                self.lines.append(axtemp.vlines(self.lr_list, ymin=[0 for _ in range(len(self.lr_list))], 
                    ymax=[self.kpi_num for _ in range(len(self.lr_list))], colors='r', linestyles='-', linewidth=1))
            else:
                new_x = [self.data['timestamp'][0] + x*(self.data['timestamp'][1] - self.data['timestamp'][0]) for x in self.x_list]
                new_lr = [self.data['timestamp'][0] + lr*(self.data['timestamp'][1] - self.data['timestamp'][0]) for lr in self.lr_list]
                self.lines.append(axtemp.vlines(new_x, ymin=[0 for _ in range(len(new_x))], 
                    ymax=[self.kpi_num for _ in range(len(new_x))], colors='r',linestyles='-',linewidth=1))
                self.lines.append(axtemp.vlines(new_lr, ymin=[0 for _ in range(len(new_lr))], 
                    ymax=[self.kpi_num for _ in range(len(new_lr))], colors='r', linestyles='-', linewidth=1))

    @Slot()
    def jump(self):
        button = self.sender()
        button.setIcon(QIcon(QPixmap('images/line_blue.png')))
        button.setStyleSheet("QPushButton{background-color:rgb(2,34,63);font-family:'Calibri';font-size:20px;color:rgb(24,144,255);}")
        if self.data_button:
            self.data_button.setIcon(QIcon(QPixmap('images/line.png')))
            self.data_button.setStyleSheet("QPushButton{font-family:'Calibri';font-size:20px;color:white;}")
        self.data_button = button
        machine = button.text()
        self.ind = self.machine_list.index(machine)
        self.lr = -1
        self.lr_list = []
        self.x_list = []
        self.segments = 0
        self.anomaly_length = 0       
        self.data = self._read_data(machine)
        self.draw(self.data, machine)
        self.ui.segment_button.setText('0')
        self.ui.percent_button.setText('0.0%') 


    @Slot()
    def finish(self):
        self.lr = -1
        self.lr_list = []
        self.x_list = []
        self.segments = 0
        self.anomaly_length = 0
        machine = self.machine_list[self.ind % len(self.machine_list)]
        path = self.config['label_dir']+'/label_process_'+self.dir_+'.txt'
        with open(path, 'a') as f:
            f.writelines('machine\n')
        self.ind = (self.ind+1) % len(self.machine_list)
        machine = self.machine_list[self.ind]
        self.data = self._read_data(machine)
        self.draw(self.data, machine)
        self.ui.segment_button.setText('0')
        self.ui.percent_button.setText('0.0%')

    '''
    def _zoom_score(self, event):
        print('enter zoom score')
        if self.config['score']:
            quantile = self.tag_quantile
            score = self.data['score']
            allaxes = self.canvas.get_axes()
            score_plt = allaxes[1]
            if event.key == 'w' and quantile < 0.009:
                print('key up')
                quantile += 0.001
                score_plt.set_ylim([np.quantile(score, quantile), np.max(score)])
            elif event.key == 's' and quantile > 0:
                print('key down')
                quantile -= 0.001
                score_plt.set_ylim([np.quantile(score, quantile), np.max(score)])
            self.tag_quantile = quantile
            self.canvas.draw_idle()
    '''
