import os
import time
from types import SimpleNamespace

import tables
from PyQt5.QtCore import pyqtSignal, QObject,  QThread
from PyQt5.QtWidgets import QSizePolicy, QApplication

import mne
import nibabel as nib
import numpy as np
import pyqtgraph.opengl as gl
from matplotlib import cm
from matplotlib.colors import Colormap as matplotlib_Colormap
from mne.datasets import sample
from scipy import sparse

from ..helpers.pysurfer.smoothing_matrix import smoothing_matrix, mesh_edges
from .node import OutputNode
from .. import CHANNEL_AXIS, TIME_AXIS, PYNFB_TIME_AXIS
from ..helpers.lsl import (convert_numpy_format_to_lsl,
                           convert_numpy_array_to_lsl_chunk,
                           create_lsl_outlet)
from ..helpers.matrix_functions import last_sample, make_time_dimension_second
from ..helpers.ring_buffer import RingBuffer
from ..helpers.channels import read_channel_types, channel_labels_saver
from ..helpers.inverse_model import get_mesh_data_from_forward_solution
from vendor.nfb.pynfb.widgets.signal_viewers import RawSignalViewer

# visbrain visualization imports
from ..gui.brain_visual import BrainMesh
from vispy import scene
# from vispy.app import Canvas

import torch
# import logging


class Communicate(QObject):
    init_widget_sig = pyqtSignal()
    draw_sig = pyqtSignal('PyQt_PyObject')


class WidgetOutput(OutputNode):
    """Abstract class for widget initialization logic with qt signals"""
    def __init__(self, *pargs, **kwargs):
        OutputNode.__init__(self, *pargs, **kwargs)
        self.signal_sender = Communicate()
        self.signal_sender.init_widget_sig.connect(self.init_widget)
        self.signal_sender.draw_sig.connect(self.on_draw)

    def init_widget(self):
        if self.widget is not None:
            parent = self.widget.parent()
            ind = parent.indexOf(self.widget)
            cur_width = self.widget.size().width()
            cur_height = self.widget.size().height()
            self.widget.deleteLater()
            self.widget = self._create_widget()
            parent.insertWidget(ind, self.widget)
            self.widget.resize(cur_width, cur_height)
        else:
            self.widget = self._create_widget()
            self.widget.setMinimumWidth(50)

    def _create_widget(self):
        raise NotImplementedError

    def on_draw(self):
        raise NotImplementedError


class LSLStreamOutput(OutputNode):

    def _on_input_history_invalidation(self):
        pass

    def _check_value(self, key, value):
        pass  # TODO: check that value as a string usable as a stream name

    CHANGES_IN_THESE_REQUIRE_RESET = ('stream_name', )

    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = (
        'source_name', 'mne_info', 'dtype')

    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = (
        {'mne_info': lambda info: (info['sfreq'], ) +
         channel_labels_saver(info)})

    def _reset(self):
        # It is impossible to change then name of an already
        # started stream so we have to initialize again
        self._should_reinitialize = True
        self.initialize()

    def __init__(self, stream_name=None):
        super().__init__()
        self._provided_stream_name = stream_name
        self.stream_name = None
        self._outlet = None

    def _initialize(self):
        # If no name was supplied we will use a modified
        # version of the source name (a file or a stream name)
        source_name = self.traverse_back_and_find('source_name')
        self.stream_name = (self._provided_stream_name or
                            (source_name + '_output'))

        # Get other info from somewhere down the predecessor chain
        dtype = self.traverse_back_and_find('dtype')
        channel_format = convert_numpy_format_to_lsl(dtype)
        mne_info = self.traverse_back_and_find('mne_info')
        frequency = mne_info['sfreq']
        channel_labels = mne_info['ch_names']
        channel_types = read_channel_types(mne_info)

        self._outlet = create_lsl_outlet(
            name=self.stream_name, frequency=frequency,
            channel_format=channel_format, channel_labels=channel_labels,
            channel_types=channel_types)

    def _update(self):
        chunk = self.input_node.output
        lsl_chunk = convert_numpy_array_to_lsl_chunk(chunk)
        self._outlet.push_chunk(lsl_chunk)


