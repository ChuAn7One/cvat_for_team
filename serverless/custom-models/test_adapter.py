"""Protocol/configuration checks; these do not validate checkpoint inference."""
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'nuclio'))
from geometry import mask_payload, validate_names
from engines import Engine

spec = importlib.util.spec_from_file_location('prepare_custom', ROOT / 'prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ProtocolTests(unittest.TestCase):
    def test_masks_roundtrip_inclusive_bounds_row_major(self):
        rng = random.Random(42)
        for height, width in [(1, 1), (3, 7), (9, 4)]:
            for _ in range(12):
                rows = [[rng.randrange(2) for _ in range(width)] for _ in range(height)]
                payload = mask_payload(rows, rle=True)
                if payload is None:
                    self.assertFalse(any(any(row) for row in rows))
                    continue
                left, top, right, bottom = payload[-4:]
                pixels = []
                for index, length in enumerate(payload[:-4]):
                    pixels.extend([index % 2] * length)
                restored = [[0] * width for _ in range(height)]
                crop_width = right - left + 1
                self.assertEqual(len(pixels), crop_width * (bottom - top + 1))
                for offset, value in enumerate(pixels):
                    restored[top + offset // crop_width][left + offset % crop_width] = value
                self.assertEqual(restored, rows)
                self.assertEqual(mask_payload(rows), pixels + payload[-4:])

    def test_empty_and_holes(self):
        self.assertIsNone(mask_payload([]))
        self.assertIsNone(mask_payload([[0, 0]]))
        self.assertEqual(mask_payload([[1, 1, 1], [1, 0, 1], [1, 1, 1]], rle=True),
                         [0, 4, 1, 4, 0, 0, 2, 2])

    def test_labels_must_match_ids(self):
        validate_names(['cat', 'dog'], {0: 'cat', 1: 'dog'})
        with self.assertRaises(ValueError):
            validate_names(['dog', 'cat'], {0: 'cat', 1: 'dog'})

    def test_detector_mask_has_dense_mask_field(self):
        class Mask:
            def tolist(self):
                return [[0, 0, 0], [0, 1, 1]]

        engine = Engine.__new__(Engine)
        engine.names = ['cat']
        self.assertEqual(engine._shape(0, 0.9, [0, 0, 3, 2], Mask()),
                         {'label': 'cat', 'confidence': '0.9', 'type': 'mask',
                          'mask': [1, 1, 1, 1, 2, 1]})

    def test_generate_gpu_segmentation_and_sam_configs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / 'sam2.1_b.pt'
            weights.write_bytes(b'CONFIGURATION TEST ONLY - NOT A CHECKPOINT')
            labels = root / 'labels.json'
            labels.write_text('["cat", "dog"]')
            for engine, task in [('ultralytics', 'segment'), ('yolov5', 'detect'),
                                 ('yolov5', 'segment'), ('sam', 'interactive')]:
                args = prepare.parser().parse_args([
                    '--name', f'test-{engine}-{task}', '--engine', engine, '--task', task,
                    '--weights', str(weights), '--labels', str(labels),
                    '--gpu', '--output', str(root / 'out')])
                target = prepare.prepare(args)
                function = json.loads((target / 'function.yaml').read_text())
                self.assertTrue(function['spec']['description'])
                self.assertEqual(function['spec']['resources']['limits']['nvidia.com/gpu'], 1)
                self.assertEqual(function['spec']['triggers']['myHttpTrigger']['numWorkers'], 1)
                self.assertEqual((target / 'weights' / weights.name).read_bytes(), weights.read_bytes())
                for filename in ['main.py', 'engines.py', 'geometry.py']:
                    compile((target / filename).read_text(), filename, 'exec')
                with self.assertRaises(FileExistsError):
                    prepare.prepare(args)
                if task == 'segment':
                    declared = json.loads(function['metadata']['annotations']['spec'])
                    self.assertEqual(declared[0]['type'], 'mask')
                elif task == 'interactive':
                    self.assertEqual(function['metadata']['annotations']['min_pos_points'], '0')

    def test_sam_prompt_protocol_and_original_image_masks(self):
        class Mask:
            shape = (2, 3)

            def __gt__(self, threshold):
                return self

            def tolist(self):
                return [[0, 0, 0], [0, 1, 1]]

        class Masks:
            @property
            def data(self):
                return self

            def cpu(self):
                return self

            def numpy(self):
                return [Mask()]

        class Result:
            masks = Masks()

        class Predictor:
            def predict(self, **kwargs):
                self.last_prompt = kwargs
                return [Result()]

        class Image:
            height, width = 2, 3

        engine = Engine.__new__(Engine)
        engine.device = 'cpu'
        engine.model = Predictor()
        self.assertEqual(engine._sam(Image(), {}), {'shapes': []})
        with self.assertRaises(ValueError):
            engine._sam(Image(), {'neg_points': [[0, 0]]})
        result = engine._sam(Image(), {'pos_points': [[2, 1]], 'neg_points': [[0, 0]]})
        self.assertEqual(engine.model.last_prompt['points'], [[[2, 1], [0, 0]]])
        self.assertEqual(engine.model.last_prompt['labels'], [[1, 0]])
        self.assertEqual(result['shapes'][0]['points'], [0, 2, 1, 1, 2, 1])
        engine._sam(Image(), {'obj_bbox': [[0, 0], [2, 1]]})
        self.assertEqual(engine.model.last_prompt['bboxes'], [[0, 0, 2, 1]])

    def test_invalid_engine_task_rejected_before_writes(self):
        args = prepare.parser().parse_args(['--name', 'bad', '--engine', 'sam',
                                            '--task', 'detect', '--weights', 'missing.pt'])
        with self.assertRaises(ValueError):
            prepare.prepare(args)


if __name__ == '__main__':
    unittest.main()
