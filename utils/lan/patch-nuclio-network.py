"""Patch the pinned CVAT image to invoke Nuclio by its Docker service name."""
import ast
from importlib.util import find_spec
from pathlib import Path
import sys


def patch_file(path):
    original = 'url = f"http://host.docker.internal:{func.port}"'
    replacement = '''url = f"http://nuclio-{settings.NUCLIO['FUNCTION_NAMESPACE']}-{func.id}:8080"'''
    source = path.read_text(encoding='utf-8')
    if source.count(original) != 1:
        raise ValueError('CVAT invocation implementation changed; review the LAN patch before building')
    patched = source.replace(original, replacement)
    ast.parse(patched)
    path.write_text(patched, encoding='utf-8')


if __name__ == '__main__':
    path = (Path(sys.argv[1]) if len(sys.argv) > 1 else
            Path(find_spec('cvat').origin).parent / 'apps/lambda_manager/views.py')
    patch_file(path)