class BrainViewer(WidgetOutput):

    CHANGES_IN_THESE_REQUIRE_RESET = ('buffer_length', 'take_abs', )
    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = (
        'mne_forward_model_file_path', 'mne_info')

    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = {'mne_info': channel_labels_saver}

    LIMITS_MODES = SimpleNamespace(GLOBAL='Global', LOCAL='Local',
                                   MANUAL='Manual')

    def __init__(self, take_abs=True, limits_mode=LIMITS_MODES.LOCAL,
                 buffer_length=1, threshold_pct=50, surfaces_dir=None):
        super().__init__()

        self.limits_mode = limits_mode
        self.lock_limits = False
        self.buffer_length = buffer_length
        self.take_abs = take_abs
        self.colormap_limits = SimpleNamespace(lower=None, upper=None)
        self._threshold_pct = threshold_pct

        self._limits_buffer = None
        self.surfaces_dir = surfaces_dir
        self.mesh_data = None
        self.smoothing_matrix = None
        self.widget = None
        self.output = None

    def _initialize(self):
        mne_forward_model_file_path = self.traverse_back_and_find(
            'mne_forward_model_file_path')

        frequency = self.traverse_back_and_find('mne_info')['sfreq']
        buffer_sample_count = np.int(self.buffer_length * frequency)
        self._limits_buffer = RingBuffer(row_cnt=2, maxlen=buffer_sample_count)

        self.forward_solution = mne.read_forward_solution(
            mne_forward_model_file_path, verbose='ERROR')
        self.mesh_data = self._get_mesh_data_from_surfaces_dir()
        self.signal_sender.init_widget_sig.emit()
        self.smoothing_matrix = self._get_smoothing_matrix(
            mne_forward_model_file_path)

    def _on_input_history_invalidation(self):
        self._should_reset = True
        self.reset()

    def _check_value(self, key, value):
        pass

    def _reset(self):
        self._limits_buffer.clear()

    @property
    def threshold_pct(self):
        return self._threshold_pct

    @threshold_pct.setter
    def threshold_pct(self, value):
        self._threshold_pct = value

    def _update(self):
        sources = self.input_node.output
        self.output = sources
        if self.take_abs:
            sources = np.abs(sources)
        self._update_colormap_limits(sources)
        normalized_sources = self._normalize_sources(last_sample(sources))
        self.signal_sender.draw_sig.emit(normalized_sources)

    def _update_colormap_limits(self, sources):
        self._limits_buffer.extend(np.array([
            make_time_dimension_second(np.min(sources, axis=CHANNEL_AXIS)),
            make_time_dimension_second(np.max(sources, axis=CHANNEL_AXIS)),
        ]))

        if self.limits_mode == self.LIMITS_MODES.GLOBAL:
            mins, maxs = self._limits_buffer.data
            self.colormap_limits.lower = np.percentile(mins, q=5)
            self.colormap_limits.upper = np.percentile(maxs, q=95)
        elif self.limits_mode == self.LIMITS_MODES.LOCAL:
            sources = last_sample(sources)
            self.colormap_limits.lower = np.min(sources)
            self.colormap_limits.upper = np.max(sources)
        elif self.limits_mode == self.LIMITS_MODES.MANUAL:
            pass

    def _normalize_sources(self, last_sources):
        minimum = self.colormap_limits.lower
        maximum = self.colormap_limits.upper
        if minimum == maximum:
            return last_sources * 0
        else:
            return (last_sources - minimum) / (maximum - minimum)


    def on_draw(self, normalized_values):
        QApplication.processEvents()
        if self.smoothing_matrix is not None:
            sources_smoothed = self.smoothing_matrix.dot(normalized_values)
        else:
            self.logger.debug('Draw without smoothing')
            sources_smoothed = normalized_values
        threshold = self.threshold_pct / 100
        mask = sources_smoothed <= threshold

        # reset colors to white
        self.mesh_data._alphas[:, :] = 0.
        self.mesh_data._alphas_buffer.set_data(self.mesh_data._alphas)

        if np.any(~mask):
            self.mesh_data.add_overlay(sources_smoothed[~mask],
                                       vertices=np.where(~mask)[0],
                                       to_overlay=1)
        self.mesh_data.update()
        if self.logger.getEffectiveLevel() == 20:  # DEBUG level
            self.canvas.measure_fps(
                window=10,
                callback=(lambda x:
                          self.logger.info('Updating at %1.1f FPS' % x)))

    def _get_mesh_data_from_surfaces_dir(self, cortex_type='inflated'):
        if self.surfaces_dir:
            surf_paths = [os.path.join(self.surfaces_dir,
                                       '{}.{}'.format(h, cortex_type))
                          for h in ('lh', 'rh')]
        else:
            raise NameError('surfaces_dir is not set')
        lh_mesh, rh_mesh = [nib.freesurfer.read_geometry(surf_path)
                            for surf_path in surf_paths]
        lh_vertexes, lh_faces = lh_mesh
        rh_vertexes, rh_faces = rh_mesh

        # Move all the vertices so that the lh has x (L-R) <= 0 and rh - >= 0
        lh_vertexes[:, 0] -= np.max(lh_vertexes[:, 0])
        rh_vertexes[:, 0] -= np.min(rh_vertexes[:, 0])

        # Combine two meshes
        vertices = np.r_[lh_vertexes, rh_vertexes]
        lh_vertex_cnt = lh_vertexes.shape[0]
        faces = np.r_[lh_faces, lh_vertex_cnt + rh_faces]

        # Move the mesh so that the center of the brain is at (0, 0, 0) (kinda)
        vertices[:, 1:2] -= np.mean(vertices[:, 1:2])

        mesh_data = BrainMesh(vertices=vertices, faces=faces)

        return mesh_data


    def _create_widget(self):
        canvas = scene.SceneCanvas(keys='interactive', show=True)
        self.canvas = canvas

        # Add a ViewBox to let the user zoom/rotate
        view = canvas.central_widget.add_view()
        view.camera = 'turntable'
        view.camera.fov = 50
        view.camera.distance = 400
        # Make light follow the camera
        self.mesh_data.shared_program.frag['camtf'] = view.camera.transform
        view.add(self.mesh_data)
        return canvas.native

    def _get_smoothing_matrix(self, mne_forward_model_file_path):
        """
        Creates or loads a smoothing matrix that lets us
        interpolate source values onto all mesh vertices

        """
        # Not all the vertices in the forward solution mesh are sources.
        # sources_idx actually indexes into the union of
        # high-definition meshes for left and right hemispheres.
        # The smoothing matrix then lets us assign a color to each vertex.
        # If in future we decide to use low-definition mesh from
        # the forward model for drawing, we should index into that.
        # Shorter: the coordinates of the jth source are
        # in self.mesh_data.vertexes()[sources_idx[j], :]
        smoothing_matrix_file_path = (
            os.path.splitext(mne_forward_model_file_path)[0] +
            '-smoothing-matrix.npz')
        try:
            return sparse.load_npz(smoothing_matrix_file_path)
        except FileNotFoundError:
            self.logger.info('Calculating smoothing matrix.' +
                             ' This might take a while the first time.')
            sources_idx, vertexes, faces = get_mesh_data_from_forward_solution(
                self.forward_solution)
            adj_mat = mesh_edges(self.mesh_data._faces)
            smoothing_mat = smoothing_matrix(sources_idx, adj_mat)
            sparse.save_npz(smoothing_matrix_file_path, smoothing_mat)
            return smoothing_mat


