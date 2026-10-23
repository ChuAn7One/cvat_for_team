"""Isolated inference engines; imports happen only in deployed containers."""
import sys

from geometry import mask_payload, validate_names


class Engine:
    def __init__(self, config):
        import torch

        self.config = config
        self.device = 'cuda:0' if config['gpu'] else 'cpu'
        if config['gpu'] and not torch.cuda.is_available():
            raise RuntimeError('GPU requested but CUDA is unavailable in this container')
        weights = '/opt/nuclio/weights/' + config['weights']
        self.names = config['labels']
        if config['engine'] == 'yolov5':
            sys.path.insert(0, '/opt/yolov5')
            from models.common import DetectMultiBackend
            self.model = DetectMultiBackend(weights, device=torch.device(self.device))
        else:
            from ultralytics import SAM, YOLO
            if config['engine'] == 'sam':
                self.model = SAM(weights)
            else:
                task = 'segment' if config['task'] == 'segment' else 'detect'
                self.model = YOLO(weights, task=task)
                if self.model.task != task:
                    raise ValueError('Checkpoint task differs from the deployment task')
        if config['engine'] != 'sam':
            names = self.model.names
            if isinstance(names, list):
                names = dict(enumerate(names))
            validate_names(self.names, names)

    def infer(self, image, data):
        import torch

        threshold = float(data.get('threshold', 0.25))
        if not 0 <= threshold <= 1:
            raise ValueError('threshold must be between 0 and 1')
        with torch.inference_mode():
            if self.config['engine'] == 'sam':
                return self._sam(image, data)
            if self.config['engine'] == 'yolov5':
                return self._v5(image, threshold)
            result = self.model.predict(source=image, conf=threshold, device=self.device,
                                        imgsz=self.config['imgsz'], retina_masks=True,
                                        verbose=False)[0]
            shapes = []
            for index, box in enumerate(result.boxes):
                mask = None
                if self.config['task'] == 'segment':
                    if result.masks is None:
                        raise RuntimeError('Segmentation checkpoint returned boxes without masks')
                    mask = result.masks.data[index].cpu().numpy() > 0.5
                    if mask.shape != (image.height, image.width):
                        raise RuntimeError('Mask dimensions differ from the original image')
                shape = self._shape(int(box.cls.item()), float(box.conf.item()),
                                    box.xyxy[0].tolist(), mask)
                if shape:
                    shapes.append(shape)
            return shapes

    def _shape(self, class_id, confidence, box, mask=None):
        shape = {'label': self.names[class_id], 'confidence': str(confidence),
                 'type': 'rectangle', 'points': box}
        if mask is not None:
            payload = mask_payload(mask.tolist())
            if payload is None:
                return None
            shape = {'label': self.names[class_id], 'confidence': str(confidence),
                     'type': 'mask', 'mask': payload}
        return shape

    def _sam(self, image, data):
        positive = data.get('pos_points', [])
        negative = data.get('neg_points', [])
        box = data.get('obj_bbox')
        if data.get('text_prompts'):
            raise ValueError('This adapter supports point/box prompts; text prompts need a separate SAM3 predictor')
        if not positive and box is None:
            if negative:
                raise ValueError('Provide a positive point or a bounding box before negative clicks')
            return {'shapes': []}
        prompts = {}
        if positive or negative:
            # Nested points represent ONE object with positive/negative clicks.
            prompts.update(points=[positive + negative],
                           labels=[[1] * len(positive) + [0] * len(negative)])
        if box is not None:
            if len(box) == 2 and isinstance(box[0], (list, tuple)):
                box = [*box[0], *box[1]]
            prompts['bboxes'] = [box]
        result = self.model.predict(source=image, device=self.device, verbose=False, **prompts)[0]
        shapes = []
        if result.masks is not None:
            for mask in result.masks.data.cpu().numpy():
                if mask.shape != (image.height, image.width):
                    raise RuntimeError('SAM mask dimensions differ from the original image')
                points = mask_payload((mask > 0.5).tolist(), rle=True)
                if points is not None:
                    shapes.append({'type': 'mask', 'points': points, 'group': 0,
                                   'source': 'semi-auto', 'attributes': [],
                                   'occluded': False, 'rotation': 0})
        return {'shapes': shapes}

    def _v5(self, image, threshold):
        import numpy as np
        import torch
        from utils.augmentations import letterbox
        from utils.general import check_img_size, non_max_suppression, scale_boxes
        from utils.segment.general import process_mask_native

        original = np.asarray(image)
        size = check_img_size(self.config['imgsz'], s=self.model.stride)
        resized = letterbox(original, size, stride=self.model.stride, auto=False)[0]
        # PIL input is already RGB; only change HWC to CHW.
        tensor = torch.from_numpy(np.ascontiguousarray(resized.transpose(2, 0, 1)))
        tensor = tensor.to(self.device).float().unsqueeze(0) / 255
        segment = self.config['task'] == 'segment'
        output = self.model(tensor)
        prediction = output[0] if isinstance(output, (list, tuple)) else output
        detections = non_max_suppression(prediction, threshold, 0.45, nm=32 if segment else 0)[0]
        if not len(detections):
            return []
        detections[:, :4] = scale_boxes(tensor.shape[2:], detections[:, :4], original.shape).round()
        masks = None
        if segment:
            masks = process_mask_native(output[1][0], detections[:, 6:], detections[:, :4],
                                        original.shape[:2]).cpu().numpy()
        shapes = []
        for index, detection in enumerate(detections):
            shape = self._shape(int(detection[5]), float(detection[4]),
                                detection[:4].tolist(), masks[index] if segment else None)
            if shape:
                shapes.append(shape)
        return shapes
