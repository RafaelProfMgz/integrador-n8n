import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/build_workflows.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class WorkflowBehavior(unittest.TestCase):
    def validate(self, payload, env=None):
        source = 'const $env = ' + json.dumps(env or {}) + ';\n'
        source += 'const $input = {first:()=>({json:' + json.dumps(payload) + '})};\n'
        source += 'const run = () => {\n' + builder.VALIDATE + '\n}; console.log(JSON.stringify(run()));'
        return subprocess.run(['node', '-e', source], capture_output=True, text=True)

    def content(self):
        return dict(platform='instagram', dry_run=True, approved=False, caption='Teste',
                    image_url='https://example.com/foto.jpg')

    def test_dry_run_needs_no_credentials(self):
        self.assertEqual(self.validate(self.content()).returncode, 0)

    def test_live_rejects_missing_approval(self):
        p = self.content(); p['dry_run'] = False
        self.assertIn('Aprovacao', self.validate(p).stderr)

    def test_live_rejects_placeholder_and_bad_version(self):
        p = self.content(); p.update(dry_run=False, approved=True)
        self.assertNotEqual(self.validate(p).returncode, 0)

    def test_string_false_cannot_enable_publishing(self):
        p = self.content(); p['dry_run'] = 'false'
        self.assertNotEqual(self.validate(p).returncode, 0)

    def test_rejects_local_media_and_long_caption(self):
        for changes in [dict(image_url='http://localhost/a.jpg'), dict(caption='x'*2201)]:
            p = self.content(); p.update(changes)
            self.assertNotEqual(self.validate(p).returncode, 0)

    def test_valid_live_configuration(self):
        p = self.content(); p.update(dry_run=False, approved=True, image_url='https://cdn.test/image.jpg')
        env = dict(META_INSTAGRAM_ACCOUNT_ID='123', META_GRAPH_VERSION='v99.0', META_INSTAGRAM_ACCESS_TOKEN='test-secret')
        result = self.validate(p, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('test-secret', result.stdout)
        env['META_INSTAGRAM_ACCESS_TOKEN'] = ''
        self.assertNotEqual(self.validate(p, env).returncode, 0)

    def test_instagram_does_not_publish_processing_container(self):
        workflow = builder.build('instagram')
        code = next(n['parameters']['jsCode'] for n in workflow['nodes'] if n['name'] == 'Exigir FINISHED')
        for status, expected in [('IN_PROGRESS',1), ('ERROR',1), ('FINISHED',0)]:
            source = "const $input={first:()=>({json:{status_code:"+json.dumps(status)+"}})}; const $=()=>({first:()=>({json:{id:'123'}})}); const run=()=>{"+code+"}; run();"
            result = subprocess.run(['node','-e',source], capture_output=True)
            self.assertEqual(result.returncode, expected)

    def test_templates_have_safe_defaults_and_valid_edges(self):
        for platform in ('facebook','instagram'):
            workflow = json.loads((ROOT/'workflows'/f'{platform}-photo.json').read_text())
            self.assertEqual(workflow,builder.build(platform))
            self.assertFalse(workflow['active'])
            names = {n['name'] for n in workflow['nodes']}
            for node in workflow['nodes']:
                self.assertNotIn('credentials', node)
                self.assertFalse(node.get('retryOnFail', False))
            for edge in workflow['connections'].values():
                for output in edge['main']:
                    for target in output: self.assertIn(target['node'], names)

if __name__ == '__main__': unittest.main()
