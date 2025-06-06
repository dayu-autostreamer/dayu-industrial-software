import threading
from .base_inference import BaseInference
from typing import List
import numpy as np
import os
import sys
cur_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(f"{cur_dir}/ofa")
from utils.bn_calibration import load_bn_statistics
import torch
import time
import cv2
import torchvision.transforms.functional as F
import torchvision.transforms as T
from PIL import Image

from core.lib.common import Context

class OfaInference(BaseInference):
# class OfaInference:
    def __init__(self, *args, **kwargs):
        '''
        Load all models, do all the necessary initializations.
        '''
        super().__init__(*args, **kwargs)
        # assert 'ofa_det_type' in kwargs, 'ofa_det_type not provided'
        self.ofa_det_type = kwargs['ofa_det_type']
        # assert self.ofa_det_type in ['mbv3_faster_rcnn', 'mbv3_fcos', 'resnet50_faster_rcnn', 'resnet50_fcos'], 'Invalid ofa_det_type'
        # assert 'subnet_nums' in kwargs, 'subnet_nums not provided'
        self.subnet_nums = kwargs['subnet_nums']
        # assert 'subnet_archs' in kwargs, 'subnet_archs not provided'
        self.subnet_archs = kwargs['subnet_archs']
        # assert 'subnet_accuracy' in kwargs, 'subnet_accuracy not provided'
        self.subnet_accuracy = kwargs['subnet_accuracy']
        self.subnet_latency =[]
        # assert len(self.subnet_archs) == self.subnet_nums, 'Subnet archs and subnet nums do not match'
        # assert len(self.subnet_accuracy) == self.subnet_nums, 'Subnet accuracy and subnet nums do not match'
        # TODO: validate subnet_archs 
        # assert 'weights_dir' in kwargs, 'weights_dir not provided'
        self.weights_dir = kwargs['weights_dir']
        self.supernet_path = f"{self.weights_dir}/supernet.pth"
        # assert os.path.exists(self.supernet_path), f"Supernet weights file not found: {self.supernet_path}"
        self.subnet_bn_paths = [f"{self.weights_dir}/net{i}_bn.pth" for i in range(kwargs['subnet_nums'])]
        # assert all([os.path.exists(path) for path in self.subnet_bn_paths]), f"Subnet bn weights file not found"

        if self.ofa_det_type == 'mbv3_faster_rcnn':
            from models.backbone.ofa_supernet import get_ofa_supernet_mbv3_w12
            from models.fpn.ofa_supernet_mbv3_w12_fpn import Mbv3W12Fpn
            from models.detection.fasterrcnn import get_faster_rcnn
            self.model = get_faster_rcnn(Mbv3W12Fpn(get_ofa_supernet_mbv3_w12()))
        elif self.ofa_det_type == 'mbv3_fcos':
            from models.backbone.ofa_supernet import get_ofa_supernet_mbv3_w12
            from models.fpn.ofa_supernet_mbv3_w12_fpn import Mbv3W12Fpn
            from models.detection.fcos import get_fcos
            self.model = get_fcos(Mbv3W12Fpn(get_ofa_supernet_mbv3_w12()))
        elif self.ofa_det_type == 'resnet_faster_rcnn':
            from models.backbone.ofa_supernet import get_ofa_supernet_resnet50
            from models.fpn.ofa_supernet_resnet50_fpn import Resnet50Fpn
            from models.detection.fasterrcnn import get_faster_rcnn
            self.model = get_faster_rcnn(Resnet50Fpn(get_ofa_supernet_resnet50()))
        elif self.ofa_det_type == 'resnet_fcos':
            from models.backbone.ofa_supernet import get_ofa_supernet_resnet50
            from models.fpn.ofa_supernet_resnet50_fpn import Resnet50Fpn
            from models.detection.fcos import get_fcos
            self.model = get_fcos(Resnet50Fpn(get_ofa_supernet_resnet50()))
        else:
            raise ValueError('Invalid ofa_det_type')
        
        self.current_model_index = None
        self.model_switch_lock = threading.Lock()
        self._load_supernet()
        self._measure_initial_latencies()

    def _load_supernet(self):
        print('Loading supernet...')
        try:
            print(f'Loading supernet...')
            model_path = Context.get_file_path(self.supernet_path)
            self.model = torch.load(model_path, map_location=torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'))
            self.model.eval()
            if torch.cuda.is_available():
                self.model = self.model.cuda()
            print(f'Supernet loaded.')
        except Exception as e:
            print(f'Error loading supernet: {str(e)}!')
        with self.model_switch_lock:
            self.current_model_index = 0
        print(f'Switched to model: {self.current_model_index}.')

    def _measure_initial_latencies(self):
        print("Measuring initial latencies...")
        dummy_input = torch.rand(1, 3, 640, 640).to(torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'))
        
        for idx in range(self.subnet_nums):
            times = []
            self.switch_model(idx)
            # 预热
            for _ in range(5):
                with torch.no_grad():
                    self.model(dummy_input)
            
            # 测量
            for _ in range(10):
                start_time = time.perf_counter()
                with torch.no_grad():
                    self.model(dummy_input)
                times.append(time.perf_counter() - start_time)
            self.subnet_latency.append(np.mean(times))
            print(f'Subnet {idx} takes time: {self.subnet_latency[idx]}')

    def switch_model(self, index: int):
        '''
        Switch the model to the one specified in the arguments.
        '''
        with self.model_switch_lock:
            if index >= self.subnet_nums or index < 0:
                raise ValueError('Invalid model index')
            relative_bn_weights_path = self.subnet_bn_paths[index]
            bn_weights_path = Context.get_file_path(relative_bn_weights_path)
            load_bn_statistics(self.model, bn_weights_path)
            self.model.backbone.body.set_active_subnet(**self.subnet_archs[index])
            self.model.eval()
            self.current_model_index = index
            print(f'Switched to model: {self.current_model_index}')

    def get_models_accuracy(self):
        return self.subnet_accuracy
    
    def get_models_latency(self):
        return self.subnet_latency
    
    def get_current_model_index(self):
        return self.current_model_index
    
    def get_models_num(self):
        '''
        Get the number of models.
        '''
        return self.subnet_nums
    
    def infer(self, image: np.ndarray):

        processed_image = self.preprocess_image(image).to(torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'))
        start_time = time.perf_counter()
        with torch.no_grad():
            results = self.model(processed_image)[0]
        inference_latency = time.perf_counter() - start_time
        # 过滤低置信度的预测结果
        mask = results['scores'] > 0.3
        boxes = results['boxes'][mask].cpu().numpy().tolist()
        labels = results['labels'][mask].cpu().numpy().tolist()
        scores = results['scores'][mask].cpu().numpy().tolist()

        # start a new thread to update stats
        update_stats_thread = threading.Thread(target=self.prepare_update_stats, args=(image, boxes, scores, labels, inference_latency))
        update_stats_thread.start()
        return boxes, scores, labels
    
    def prepare_update_stats(self, image: np.ndarray, boxes, scores, labels, inference_latency):
        '''
        Prepare the stats for updating.
        '''
        super().prepare_update_stats(image, boxes, scores, labels, inference_latency)    

    def preprocess_image(self, raw_bgr_image):

        # BGR numpy array -> RGB PIL Image
        rgb_image = cv2.cvtColor(raw_bgr_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        
        # 创建转换pipeline
        transform = T.Compose([
            T.ToTensor(),
        ])
        
        # PIL Image -> Tensor
        image_tensor = transform(pil_image)
        
        # 添加batch维度
        image_tensor = image_tensor.unsqueeze(0)
        
        return image_tensor

