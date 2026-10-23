"""Prepare the downloaded official YOLO11n demo and its exact COCO labels."""
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
models = root / 'utils/lan/models/yolo11n-demo'
text = (models / 'coco.yaml').read_text(encoding='utf-8')
names = {}
for match in re.finditer(r'^  (\d+):\s*(.+?)\s*$', text, re.MULTILINE):
    names[int(match[1])] = match[2].strip('"\'')
if set(names) != set(range(80)):
    raise ValueError('Downloaded COCO metadata must contain class IDs 0 through 79')
labels = models / 'labels.json'
labels.write_text(json.dumps([names[index] for index in range(80)]), encoding='utf-8')
target = root / 'serverless/custom-models/generated/yolo11n-demo'
if target.exists():
    print(f'Using existing demo build directory: {target}')
    sys.exit(0)
subprocess.run([
    sys.executable, str(root / 'serverless/custom-models/prepare.py'),
    '--name', 'yolo11n-demo', '--engine', 'ultralytics', '--task', 'detect',
    '--weights', str(models / 'weights/yolo11n.pt'), '--labels', str(labels), '--gpu',
], check=True)
