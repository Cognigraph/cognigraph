from typing import List
from PyQt5 import QtCore, QtWidgets
from ..pipeline import Pipeline
from .controls import Controls
from .screen_recorder import ScreenRecorder
from portal.portal_server import PortalServer

import threading
import time

import logging
logger = logging.getLogger(name=__name__)


class GUIWindow(QtWidgets.QMainWindow):
    def __init__(self, pipeline=Pipeline()):
        super().__init__()
        self._pipeline = pipeline  # type: Pipeline
        self._controls = Controls(pipeline=self._pipeline)
        self._controls_widget = self._controls.widget

        # Start button
        self.run_button = QtWidgets.QPushButton("Start")
        self.run_button.clicked.connect(self._toggle_run_button)

        # Record gif button and recorder
        self._gif_recorder = ScreenRecorder()
        self.gif_button = QtWidgets.QPushButton("Record gif")
        self.gif_button.clicked.connect(self._toggle_gif_button)

        # Portal button
        self.portal_button = QtWidgets.QPushButton('Activate Portal')
        self.portal_button.clicked.connect(self._toggle_portal_button)
        self.portal_run_button = QtWidgets.QPushButton('Run Portal')
        self.portal_run_button.clicked.connect(self._toggle_run_portal_button)
        self.portal_run_button.setEnabled(False)
        self.portal_subject = None

        # Resize screen
        self.resize(QtCore.QSize(
            QtWidgets.QDesktopWidget().availableGeometry().width() * 0.9,
            QtWidgets.QDesktopWidget().availableGeometry().height() * 0.9))

        # Portal server
        self.portal_server = PortalServer(('localhost', 8007))
        self._FINISH_THREADS = False

    def init_ui(self):
        self._controls.initialize()

        central_widget = QtWidgets.QSplitter()
        self.setCentralWidget(central_widget)

        # Build the controls portion of the window
        controls_layout = QtWidgets.QVBoxLayout()
        controls_layout.addWidget(self._controls_widget)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.run_button)
        buttons_layout.addWidget(self.gif_button)

        portal_layout = QtWidgets.QHBoxLayout()
        portal_layout.addWidget(self.portal_button)
        portal_layout.addWidget(self.portal_run_button)

        controls_layout.addLayout(buttons_layout)
        controls_layout.addLayout(portal_layout)

        self._controls_widget.setMinimumWidth(400)

        # Add control portion to the main widget
        controls_layout_wrapper = QtWidgets.QWidget()
        controls_layout_wrapper.setLayout(controls_layout)
        self.centralWidget().addWidget(controls_layout_wrapper)

    def initialize(self):
        logger.debug('Initializing all nodes')
        self._pipeline.initialize_all_nodes()
        for node_widget in self._node_widgets:
            if node_widget:
                # node_widget.setMinimumWidth(600)

                # insert widget at before-the-end pos (just before controls widget)
                self.centralWidget().insertWidget(self.centralWidget().count() - 1,
                                                  node_widget)
                self.centralWidget().insertWidget(
                    self.centralWidget().count() - 1, node_widget)
            else:
                raise ValueError('Node widget is not defined')

    def moveEvent(self, event):
        self._reset_gif_sector()
        return super(GUIWindow, self).moveEvent(event)

    def _reset_gif_sector(self):
        widgetRect = self.centralWidget().widget(0).geometry()
        widgetRect.moveTopLeft(
            self.centralWidget().mapToGlobal(widgetRect.topLeft()))
        self._gif_recorder.sector = (widgetRect.left(), widgetRect.top(),
                                     widgetRect.right(), widgetRect.bottom())

    def _toggle_run_button(self):
        if self.run_button.text() == "Pause":
            self.run_button.setText("Start")
        else:
            self.run_button.setText("Pause")

    def _toggle_gif_button(self):
        if self.gif_button.text() == "Stop recording":
            self.gif_button.setText("Record gif")

            self._gif_recorder.stop()
            save_path = QtWidgets.QFileDialog.getSaveFileName(
                caption="Save the recording", filter="Gif image (*.gif)")[0]
            self._gif_recorder.save(save_path)
        else:
            self._reset_gif_sector()
            self.gif_button.setText("Stop recording")
            self._gif_recorder.start()

    def closeEvent(self, event):
        self.portal_server.stop()
        self._FINISH_THREADS = True
        time.sleep(1)
        # print([x.getName() for x in threading.enumerate()])
        event.accept()

    def _toggle_portal_button(self):
        if self.portal_button.text() == 'Activate Portal':
            if not self.portal_server.isAlive():
                self.portal_server.start()
            t = threading.Thread(target=self._portal_activation, args=())
            t.start()
        else:
            self.portal_button.setText('Activate Portal')
            self.portal_server.close_connection()
            self.portal_run_button.setEnabled(False)

    def _toggle_run_portal_button(self):
        data = self.portal_server.get_splitted_data()
        self._show_portal_dialog(data)
        if self.portal_subject is not None:
            self.portal_server.send_message(self.portal_subject)
            self.portal_server.stop()

    def _portal_activation(self):
        self.portal_button.setEnabled(False)
        self.portal_server.listen_connection()
        counter = 0
        while self.portal_server.is_listening:
            time.sleep(1)
            counter += 1
            if counter == 10:
                counter = 0
                print('No Portal..')
            if self._FINISH_THREADS:
                break

        if self.portal_server.connection is not None:
            self.portal_button.setText('Deactivate Portal')
            self.portal_server.receive_message()
            self.portal_button.setEnabled(True)
            counter = 0
            while self.portal_server.received_data is None:
                time.sleep(1)
                counter += 1
                if counter == 10:
                    counter = 0
                    print('No Data..')
                if self._FINISH_THREADS:
                    break
            self.portal_run_button.setEnabled(True)
        else:
            self.portal_button.setEnabled(True)

    def _show_portal_dialog(self, data):
        def select_clicked():
            items = listbox.selectedItems()
            if len(items) > 0:
                self.portal_subject = '0|' + combobox.currentText() + '/' + items[0].text()
                dialog.close()

        def new_clicked():
            self.portal_subject = '1|' + combobox.currentText()
            dialog.close()

        def combobox_changed():
            index = combobox.currentIndex()
            listbox.clear()
            if len(data[index]) > 2:
                listbox.addItems(data[index][2:])
            newmodel_button.setEnabled(int(data[index][1]))

        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle('Portal')
        dialog.setFixedSize(200, 270)

        select_button = QtWidgets.QPushButton('Select', dialog)
        select_button.move(10, 240)
        select_button.setFixedWidth(54)
        select_button.clicked.connect(select_clicked)

        newmodel_button = QtWidgets.QPushButton('New', dialog)
        newmodel_button.move(73, 240)
        newmodel_button.setFixedWidth(54)
        newmodel_button.clicked.connect(new_clicked)

        cancel_button = QtWidgets.QPushButton('Cancel', dialog)
        cancel_button.move(136, 240)
        cancel_button.setFixedWidth(54)
        cancel_button.clicked.connect(dialog.close)

        combobox = QtWidgets.QComboBox(dialog)
        combobox.setGeometry(10, 10, 180, 20)
        combobox.addItems([x[0] for x in data])
        combobox.currentIndexChanged.connect(combobox_changed)

        listbox = QtWidgets.QListWidget(dialog)
        combobox_changed()
        listbox.setGeometry(10, 40, 180, 190)
        dialog.exec_()

    @property
    def _node_widgets(self) -> List[QtWidgets.QWidget]:
        node_widgets = list()
        for node in self._pipeline.all_nodes:
            try:
                node_widgets.append(node.widget)
            except AttributeError:
                pass
        return node_widgets
