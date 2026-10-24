"""Check existing YOLO/SAM services through CVAT without saving annotations."""
import json
from pathlib import Path
import runpy
import time

HERE = Path(__file__).resolve().parent


def main():
    module = runpy.run_path(str(HERE / 'verify-demo.py'))
    request, credentials = module['request'], module['credentials']
    request('/api/auth/login', {'username': credentials['username'], 'password': credentials['password']})
    detector_task = json.loads((HERE / '.demo-state.json').read_text())['task_id']
    sam_task = json.loads((HERE / '.sam-state.json').read_text())['task_id']
    task_ids = {detector_task, sam_task}
    before = {task_id: request(f'/api/tasks/{task_id}/annotations') for task_id in task_ids}
    sam_models = json.loads((HERE / 'sam-models.json').read_text())
    cases = [('yolo11n-demo', detector_task, {'threshold': 0.25}, 'rectangle')]
    cases.extend((model['name'], sam_task, {'pos_points': [[400, 400]], 'neg_points': []}, 'mask')
                 for model in sam_models)
    for name, task_id, prompts, shape_type in cases:
        started = time.monotonic()
        result = request('/api/lambda/functions/' + name, {'task': task_id, 'frame': 0, **prompts})
        assert isinstance(result, dict) and result.get('shapes'), f'{name}: invalid result'
        assert all(shape['type'] == shape_type for shape in result['shapes']), f'{name}: wrong model response'
        print(json.dumps({'model': name, 'type': shape_type, 'shapes': len(result['shapes']),
                          'seconds': round(time.monotonic() - started, 3), 'status': 'passed'}), flush=True)
    for task_id in task_ids:
        assert request(f'/api/tasks/{task_id}/annotations') == before[task_id], 'Annotations changed during check'
    print('All model calls passed; saved annotations unchanged.', flush=True)


if __name__ == '__main__':
    main()
