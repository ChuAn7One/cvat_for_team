"""Create the local annotation workspace; does not invite or message anyone."""
import json
from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
module = runpy.run_path(str(here / 'verify-demo.py'))
request = module['request']
credentials = module['credentials']
request('/api/auth/login', {'username': credentials['username'], 'password': credentials['password']})
response = request('/api/organizations?search=annotation-team')
org = next((item for item in response['results'] if item['slug'] == 'annotation-team'), None)
if org is None:
    org = request('/api/organizations', {'slug': 'annotation-team', 'name': '标注团队'})
state_path = here / '.demo-state.json'
if state_path.exists():
    state = json.loads(state_path.read_text())
    task_id = state['task_id']
    task = request(f'/api/tasks/{task_id}')
    if task.get('organization') != org['id']:
        request(f'/api/tasks/{task_id}', {'organization_id': org['id']}, method='PATCH')
team_state = {'organization_id': org['id'], 'slug': org['slug'], 'name': org['name']}
(here / '.team-state.json').write_text(json.dumps(team_state, ensure_ascii=False), encoding='utf-8')
print(json.dumps(team_state, ensure_ascii=False))
