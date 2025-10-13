from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import Context, FileOps
from core.lib.common import ClassFactory, ClassType
import os


@ClassFactory.register(ClassType.PROCESSOR, alias='mmwave_detector_processor')
class MMWaveDetectorProcessor(Processor):
    def __init__(self):
        super().__init__()
        # Read configuration file
        self.Detector = Context.get_instance('MMWaveDetector')

    def __call__(self, task: Task):
        data_file_path = task.get_file_path()
        # extract zip to a temporary directory
        tmp_dir = f"mmwave_{task.get_source_id()}_{task.get_task_id()}_dir"
        FileOps.create_directory(tmp_dir)
        FileOps.unzip_file(data_file_path, tmp_dir)

        # collect .bin files
        file_list = []
        for root, _, files in os.walk(tmp_dir):
            for fn in files:
                if fn.lower().endswith('.bin'):
                    file_list.append(os.path.join(root, fn))
        # sort by filename to preserve order
        file_list.sort()

        result = self.infer(file_list)

        # Store results in task
        task.set_current_content(result)

        FileOps.remove_file(tmp_dir)
        return task

    def infer(self, data):
        assert self.Detector, 'No mmw Detector defined!'

        with Timer(f'MMWave Detector'):
            process_output = self.Detector(data)

        return process_output
