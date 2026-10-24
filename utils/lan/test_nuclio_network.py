"""Check that the LAN image patch routes each function to its own stable host."""
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patch_nuclio', HERE / 'patch-nuclio-network.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class NetworkPatchTests(unittest.TestCase):
    def test_routes_by_namespace_and_name_instead_of_stale_port(self):
        source = '''def route(func):
    url = f"http://host.docker.internal:{func.port}"
    return url
'''
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'views.py'
            target.write_text(source)
            patcher.patch_file(target)
            scope = {'settings': types.SimpleNamespace(NUCLIO={'FUNCTION_NAMESPACE': 'nuclio'})}
            exec(compile(target.read_text(), str(target), 'exec'), scope)
            for name in ['mobile-sam', 'sam2-1-tiny', 'sam-vit-b', 'yolo11n-demo']:
                for old_port in [54002, 62963, None]:
                    function = types.SimpleNamespace(id=name, port=old_port)
                    self.assertEqual(scope['route'](function), f'http://nuclio-nuclio-{name}:8080')

    def test_rejects_changed_upstream_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'views.py'
            for source in ['url = "different transport"',
                           'url = f"http://host.docker.internal:{func.port}"\n' * 2]:
                target.write_text(source)
                with self.assertRaises(ValueError):
                    patcher.patch_file(target)
                self.assertEqual(target.read_text(), source)


if __name__ == '__main__':
    unittest.main()
