import pytest
import os.path as op
from mne.io import Raw

from cognigraph import COGNIGRAPH_ROOT
from cognigraph.utils.io import DataDownloader

test_data_path = op.join(COGNIGRAPH_ROOT, 'tests/data')


@pytest.fixture
def info(scope='session'):
    """Get info with applied average projection"""
    dloader = DataDownloader()
    info_src_path = dloader.get_file('Koleno_raw.fif')
    raw = Raw(info_src_path, preload=True)
    raw.set_eeg_reference('average', projection=True)
    return raw.info
