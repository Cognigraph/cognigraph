from typing import List
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTranslator, QEvent
from PyQt5.Qt import QSizePolicy
from PyQt5.QtWidgets import (
    QDockWidget,
    QWidget,
    QMainWindow,
    QMdiArea,
    QAction,
    QMdiSubWindow,
    QProgressDialog,
    QFileDialog,
    QMessageBox,
    QMenu,
)
from ..nodes.pipeline import Pipeline
from .async_pipeline_update import AsyncPipelineInitializer, AsyncUpdater
from .controls import Controls
from .. import PIPELINES_DIR
from .. import nodes
from . import qrc_resources  # noqa

import logging
import json


class _HookedSubWindow(QMdiSubWindow):
    """Subwindow with intercepted X button behaviour"""

    def closeEvent(self, close_event):
        """
        Before closing subwindow delete output node
        from pipeline and tree widget

        """
        node = self.widget().pipeline_node
        tw = self.parent().parent().parent()._controls.tree_widget
        item = tw.fetch_item_by_node(node)
        tw.remove_item(item)
        QMdiSubWindow.closeEvent(self, close_event)


class GUIWindow(QMainWindow):
    def __init__(self, app, pipeline=Pipeline()):
        super().__init__()
        self._app = app
        self._logger = logging.getLogger(self.__class__.__name__)
        self._is_initialized = False
        self.translator = QTranslator()
        self.language = 'eng'
        self.init_translator()
        self.init_basic(pipeline)
        self.init_ui()
        self.init_controls()
        self.setWindowTitle("Cognigraph")
        self.setWindowIcon(QIcon(':/cognigraph_icon.png'))

    def init_translator(self):
        print('Loading translation file:', self.translator.load('../translate/tr_eng.qm'))
        self._app.installTranslator(self.translator)
        # self._app.translate("QDockWidget", "Processing pipeline setup")
        # self._app.translate("QDockWidget", "Настройка конвейера")
        # self._app.translate("QMenu", "File")
        # self._app.translate("QMenu", "Файл")
        # self._app.translate("QMenu", "Load pipeline")
        # self._app.translate("QMenu", "Загрузить конвейер")
        # self._app.translate("QMenu", "Save pipeline")
        # self._app.translate("QMenu", "Сохранить конвейер")
        # self._app.translate("QMenu", "Language")
        # self._app.translate("QMenu", "Язык")
        # self._app.translate("QMenu", "English")
        # self._app.translate("QMenu", "Английский")
        # self._app.translate("QMenu", "Russian")
        # self._app.translate("QMenu", "Русский")
        # self._app.translate("QMenu", "Tile windows")
        # self._app.translate("QMenu", "Закрепить окна")
        # self._app.translate("QMenu", "View")
        # self._app.translate("QMenu", "Просмотр")
        # self._app.translate("QMenu", "Edit")
        # self._app.translate("QMenu", "Редактирование")
        # self._app.translate("QMenu", "Hide pipeline settings")
        # self._app.translate("QMenu", "Скрыть настройки конвейера")
        # self._app.translate("QMenu", "Show pipeline settings")
        # self._app.translate("QMenu", "Показать настройки конвейера")
        # self._app.translate("QMenu", "Start")
        # self._app.translate("QMenu", "Старт")
        # self._app.translate("QMenu", "Run")
        # self._app.translate("QMenu", "Запуск")
        # self._app.translate("QMenu", "Initialize pipeline")
        # self._app.translate("QMenu", "Инициализировать конвейер")
        # self._app.translate("Pipeline", "Pipeline")
        # self._app.translate("Pipeline", "Конвейер обработки")
        # self._app.translate("Pipeline", "File Source Node")
        # self._app.translate("Pipeline", "File Source")
        # self._app.translate("Pipeline", "Входной файл")
        # self._app.translate("Pipeline", "Preprocessing Node")
        # self._app.translate("Pipeline", "Preprocessing")
        # self._app.translate("Pipeline", "Предобработка")
        # self._app.translate("Pipeline", "Linear Filter Node")
        # self._app.translate("Pipeline", "Linear Filter")
        # self._app.translate("Pipeline", "Линейная фильтрация")
        # self._app.translate("Pipeline", "Beamformer Node")
        # self._app.translate("Pipeline", "Beamformer")
        # self._app.translate("Pipeline", "Бимформер")
        # self._app.translate("Pipeline", "Envelope Extractor Node")
        # self._app.translate("Pipeline", "Envelope Extractor")
        # self._app.translate("Pipeline", "Огибающая")
        # self._app.translate("Pipeline", "Brain Viewer Node")
        # self._app.translate("Pipeline", "Brain Viewer")
        # self._app.translate("Pipeline", "Отображение мозга")
        # self._app.translate("Pipeline", "LSL stream")
        # self._app.translate("Pipeline", "Входной LSL поток")
        # self._app.translate("Pipeline", "ICA Rejection")
        # self._app.translate("Pipeline", "Удаление артефактов (ICA)")
        # self._app.translate("Pipeline", "MNE")
        # self._app.translate("Pipeline", "MCE")
        # self._app.translate("Pipeline", "LSL Stream Output")
        # self._app.translate("Pipeline", "Выходной LSL поток")
        # self._app.translate("Pipeline", "File Output")
        # self._app.translate("Pipeline", "Выходной файл")
        # self._app.translate("Pipeline", "Signal Viewer")
        # self._app.translate("Pipeline", "Отображение сигналов")
        # self._app.translate("Pipeline", "Coherence")
        # self._app.translate("Pipeline", "Когерентности")
        # self._app.translate("Pipeline", "Atlas Viewer")
        # self._app.translate("Pipeline", "Отображение атласа")
        # self._app.translate("Pipeline", "Seed Coherence")
        # self._app.translate("Pipeline", "Когерентности с источником")
        # self._app.translate("Pipeline", "LSL stream Node")
        # self._app.translate("Pipeline", "ICA Rejection Node")
        # self._app.translate("Pipeline", "MNE Node")
        # self._app.translate("Pipeline", "MCE Node")
        # self._app.translate("Pipeline", "LSL Stream Output Node")
        # self._app.translate("Pipeline", "Signal Viewer Node")
        # self._app.translate("Pipeline", "File Output Node")
        # self._app.translate("Pipeline", "Atlas Viewer Node")
        # self._app.translate("Pipeline", "Seed Coherence Node")
        # self._app.translate("Pipeline", "Coherence Node")
        # self._app.translate("Parameters", "Factor: ")
        # self._app.translate("Parameters", "Method: ")
        # self._app.translate("Parameters", "Disable: ")
        # self._app.translate("Parameters", "Source type: ")
        # self._app.translate("Parameters", "Choose a stream: ")
        # self._app.translate("Parameters", "Path to file: ")
        # self._app.translate("Parameters", "Parameters setup")
        # self._app.translate("Parameters", "LSL stream Node")
        # self._app.translate("Parameters", "File Source Node")
        # self._app.translate("Parameters", "source controls")
        # self._app.translate("Parameters", "Select data...")
        # self._app.translate("Parameters", "Preprocessing")
        # self._app.translate("Parameters", "Baseline duration: ")
        # self._app.translate("Parameters", "Downsample factor: ")
        # self._app.translate("Parameters", "Find bad channels")
        # self._app.translate("Parameters", "Bad channels")
        # self._app.translate("Parameters", "Reset bad channels")
        # self._app.translate("Parameters", "Linear filter")
        # self._app.translate("Parameters", "Lower cutoff: ")
        # self._app.translate("Parameters", "Upper cutoff: ")
        # self._app.translate("Parameters", "ICA rejection")
        # self._app.translate("Parameters", "ICA duration: ")
        # self._app.translate("Parameters", "Collect data")
        # self._app.translate("Parameters", "Reset ICA decomposition")
        # self._app.translate("Parameters", "Select ICA components")
        # self._app.translate("Parameters", "Inverse modelling")
        # self._app.translate("Parameters", "SNR: ")
        # self._app.translate("Parameters", "Setup forward model")
        # self._app.translate("Parameters", "MCE Inverse modelling")
        # self._app.translate("Parameters", "Number of PCA components: ")
        # self._app.translate("Parameters", "Beamformer")
        # self._app.translate("Parameters", "Use adaptive version: ")
        # self._app.translate("Parameters", "Prewhiten: ")
        # self._app.translate("Parameters", "Regularization: ")
        # self._app.translate("Parameters", "Output type: ")
        # self._app.translate("Parameters", "Forgetting factor (per second): ")
        # self._app.translate("Parameters", "LSL stream")
        # self._app.translate("Parameters", "Output stream name: ")
        # self._app.translate("Parameters", "File Output")
        # self._app.translate("Parameters", "Output path: ")
        # self._app.translate("Parameters", "Change output file")
        # self._app.translate("Parameters", "Start")
        # self._app.translate("Parameters", "Signal Viewer")
        # self._app.translate("Parameters", "Coherence controls")
        # self._app.translate("Parameters", "Extract envelope: ")
        # self._app.translate("Parameters", "3D visualization settings")
        # self._app.translate("Parameters", "Show absolute values: ")
        # self._app.translate("Parameters", "Limits: ")
        # self._app.translate("Parameters", "Lock current limits: ")
        # self._app.translate("Parameters", "Buffer length: ")
        # self._app.translate("Parameters", "Lower limit: ")
        # self._app.translate("Parameters", "Upper limit: ")
        # self._app.translate("Parameters", "Show activations exceeding ")
        # self._app.translate("Parameters", "Record gif")
        # self._app.translate("Parameters", "Refresh rate, FPS")
        # self._app.translate("Parameters", "Atlas Viewer")
        # self._app.translate("Parameters", "Select ROI")
        # self._app.translate("Parameters", "Seed Coherence controls")
        # self._app.translate("Parameters", "Select seed")
        # self._app.translate("Parameters", "Forward solution file")
        # self._app.translate("Parameters", "Input file")
        # self._app.translate("Parameters", "Pipeline")
        # self._app.translate("Parameters", "Pipeline settings")
        # self._app.translate("Parameters", "Preprocessing Node")
        # self._app.translate("Parameters", "Linear Filter Node")
        # self._app.translate("Parameters", "Beamformer Node")
        # self._app.translate("Parameters", "Envelope Extractor Node")
        # self._app.translate("Parameters", "Brain Viewer Node")
        # self._app.translate("Parameters", "ICA Rejection Node")
        # self._app.translate("Parameters", "MNE Node")
        # self._app.translate("Parameters", "MCE Node")
        # self._app.translate("Parameters", "Signal Viewer Node")
        # self._app.translate("Parameters", "LSL Stream Output Node")
        # self._app.translate("Parameters", "File Output Node")
        # self._app.translate("Parameters", "Atlas Viewer Node")
        # self._app.translate("Parameters", "Seed Coherence Node")
        # self._app.translate("Parameters", "Coherence Node")

    def init_basic(self, pipeline):
        self._pipeline = pipeline  # type: Pipeline
        self._updater = AsyncUpdater(self._app, pipeline)
        self._pipeline._signal_sender.long_operation_started.connect(
            self._show_progress_dialog
        )
        self._pipeline._signal_sender.long_operation_finished.connect(
            self._hide_progress_dialog
        )
        self._pipeline._signal_sender.request_message.connect(
            self._show_message
        )
        self._pipeline._signal_sender.node_widget_added.connect(
            self._on_node_widget_added
        )
        self._controls = Controls(pipeline=self._pipeline, app=self._app)
        self._controls.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Expanding
        )

        self._controls.tree_widget.node_removed.connect(self._on_node_removed)
        if hasattr(self, "central_widget"):
            for w in self.central_widget.subWindowList():
                self.central_widget.removeSubWindow(w)

    def init_controls(self):
        self.controls_dock.setWidget(self._controls)
        self.run_toggle_action.triggered.disconnect()
        self.run_toggle_action.triggered.connect(self._updater.toggle)
        self._updater._sender.run_toggled.connect(self._on_run_button_toggled)
        self._updater._sender.errored.connect(self._show_message)
        self.is_initialized = False

    def init_ui(self):
        self.central_widget = QMdiArea()
        self.setCentralWidget(self.central_widget)

        # -------- controls widget -------- #
        self.controls_dock = QDockWidget("Processing pipeline setup", self)
        self.controls_dock.setObjectName("Controls")
        self.controls_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )
        self.controls_dock.visibilityChanged.connect(
            self._update_pipeline_tree_widget_action_text
        )

        self.addDockWidget(Qt.LeftDockWidgetArea, self.controls_dock)

        # self._controls.setMinimumWidth(800)
        # --------------------------------- #

        file_menu = self.menuBar().addMenu("File")  # file menu
        load_pipeline_action = self._createAction("Load pipeline", self._load_pipeline)
        save_pipeline_action = self._createAction("Save pipeline", self._save_pipeline)
        file_menu.addAction(load_pipeline_action)
        file_menu.addAction(save_pipeline_action)

        language_menu = self.menuBar().addMenu("Language")
        set_english_action = self._createAction("English", self._set_english)
        set_russian_action = self._createAction("Русский", self._set_russian)
        language_menu.addAction(set_english_action)
        language_menu.addAction(set_russian_action)

        # -------- view menu & toolbar -------- #
        tile_windows_action = self._createAction("Tile windows", self.central_widget.tileSubWindows)
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(tile_windows_action)
        view_toolbar = self.addToolBar("View")
        view_toolbar.addAction(tile_windows_action)
        # ------------------------------------- #

        edit_menu = self.menuBar().addMenu("Edit")
        self._toggle_pipeline_tree_widget_action = self._createAction("Hide pipeline settings", self._toggle_pipeline_tree_widget)
        edit_menu.addAction(self._toggle_pipeline_tree_widget_action)
        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setObjectName("edit_toolbar")
        edit_toolbar.addAction(self._toggle_pipeline_tree_widget_action)

        # -------- run menu & toolbar -------- #
        self.run_toggle_action = self._createAction("Start", self._on_run_button_toggled)
        run_menu = self.menuBar().addMenu("Run")
        self.initialize_pipeline = self._createAction("Initialize pipeline", self.initialize)
        run_menu.addAction(self.run_toggle_action)
        run_menu.addAction(self.initialize_pipeline)
        run_toolbar = self.addToolBar("Run")
        run_toolbar.setObjectName("run_toolbar")
        run_toolbar.addAction(self.run_toggle_action)
        run_toolbar.addAction(self.initialize_pipeline)
        # ------------------------------------ #

    def _toggle_pipeline_tree_widget(self):
        if self.controls_dock.isHidden():
            self.controls_dock.show()
        else:
            self.controls_dock.hide()

    def _update_pipeline_tree_widget_action_text(self, is_visible):
        if is_visible:
            self._toggle_pipeline_tree_widget_action.setText(self._app.translate("QMenu", "Hide pipeline settings"))
        else:
            self._toggle_pipeline_tree_widget_action.setText(self._app.translate("QMenu", "Show pipeline settings"))

    def _reinitialize_pipeline(self):
        params = self._pipeline._save_dict()
        # selected_item = self._controls.tree_widget.selectedIndexes()[0]
        pipeline = self.assemble_pipeline(params, "Pipeline")
        self.init_basic(pipeline)
        self.init_controls()
        # self._controls.tree_widget.setCurrentIndex(selected_item)

    def _load_pipeline(self):
        file_dialog = QFileDialog(
            caption="Select pipeline file", directory=PIPELINES_DIR
        )
        ext_filter = "JSON file (*.json);; All files (*.*)"
        pipeline_path = file_dialog.getOpenFileName(filter=ext_filter)[0]
        if pipeline_path:
            self._logger.info(
                "Loading pipeline configuration from %s" % pipeline_path
            )
            if not self._updater.is_paused:
                self.run_toggle_action.trigger()
            with open(pipeline_path, "r") as db:
                try:
                    params_dict = json.load(db)
                except json.decoder.JSONDecodeError as e:
                    self._show_message(
                        "Bad pipeline configuration file", detailed_text=str(e)
                    )

                pipeline = self.assemble_pipeline(params_dict, "Pipeline")
                self.init_basic(pipeline)
                self.init_controls()
                # self.resize(self.sizeHint())
        else:
            return

    def _save_pipeline(self):
        self._logger.info("Saving pipeline")
        file_dialog = QFileDialog(
            caption="Select pipeline file", directory=PIPELINES_DIR
        )
        ext_filter = "JSON file (*.json);; All files (*.*)"
        pipeline_path = file_dialog.getSaveFileName(filter=ext_filter)[0]
        if pipeline_path:
            self._logger.info(
                "Saving pipeline configuration to %s" % pipeline_path
            )
            try:
                self._pipeline.save_pipeline(pipeline_path)
            except Exception as exc:
                self._show_message(
                    "Cant`t save pipeline configuration to %s" % pipeline_path,
                    detailed_text=str(exc),
                )
                self._logger.exception(exc)

    def _set_english(self):
        if self.language == 'eng':
            return
        self.language = 'eng'
        self._app.removeTranslator(self.translator)
        print('Loading translation file:', self.translator.load('../translate/tr_eng.qm'))
        self._app.installTranslator(self.translator)

    def _set_russian(self):
        if self.language == 'ru':
            return
        self.language = 'ru'
        self._app.removeTranslator(self.translator)
        print('Loading translation file:', self.translator.load('../translate/tr_ru.qm'))
        self._app.installTranslator(self.translator)

    def translateUI(self):
        self.controls_dock.setWindowTitle(self._app.translate("QDockWidget", "Processing pipeline setup"))
        for child in self.menuBar().children():
            if isinstance(child, QMenu):
                child.setTitle(self._app.translate("QMenu", child.title()))
                for act in child.actions():
                    act.setText(self._app.translate("QMenu", act.text()))
        self._controls.translate_tree()
        self._reinitialize_pipeline()

    def changeEvent(self, event: QEvent):
        if (event.type() == QEvent.LanguageChange):
            self.translateUI()

    def assemble_pipeline(self, d, class_name):
        node_class = getattr(nodes, class_name)
        node = node_class(**d["init_args"])
        for child_class_name in d["children"]:
            child = self.assemble_pipeline(
                d["children"][child_class_name], child_class_name
            )
            node.add_child(child)
        return node

    def initialize(self):
        is_paused = self._updater.is_paused
        if not is_paused:
            self._updater.stop()
        self._logger.info("Initializing all nodes")
        async_initer = AsyncPipelineInitializer(
            pipeline=self._pipeline, parent=self
        )
        async_initer.no_blocking_execution()
        for node in self._pipeline.all_nodes:
            if hasattr(node, "widget"):
                if not node.widget.parent():  # widget not added to QMdiArea
                    self._add_subwindow(node.widget, repr(node))
        self.central_widget.tileSubWindows()
        self.run_toggle_action.setDisabled(False)
        if not is_paused:
            self._updater.start()

    def _finish_initialization(self):
        self.progress_dialog.hide()
        self.progress_dialog.deleteLater()
        for node in self._pipeline.all_nodes:
            if hasattr(node, "widget"):
                self._add_subwindow(node.widget, repr(node))
        self.central_widget.tileSubWindows()

    def _add_subwindow(self, widget, title):
        sw = _HookedSubWindow(self.central_widget)
        sw.setWidget(widget)
        sw.setWindowTitle(title)
        widget.show()

    def _show_progress_dialog(self, text):
        # -------- setup progress dialog -------- #
        self.progress_dialog = QProgressDialog(self)
        self.progress_dialog.setLabelText(text)
        self.progress_dialog.setCancelButtonText(None)
        self.progress_dialog.setRange(0, 0)
        self.progress_dialog.show()

    def _hide_progress_dialog(self):
        self.progress_dialog.hide()
        self.progress_dialog.deleteLater()

    def _on_subwindow_close(self, close_event):
        pass

    def _on_node_widget_added(self, widget, widget_name):
        self._add_subwindow(widget, widget_name)
        self.central_widget.tileSubWindows()

    def _on_node_removed(self, tree_item):
        if hasattr(tree_item.node, "widget"):
            try:
                self.central_widget.removeSubWindow(
                    tree_item.node.widget.parent()
                )
            except AttributeError:
                pass
            except Exception as exc:
                self._show_message(
                    "Can`t remove widget for %s" % tree_item.node,
                    detailed_text=str(exc),
                )
                self._logger.exception(exc)

    def _show_message(self, text, detailed_text=None, level="error"):
        if level == "error":
            icon = QMessageBox.Critical
        elif level == "warning":
            icon = QMessageBox.Warning
        elif level == "info":
            icon = QMessageBox.Information
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setText(text)
        msg.setDetailedText(detailed_text)
        msg.show()

    def _createAction(
        self,
        text,
        slot=None,
        shortcut=None,
        icon=None,
        tip=None,
        checkable=False,
    ):
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon(":/%s.png" % icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            action.triggered.connect(slot)
        if checkable:
            action.setCheckable(True)
        return action

    def moveEvent(self, event):
        return super(GUIWindow, self).moveEvent(event)

    def _on_run_button_toggled(self, is_paused=True):
        if is_paused:
            self.run_toggle_action.setText("Start")
        else:
            self.run_toggle_action.setText("Pause")

    @property
    def is_initialized(self):
        return self._is_initialized

    @is_initialized.setter
    def is_initialized(self, value):
        if value:
            self.run_toggle_action.setDisabled(False)
        else:
            self.run_toggle_action.setDisabled(True)
        self._is_initialized = value

    @property
    def _node_widgets(self) -> List[QWidget]:
        node_widgets = list()
        for node in self._pipeline.all_nodes:
            try:
                node_widgets.append(node.widget)
            except AttributeError:
                pass
        return node_widgets
