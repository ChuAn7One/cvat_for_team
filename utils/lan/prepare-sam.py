"""Download checksum-pinned official SAM presets into separate local folders."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RELEASE = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/'


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def download(model):
    directory = HERE / 'models' / model['name']
    weights = directory / 'weights' / model['filename']
    weights.parent.mkdir(parents=True, exist_ok=True)
    url = RELEASE + model['filename']
    if weights.exists():
        if weights.stat().st_size != model['size'] or checksum(weights) != model['sha256']:
            raise ValueError(f'Existing weight failed verification; inspect it before retrying: {weights}')
    else:
        partial = weights.with_suffix(weights.suffix + '.part')
        print(f'Downloading {model["name"]}: {url}', flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as stream:
            downloaded = 0
            next_progress = 32 * 1024 * 1024
            for block in iter(lambda: response.read(1024 * 1024), b''):
                stream.write(block)
                downloaded += len(block)
                if downloaded >= next_progress:
                    print(f'{model["name"]}: {downloaded // (1024 * 1024)} MiB', flush=True)
                    next_progress += 32 * 1024 * 1024
        if partial.stat().st_size != model['size'] or checksum(partial) != model['sha256']:
            raise ValueError(f'Download failed verification: {partial}')
        partial.replace(weights)
    (directory / 'source.json').write_text(json.dumps({**model, 'url': url}, indent=2), encoding='utf-8')
    print(f'Verified {model["name"]}: {weights}', flush=True)
    return weights


def main():
    models = json.loads((HERE / 'sam-models.json').read_text(encoding='utf-8'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', choices=[model['name'] for model in models],
                        default=[model['name'] for model in models])
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    for model in models:
        if model['name'] not in args.models:
            continue
        weights = download(model)
        if args.download_only:
            continue
        target = ROOT / 'serverless/custom-models/generated' / model['name']
        if target.exists():
            expected = {'engine': 'sam', 'task': 'interactive', 'weights': weights.name,
                        'labels': [], 'gpu': model['gpu'], 'imgsz': 640}
            if json.loads((target / 'model.json').read_text()) != expected:
                raise ValueError(f'Existing deployment configuration differs: {target}')
            if checksum(target / 'weights' / weights.name) != model['sha256']:
                raise ValueError(f'Existing deployment weight differs: {target}')
            print(f'Using existing build directory: {target}', flush=True)
            continue
        command = [sys.executable, str(ROOT / 'serverless/custom-models/prepare.py'),
                   '--name', model['name'], '--engine', 'sam', '--task', 'interactive',
                   '--weights', str(weights)]
        if model['gpu']:
            command.append('--gpu')
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
