"""Verify SAM prompts and saved masks in a dedicated, reusable test task."""
import argparse
import json
from pathlib import Path
import runpy
import time
import urllib.parse

HERE = Path(__file__).resolve().parent


def validate_mask(shape, width=810, height=1080):
    assert shape['type'] == 'mask', shape['type']
    points = shape['points']
    # CVAT serializes annotation points as floats, including integer-valued RLE counts.
    assert len(points) >= 5 and all(isinstance(value, (int, float)) and value == int(value)
                                  for value in points)
    points = [int(value) for value in points]
    counts, (left, top, right, bottom) = points[:-4], points[-4:]
    assert 0 <= left <= right < width and 0 <= top <= bottom < height
    assert all(count >= 0 for count in counts)
    assert sum(counts) == (right - left + 1) * (bottom - top + 1)
    assert sum(counts[1::2]) > 0, 'Empty mask'


def main():
    presets = json.loads((HERE / 'sam-models.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', choices=[item['name'] for item in presets],
                        default=[item['name'] for item in presets])
    args = parser.parse_args()
    module = runpy.run_path(str(HERE / 'verify-demo.py'))
    request, credentials = module['request'], module['credentials']
    request('/api/auth/login', {'username': credentials['username'], 'password': credentials['password']})
    functions = {item['id']: item for item in request('/api/lambda/functions')}
    for name in args.models:
        assert functions[name]['kind'] == 'interactor', name
        assert functions[name]['min_pos_points'] == 0, 'Box-only prompts need min_pos_points=0'
    state_path = HERE / '.sam-state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        team_path = HERE / '.team-state.json'
        suffix = ''
        if team_path.exists():
            suffix = '?org_id=' + str(json.loads(team_path.read_text())['organization_id'])
        task = request('/api/tasks' + suffix, {'name': 'SAM interactive deployment check - bus',
                                             'labels': [{'name': 'bus', 'type': 'mask'}]})
        state = {'task_id': task['id']}
        state_path.write_text(json.dumps(state))
    task_id = state['task_id']
    if request(f'/api/tasks/{task_id}').get('size', 0) == 0:
        if 'rq_id' not in state:
            response = module['upload_image'](task_id)
            state['rq_id'] = response['rq_id']
            state_path.write_text(json.dumps(state))
        for _ in range(90):
            status = request('/api/requests/' + urllib.parse.quote(state['rq_id'], safe=''))
            if status['status'] == 'finished':
                break
            if status['status'] == 'failed':
                raise RuntimeError(f'Test image import failed: {status}')
            time.sleep(2)
        else:
            raise TimeoutError('Test image import timed out')
    task = request(f'/api/tasks/{task_id}')
    assert task['size'] == 1
    labels = request(f'/api/labels?task_id={task_id}')['results']
    label_id = next(label['id'] for label in labels if label['name'] == 'bus')
    cases = {
        'point': {'pos_points': [[400, 400]], 'neg_points': []},
        'point_and_negative': {'pos_points': [[400, 400]], 'neg_points': [[400, 100]]},
        'box': {'pos_points': [], 'neg_points': [], 'obj_bbox': [[20, 230], [805, 750]]},
    }
    shapes, checks = [], []
    for group, name in enumerate(args.models, 1):
        for case, prompts in cases.items():
            started = time.monotonic()
            response = request('/api/lambda/functions/' + name,
                               {'task': task_id, 'frame': 0, **prompts})
            elapsed = round(time.monotonic() - started, 3)
            assert response['shapes'], f'{name}: no masks for {case}'
            for shape in response['shapes']:
                validate_mask(shape)
                shapes.append({**shape, 'label_id': label_id, 'frame': 0, 'group': group})
            check = {'model': name, 'prompt': case, 'masks': len(response['shapes']), 'seconds': elapsed}
            checks.append(check)
            print(json.dumps(check), flush=True)
    current = request(f'/api/tasks/{task_id}/annotations')
    request(f'/api/tasks/{task_id}/annotations',
            {'version': current['version'], 'tags': [], 'tracks': [], 'shapes': shapes}, method='PUT')
    saved = request(f'/api/tasks/{task_id}/annotations')['shapes']
    assert len(saved) == len(shapes)
    for expected, actual in zip(shapes, saved):
        assert expected['points'] == actual['points'] and actual['label_id'] == label_id
        validate_mask(actual)
    report = {'status': 'passed', 'task_id': task_id,
              'task_url': f'{module["base"]}/tasks/{task_id}', 'checks': checks, 'saved_masks': len(saved)}
    (HERE / 'sam-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
