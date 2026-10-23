"""Prepare one Nuclio function per checkpoint, without importing ML packages."""
import argparse
import json
from pathlib import Path
import re
import shlex
import shutil


def prepare(args):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,54}', args.name):
        raise ValueError('name must be lowercase letters, numbers and hyphens (max 55)')
    if (args.engine == 'sam') != (args.task == 'interactive'):
        raise ValueError('sam requires task=interactive; YOLO requires detect or segment')
    weights = Path(args.weights).resolve(strict=True)
    if weights.suffix.lower() not in {'.pt', '.pth'} or not re.fullmatch(r'[\w.-]+', weights.name):
        raise ValueError('Provide a .pt/.pth checkpoint with a simple filename')
    names = []
    if args.engine != 'sam':
        if not args.labels:
            raise ValueError('YOLO requires --labels labels.json in checkpoint class-ID order')
        names = json.loads(Path(args.labels).read_text(encoding='utf-8-sig'))
        if (not isinstance(names, list) or not names
                or any(not isinstance(name, str) or not name.strip() for name in names)
                or len(set(names)) != len(names)):
            raise ValueError('labels must be a nonempty JSON list of unique class names')
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.ultralytics_version):
        raise ValueError('ultralytics-version must be an exact version such as 8.4.184')
    target = Path(args.output).resolve() / args.name
    target.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).parent / 'nuclio'
    for filename in ('main.py', 'engines.py', 'geometry.py'):
        shutil.copy2(source / filename, target / filename)
    (target / 'weights').mkdir()
    shutil.copy2(weights, target / 'weights' / weights.name)
    config = {'engine': args.engine, 'task': args.task, 'weights': weights.name,
              'labels': names, 'gpu': args.gpu, 'imgsz': args.imgsz}
    (target / 'model.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    annotations = {'name': args.name, 'type': 'interactor' if args.engine == 'sam' else 'detector',
                   'spec': json.dumps([{'id': i, 'name': name,
                                       'type': 'mask' if args.task == 'segment' else 'rectangle'}
                                      for i, name in enumerate(names)], ensure_ascii=False)}
    if args.engine == 'sam':
        annotations.update(version='2', min_pos_points='1', min_neg_points='0',
                           startswith_box_optional='true',
                           help_message='Positive/negative clicks or box to segment one object')
    # Pin a CUDA build which retains support for the host's Turing GPU (sm_75).
    torch_index = 'cu118' if args.gpu else 'cpu'
    install = (
        'pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 '
        f'--index-url https://download.pytorch.org/whl/{torch_index} && '
        f'pip install --no-cache-dir ultralytics=={args.ultralytics_version} '
        'torch==2.5.1 torchvision==0.20.1'
    )
    if args.engine == 'yolov5':
        install = ('pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 "numpy<2" && '
                   'git clone --branch v7.0 --depth 1 https://github.com/ultralytics/yolov5.git /opt/yolov5 && '
                   'pip install --no-cache-dir -r /opt/yolov5/requirements.txt "numpy<2" '
                   'torch==2.5.1 torchvision==0.20.1')
    spec = {
        'description': f'Custom {args.engine} {args.task}: {args.name}',
        'runtime': 'python:3.11', 'handler': 'main:handler', 'eventTimeout': '120s',
        'readinessTimeoutSeconds': 180,
        'build': {'image': f'cvat.custom.{args.name}', 'baseImage': 'python:3.11-slim-bookworm',
                  'directives': {'preCopy': [
                      {'kind': 'RUN', 'value': 'apt-get -o Acquire::Retries=5 update && apt-get -o Acquire::Retries=5 install -y --no-install-recommends git libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*'},
                      {'kind': 'WORKDIR', 'value': '/opt/nuclio'},
                      {'kind': 'RUN', 'value': install}]}},
        'triggers': {'myHttpTrigger': {'kind': 'http', 'numWorkers': 1,
                      'workerAvailabilityTimeoutMilliseconds': 120000,
                      'attributes': {'maxRequestBodySize': 33554432}}},
        'platform': {'attributes': {'network': 'cvat_cvat', 'mountMode': 'volume',
                                    'restartPolicy': {'name': 'always', 'maximumRetryCount': 3}}},
    }
    if args.gpu:
        spec['resources'] = {'limits': {'nvidia.com/gpu': 1}}
        spec['env'] = [{'name': 'NVIDIA_VISIBLE_DEVICES', 'value': 'all'},
                       {'name': 'NVIDIA_DRIVER_CAPABILITIES', 'value': 'compute,utility'}]
    function = {'metadata': {'name': args.name, 'namespace': 'cvat', 'annotations': annotations},
                'spec': spec}
    # JSON is valid YAML and avoids a local PyYAML prerequisite.
    (target / 'function.yaml').write_text(json.dumps(function, indent=2, ensure_ascii=False), encoding='utf-8')
    return target


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--name', required=True)
    result.add_argument('--engine', required=True, choices=['ultralytics', 'yolov5', 'sam'])
    result.add_argument('--task', required=True, choices=['detect', 'segment', 'interactive'])
    result.add_argument('--weights', required=True)
    result.add_argument('--labels')
    result.add_argument('--gpu', action='store_true')
    result.add_argument('--imgsz', type=int, default=640)
    result.add_argument('--ultralytics-version', default='8.4.184')
    result.add_argument('--output', default=str(Path(__file__).parent / 'generated'))
    return result


if __name__ == '__main__':
    args = parser().parse_args()
    if args.imgsz < 32 or args.imgsz % 32:
        raise SystemExit('imgsz must be a positive multiple of 32')
    target = prepare(args)
    print(f'Prepared: {target}')
    print('Run in WSL with Docker integration (nuctl 1.16.3):')
    print('nuctl create project cvat --platform local')
    print(shlex.join(['nuctl', 'deploy', '--project-name', 'cvat', '--path', str(target),
                      '--file', str(target / 'function.yaml'), '--platform', 'local']))
