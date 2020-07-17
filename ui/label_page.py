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

from copy import deepcopy


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

        # init and load ui
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
        self.merge = False
        ui_file = QFile('label_page.ui')
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        loader.registerCustomWidget(PlotWidget)
        self.ui = loader.load(ui_file, self)
        self.setFixedSize(1450, 900)
        self.ui.machine_label.setPixmap(QPixmap('images/machine1.png'))
        ui_file.close()
        self.setWindowTitle('Label Tool')

        # add button to choose machine
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

        # load the data of first machine
        machine = self.machine_list[self.ind]
        data = self._read_data(machine)
        self.data = data
        self.merge_kpi, self.merge_str = self.kpi_2be_merged(self.data)

        # init figure and draw kpi time series of first machine
        self.init_figure(data, self.merge)
        self.canvas = self.ui.plot_widget.canvas
        CustomedToolbar(self.canvas, self.ui.toolBar_widget)
        self.draw(data, self.merge)
        self.canvas.mpl_connect('scroll_event', self._zoom)
        self.canvas.mpl_connect('button_press_event', self._zoom)
        self.canvas.mpl_connect('button_press_event', self._label)

        # set function button and add some information bars
        self.ui.timeInterval_button.setText(self.config['time_interval'])
        self.ui.mergeKPIs_button.setText(self.merge_str+'To\n'+str(self.merge_kpi[-1]))
        if self.config['date']:
            start = time.localtime(data['timestamp'][0])
            start = time.strftime("%Y/%m/%d\n%H:%M:%S", start)
            end = time.localtime(data['timestamp'][len(data['timestamp'])-1])
            end = time.strftime("%Y/%m/%d\n%H:%M:%S", end)
        else:
            start = '0'
            end = str(data['value'].shape[0] - 1)
        info = 'Start Index: ' + start + '  —  End Index: ' + end
        self.ui.info_label.setText('| '+info)
        self.ui.startIndex_button.setText(start)
        self.ui.endIndex_button.setText(end)
        self.ui.finish_button.clicked.connect(self.finish)
        self.ui.merge_button.clicked.connect(self.merge_seperate)
        self.setWindowIcon(QIcon('images/logo.png'))

    def kpi_2be_merged(self, data):
        '''
        Get the indexs of kpis need to be merged
        '''
        value = data['value']
        len_ = value.shape[0]
        threshold = int(len_*0.99)
        merge_kpi = []
        if self.config['noshow_kpi']:
            for i in range(value.shape[1]):
                if i not in self.config['noshow_kpi'] and np.sum(value[:, i] == 0) >= threshold:
                    merge_kpi.append(i)
        else:
            for i in range(value.shape[1]):
                if np.sum(value[:, i] == 0) >= threshold:
                    merge_kpi.append(i)
        merge_str = ""
        for i, kpi in enumerate(merge_kpi):
            if (i+1) % 6 == 0:
                merge_str = merge_str + str(kpi) + '\n'
            else:
                merge_str = merge_str + str(kpi) + ' '
        if len(merge_kpi) % 6 != 0: 
            merge_str += '\n'
        return merge_kpi, merge_str


    def init_figure(self, data, merge=False):
        figure = self.ui.plot_widget.canvas.figure
        config = self.config

        # get the kpi list storing the indexes of kpis which need ploting
        kpi_num = data['value'].shape[1]
        if not config['noshow_kpi']:
            kpi_list = list(range(kpi_num))
            self.kpi_num = kpi_num
        else:
            kpi_list = [i for i in range(kpi_num) if i not in config['noshow_kpi']]
            self.kpi_num = len(kpi_list)

        # init subplot
        row_num = kpi_num
        if config['tag']:
            row_num += 3
            tag = data['tag']
        grid = figure.add_gridspec(row_num, 1, left=0.07, bottom=0.04, right=0.99, top=1.0, wspace=0.2, hspace=0.2)
        if config['tag']:
            kpi_plt = figure.add_subplot(grid[:row_num-3, 0])
            kpi_plt.xaxis.set_visible(False)
            tag_plt = figure.add_subplot(grid[row_num-3:row_num, 0], sharex=kpi_plt.axes)
            tag_plt.set_ylabel('tag', size=8)
            tag_plt.tick_params(axis="y", labelsize=5)
            tag_plt.tick_params(axis="x", labelsize=6)
            tag_plt.set_title('tag', fontsize=1)
            self.tag_plt = tag_plt
        else:
            kpi_plt = figure.add_subplot(grid[:row_num, 0])

        # configure figure
        kpi_plt.set_title('kpi', fontsize=1)
        kpi_plt.tick_params(axis="x", labelsize=6)
        kpi_plt.tick_params(axis="y", labelsize=7)
        kpi_plt.set_yticks(range(0, len(kpi_list)))
        kpi_plt.grid(linestyle="-.", color='black', linewidth=0.05)
        xs = list(range(data['value'].shape[0]))
        if config['date']:
            def ts2dt(x, pos):
                time_local = time.localtime(x)
                dt = time.strftime("%Y/%m/%d %H:%M:%S", time_local)
                return dt
            formatter_x = ticker.FuncFormatter(ts2dt)
            kpi_plt.xaxis.set_major_formatter(formatter_x)
            xs = [int(date) for date in self.data['timestamp']]
        space_x = int(len(xs) * 0.01 * (xs[1] - xs[0]))
        kpi_plt.set_xlim(xs[0]-space_x, xs[-1]+space_x)
        self.kpi_plt = kpi_plt


    def draw(self, data, merge=False):
        
        # clear lines in the figure
        if not merge:
            for line in self.lines:
                line.remove()
        else:
            for line in self.lines:
                if type(line) == mpl.lines.Line2D:
                    line.remove()
        self.lines = []
        config = self.config
        kpi_num = data['value'].shape[1]
        if config['noshow_kpi'] is None:
            kpi_list = list(range(kpi_num))
        else:
            kpi_list = [i for i in range(kpi_num) if i not in config['noshow_kpi']]
        if merge:
            kpi_list = [i for i in kpi_list if i not in self.merge_kpi]

        # plot kpis
        # TODO: modify
        # value = deepcopy(data['value'][:, kpi_list])
        value = data['value'][:, kpi_list]
        if config['tag']:
            tag = data['tag']
        if config['date']:
            dates = data['timestamp']
            xs = [int(date) for date in dates]
        else:
            xs = list(range(value.shape[0]))
        for index in range(len(kpi_list)):
            value[:, index] += index
        lines = self.kpi_plt.plot(xs, value, linewidth=1)
        self.lines.extend(lines)

        # merge kpis
        if merge:
            kpi_list.append(self.merge_kpi[-1])
            for kpi in self.merge_kpi:
                # TODO: modify
                merge_value = deepcopy(data['value'][:, kpi]).T
                #merge_value = data['value'][:, kpi].T
                merge_value += (len(kpi_list) - 1)
                self.lines.extend(self.kpi_plt.plot(xs, merge_value, linewidth=1))

        # plot tag
        if config['tag']:
            lines = self.tag_plt.plot(xs, tag, color='blue')
            self.lines.extend(lines)

        # configure figure
        self.kpi_plt.set_ylim(-1, len(kpi_list))
        self.kpi_plt.set_yticks(range(0, len(kpi_list)))
        def seq2index(y, pos):
            if y < len(kpi_list):
                return kpi_list[math.floor(y)]
            else:
                return y
        formatter_y = ticker.FuncFormatter(seq2index)
        self.kpi_plt.yaxis.set_major_formatter(formatter_y)
        self.canvas.draw_idle()

    def _read_data(self, machine):
        config = self.config
        path = config['data_root'] + '/'+self.dir_+'/'+machine+'.'+config['file']
        if not os.path.exists(path):
            raise SystemError('File in \"'+path+'\" does not exist!')
        dict_ = {'timestamp': None, 'value': None, 'tag':None}
        if config['file'] == 'csv':
            df = pd.read_csv(path)
            dict_ = {'timestamp': df['timestamp']}
            num = len(df.columns)
            if 'tag' in df.columns:
                dict_['tag'] = df['tag']
                dict_['value'] = df.values[:, 1:num-1]
            else:
                dict_['value'] = df.values[:, 1:num]
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
                        self.draw(self.data, self.merge)
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
                        self.draw(self.data, self.merge)
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
        self.merge_kpi, self.merge_str = self.kpi_2be_merged(self.data)
        self.ui.merge_label.setText('Merge KPIs')
        self.ui.mergeKPIs_button.setText(self.merge_str+'To\n'+str(self.merge_kpi[-1]))
        self.ui.merge_button.setText('Merge')
        self.merge = False
        self.draw(self.data, self.merge)
        self.ui.segment_button.setText('0')
        self.ui.percent_button.setText('0.0%')

    @Slot()
    def merge_seperate(self):
        button = self.sender()
        if button.text() == 'Merge':
            button.setText('Seperate')
            self.merge = True
            self.ui.merge_label.setText('Seperate KPIs')
            self.ui.mergeKPIs_button.setText(str(self.merge_kpi[-1])+'\nTo\n'+self.merge_str)
            self.draw(self.data, self.merge)

        else:
            button.setText('Merge')
            self.merge = False
            self.ui.merge_label.setText('Merge KPIs')
            self.ui.mergeKPIs_button.setText(self.merge_str+'To\n'+str(self.merge_kpi[-1]))
            self.draw(self.data, self.merge)

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
        self.merge_kpi, self.merge_str = self.kpi_2be_merged(self.data)
        self.ui.merge_label.setText('Merge KPIs')
        self.ui.mergeKPIs_button.setText(self.merge_str+'To\n'+str(self.merge_kpi[-1]))
        self.ui.merge_button.setText('Merge')
        self.merge = False
        self.draw(self.data, self.merge)
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