class AtlasViewer(OutputNode):
    CHANGES_IN_THESE_REQUIRE_RESET = ('label_states')
    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ()

    def __init__(self, surface_dir, annot_file='aparc.a2009s.annot'):
        super().__init__()
        self.annotation = None
        self.annot_file = annot_file

        # base, fname = os.path.split(self.annot_file)
        self.annot_files = [
            os.path.join(surface_dir, 'label', hemi + self.annot_file)
            for hemi in ('lh.', 'rh.')]

        self._read_annotation(self.annot_files)

        n_labels = len(self.label_names)
        self.label_states = []
        for i_label in range(n_labels):
            label_id = (i_label + 1
                        if self.label_names[i_label] != 'Unknown' else -1)
            label_dict = {'label_name': self.label_names[i_label],
                          'label_id': label_id, 'state': False}
            self.label_states.append(label_dict)

    def _reset(self):
        self.active_labels = [l for l in self.label_states if l['state']]
        self.mne_info = mne.create_info(
            ch_names=[str(a['label_id']) for a in self.active_labels],
            sfreq=self.sfreq)


    # def _create_widget(self):
    #     ...

    def _initialize(self):
        mne_forward_model_file_path = self.traverse_back_and_find(
            'mne_forward_model_file_path')
        self.forward_solution = mne.read_forward_solution(
            mne_forward_model_file_path, verbose='ERROR')
        # Map sources for which we solve the inv problem to the dense
        # cortex which we use for plotting
        sources_idx, _, _ = get_mesh_data_from_forward_solution(
            self.forward_solution)
        # self.sources_idx, self.vetices = sources_idx, vertices
        # print(sources_idx.shape)

        # Assign labels to available sources
        self.source_labels = np.array(
            [self.vert_labels[i] for i in sources_idx])

        self.active_labels = [l for l in self.label_states if l['state']]

        self.sfreq = self.traverse_back_and_find('mne_info')['sfreq']
        self.mne_info = mne.create_info(
            ch_names=[str(a['label_id']) for a in self.active_labels],
            sfreq=self.sfreq)

    def _read_annotation(self, annot_files):
        try:
            # Merge numeric labels and label names from both hemispheres
            annot_lh = nib.freesurfer.io.read_annot(filepath=annot_files[0])
            annot_rh = nib.freesurfer.io.read_annot(filepath=annot_files[1])

            # Get label for each vertex in dense source space
            vert_labels_lh = annot_lh[0]
            vert_labels_rh = annot_rh[0]

            vert_labels_rh[vert_labels_rh > 0] += np.max(vert_labels_lh)

            label_names_lh = annot_lh[2]
            label_names_rh = annot_rh[2]

            label_names_lh = np.array(
                [ln.decode('utf-8') for ln in label_names_lh])
            label_names_rh = np.array(
                [ln.decode('utf-8') for ln in label_names_rh])

            label_names_lh = np.array([ln + '_LH' if ln != 'Unknown'
                                       else ln for ln in label_names_lh])
            label_names_rh = np.array([ln + '_RH' for ln in label_names_rh
                                       if ln != 'Unknown'])

            self.label_names = np.r_[label_names_lh, label_names_rh]
            self.logger.debug(
                'Found the following labels in annotation: {}'
                .format(self.label_names))
            self.vert_labels = np.r_[vert_labels_lh, vert_labels_rh]
        except FileNotFoundError:
            self.logger.error(
                'Annotation files not found: {}'.format(annot_files))
            # Open file picker dialog here
            ...

    def _update(self):
        data = self.input_node.output


        n_times = data.shape[1]
        n_active_labels = len(self.active_labels)

        data_label = np.empty([n_active_labels, n_times])
        for i_label, label in enumerate(self.active_labels):
            # print(label)
            # print(self.source_labels)
            label_mask = self.source_labels == label['label_id']
            # print(label_mask)
            data_label[i_label, :] = np.mean(data[label_mask, :], axis=0)
            # print(data_label)
        self.output = data_label
        self.logger.debug(data.shape)

    def _check_value(self, key, value):
        ...


