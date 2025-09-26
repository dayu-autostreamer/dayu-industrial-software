import numpy as np
import torch
from PIL import Image
from torch.autograd import Variable
from torchvision.transforms import ToTensor
import cv2 as cv

from .model import Net


class ESCPN:
    def __init__(self, model_path, device) -> None:
        model = Net(upscale_factor=2)
        model.load_state_dict(torch.load(model_path, map_location=torch.device(device)))
        self.model = model

    def genSR(self, frame):
        if frame.size == 0:
            return frame
        img = Image.fromarray(cv.cvtColor(frame, cv.COLOR_BGR2YCrCb))
        y, cb, cr = img.split()
        image = Variable(ToTensor()(y)).view(1, -1, y.size[1], y.size[0])
        out = self.model(image)
        out = out.cpu()
        out_img_y = out.data[0].numpy()
        out_img_y *= 255.0
        out_img_y = out_img_y.clip(0, 255)
        out_img_y = Image.fromarray(np.uint8(out_img_y[0]), mode='L')
        out_img_cb = cb.resize(out_img_y.size, Image.BICUBIC)
        out_img_cr = cr.resize(out_img_y.size, Image.BICUBIC)
        out_img = Image.merge(
            'YCbCr', [out_img_y, out_img_cb, out_img_cr])
        sr_img = cv.cvtColor(np.asarray(out_img), cv.COLOR_YCrCb2BGR)
        return sr_img
