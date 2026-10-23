import base64
import io
import json
from pathlib import Path

from PIL import Image

def init_context(context):
    from engines import Engine

    config = json.loads(Path('/opt/nuclio/model.json').read_text())
    engine = Engine(config)
    context.user_data.engine = engine


def handler(context, event):
    data = event.body
    if isinstance(data, (bytes, str)):
        data = json.loads(data)
    image = Image.open(io.BytesIO(base64.b64decode(data['image']))).convert('RGB')
    result = context.user_data.engine.infer(image, data)
    return context.Response(body=json.dumps(result), headers={},
                            content_type='application/json', status_code=200)