class SignalViewer(WidgetOutput):
    CHANGES_IN_THESE_REQUIRE_RESET = ()

    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ('mne_info',)
    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = {'mne_info': channel_labels_saver}

    def __init__(self):
        super().__init__()
        self.widget = None

    def _initialize(self):
        self.signal_sender.init_widget_sig.emit()

    def _create_widget(self):
        mne_info = self.traverse_back_and_find('mne_info')
        if mne_info['nchan']:
            return RawSignalViewer(fs=mne_info['sfreq'],
                                   names=mne_info['ch_names'],
                                   seconds_to_plot=10)
        else:
            return RawSignalViewer(fs=mne_info['sfreq'],
                                   names=[''],
                                   seconds_to_plot=10)


    def _update(self):
        chunk = self.input_node.output
        self.signal_sender.draw_sig.emit(chunk)

    def on_draw(self, chunk):
        QApplication.processEvents()
        if chunk.size:
            if TIME_AXIS == PYNFB_TIME_AXIS:
                self.widget.update(chunk)
            else:
                self.widget.update(chunk.T)

    def _reset(self) -> bool:
        # Nothing to reset, really
        pass

    def _on_input_history_invalidation(self):
        # Don't really care, will draw whatever
        pass

    def _check_value(self, key, value):
        # Nothing to be set
        pass

class FileOutput(OutputNode):

    def _on_input_history_invalidation(self):
        pass

    def _check_value(self, key, value):
        pass  # TODO: check that value as a string usable as a stream name

    CHANGES_IN_THESE_REQUIRE_RESET = ('stream_name', )

    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ('mne_info', )
    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = {'mne_info':
                                           lambda info: (info['sfreq'], ) +
                                           channel_labels_saver(info)}

    def _reset(self):
        self._should_reinitialize = True
        self.initialize()

    def __init__(self, output_fname='output.h5'):
        super().__init__()
        self.output_fname = output_fname
        self.out_file = None

    def _initialize(self):
        if self.out_file:  # for resets
            self.out_file.close()

        info = self.traverse_back_and_find('mne_info')
        col_size = info['nchan']
        self.out_file = tables.open_file(self.output_fname, mode='w')
        atom = tables.Float64Atom()

        self.output_array = self.out_file.create_earray(
            self.out_file.root, 'data', atom, (col_size, 0))

    def _update(self):
        chunk = self.input_node.output
        self.output_array.append(chunk)


class TorchOutput(OutputNode):

    CHANGES_IN_THESE_REQUIRE_RESET = ()
    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ()

    def _on_input_history_invalidation(self):
        pass

    def _check_value(self, key, value):
        pass  # TODO: check that value as a string usable as a stream name

    def _reset(self):
        pass

    def _initialize(self):
        pass

    def _update(self):
        self.output = torch.from_numpy(self.input_node.output)
