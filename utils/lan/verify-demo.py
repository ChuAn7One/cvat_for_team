"""Exercise CVAT login, image import, model invocation, and saved annotations."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
credentials = json.loads((HERE / '.credentials.json').read_text(encoding='utf-8-sig'))
base = credentials['url']
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                    urllib.request.HTTPCookieProcessor(cookies))


def request(path, data=None, method=None, content_type=None):
    headers = {'Referer': base + '/'}
    csrf = next((cookie.value for cookie in cookies if cookie.name == 'csrftoken'), None)
    if csrf:
        headers['X-CSRFToken'] = csrf
    if data is not None and not isinstance(data, bytes):
        data = json.dumps(data).encode()
        content_type = 'application/json'
    if content_type:
        headers['Content-Type'] = content_type
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=180) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        # Login payloads/tokens are never included in diagnostics.
        raise RuntimeError(f'{path}: HTTP {error.code}: {error.read().decode()[:800]}') from None


def upload_image(task_id):
    boundary = 'cvat-demo-' + uuid.uuid4().hex
    parts = []
    for name, value in [('image_quality', '80')]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="client_files[0]"; '
                  'filename="bus.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode())
    parts.append((HERE / 'models/bus.jpg').read_bytes())
    parts.append(f'\r\n--{boundary}--\r\n'.encode())
    return request(f'/api/tasks/{task_id}/data', b''.join(parts),
                   content_type=f'multipart/form-data; boundary={boundary}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    about = request('/api/server/about')
    request('/api/auth/login', {'username': credentials['username'], 'password': credentials['password']})
    user = request('/api/users/self')
    assert user['is_superuser'], 'Expected administrator login'
    state_path = HERE / '.demo-state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        labels = json.loads((HERE / 'models/labels.json').read_text())
        task = request('/api/tasks', {'name': 'YOLO11n deployment demo - bus',
                                     'labels': [{'name': name, 'type': 'rectangle'} for name in labels]})
        state = {'task_id': task['id']}
        state_path.write_text(json.dumps(state))
        response = upload_image(task['id'])
        if response and response.get('rq_id'):
            state['rq_id'] = response['rq_id']
            state_path.write_text(json.dumps(state))
    task_id = state['task_id']
    if state.get('rq_id') and request(f'/api/tasks/{task_id}')['size'] == 1:
        state.pop('rq_id')
        state_path.write_text(json.dumps(state))
    if state.get('rq_id'):
        for _ in range(90):
            status = request('/api/requests/' + urllib.parse.quote(state['rq_id'], safe=''))
            if status['status'] == 'finished':
                break
            if status['status'] == 'failed':
                raise RuntimeError(f'Image import failed: {status}')
            time.sleep(2)
        else:
            raise TimeoutError('Image import did not finish')
        state.pop('rq_id')
        state_path.write_text(json.dumps(state))
    task_id = state['task_id']
    task = request(f'/api/tasks/{task_id}')
    assert task['size'] == 1, task
    print(f'CVAT {about["version"]}: admin login and image import OK; task={task_id}', flush=True)
    if not args.prepare_only:
        functions = request('/api/lambda/functions')
        assert any(function['id'] == 'yolo11n-demo' for function in functions), functions
        result = request('/api/lambda/functions/yolo11n-demo',
                         {'task': task_id, 'frame': 0, 'threshold': 0.25})
        assert result['shapes'], 'Model returned no detections for official bus image'
        payload = {'version': 0, 'tags': result.get('tags', []),
                   'tracks': [], 'shapes': result['shapes']}
        request(f'/api/tasks/{task_id}/annotations', payload, method='PUT')
        saved = request(f'/api/tasks/{task_id}/annotations')
        assert len(saved['shapes']) == len(result['shapes'])
        report = {'cvat_version': about['version'], 'task_id': task_id,
                  'task_url': f'{base}/tasks/{task_id}', 'model': 'yolo11n-demo',
                  'saved_shapes': len(saved['shapes']), 'status': 'passed'}
        (HERE / 'verification.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report), flush=True)
