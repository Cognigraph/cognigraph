import os.path as op

from cognigraph.nodes import sources, outputs
from cognigraph.pipeline import Pipeline
import logging
import time

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s:%(name)-17s:%(levelname)s:%(message)s')


cur_dir = '/home/dmalt/Code/python/cogni_submodules'  # < -- поменять на своё
data_fname = 'DF_2018-03-02_11-34-38.edf'  # < -- поменять на своё

test_data_path = cur_dir + '/tests/data/'
sim_data_path = op.join(test_data_path, data_fname)


test_data_path = cur_dir + '/tests/data/'
source = sources.FileSource(file_path=sim_data_path)
source.loop_the_file = True

pipeline = Pipeline()
pipeline.source = source
output_stream_name = 'outlsl'
pipeline.add_output(outputs.LSLStreamOutput(output_stream_name))


pipeline.initialize_all_nodes()

while True:
    pipeline.update_all_nodes()
    time.sleep(0.01)
