from pathlib import Path
import json, re, shutil, subprocess, tomllib

config = tomllib.loads(Path('.codex/config.toml').read_text(encoding='utf-8'))
assert config['model'] == 'gpt-6.1-sol'
assert config['agents']['max_concurrent_threads_per_session'] == 10
assert not ({'model_provider','model_providers','openai_base_url','model_catalog_json'} & set(config))
expected = {
 'architect': ('ccs-zhipu/glm-5.3','high','架构师'),
 'implementer': ('ccs-zhipu/glm-5.3','high','工程师'),
 'qa': ('ccs-minimax/MiniMax-M3.1-Flash','high','验收工程师'),
 'reviewer': ('ccs-minimax/MiniMax-M3','high','独立审查员'),
 'docs': ('ccs-minimax/MiniMax-M3.1-Flash','high','使用文档工程师'),
 'integrator': ('ccs-zhipu/glm-5.3','high','集成工程师'),
}
codex = shutil.which('codex')
if not codex:
    raise SystemExit('FAIL: codex must be available on PATH for verify_roles.py')
version = subprocess.check_output([codex, '--version'], text=True).strip()
assert version == 'codex-cli 0.154.0', f'expected PATH codex-cli 0.154.0, got {version}'
files = sorted(Path('.codex/agents').glob('*.toml'))
assert len(files) == len(expected) == 6
catalog = json.loads(subprocess.check_output([codex,'debug','models']).decode('utf-8'))
efforts = {m['slug']: {x['effort'] for x in m['supported_reasoning_levels']} for m in catalog['models']}
for path in files:
    role = tomllib.loads(path.read_text(encoding='utf-8'))
    assert set(role) == {'name','description','developer_instructions','model','model_reasoning_effort'}
    assert role['name'] == path.stem and role['name'] in expected
    model, effort, chinese = expected[role['name']]
    assert (role['model'],role['model_reasoning_effort']) == (model,effort)
    assert f'中文名：{chinese}' in role['description']
    assert role['developer_instructions'].startswith(f'对外角色：{chinese}。')
    assert role['model'] in efforts and effort in efforts[role['model']]
assert expected['reviewer'][0] == 'ccs-minimax/MiniMax-M3'
print(f'PASS {version} at {codex}: 6 reusable roles, model slugs, efforts, minimal fields')