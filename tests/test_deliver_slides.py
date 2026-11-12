import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'orgchart' / 'scripts'))
import deliver_slides as d


class Fake:
    def __init__(self, slides, fail_on=None):
        self.slides, self.posts, self.fail_on = list(slides), [], fail_on
    def __call__(self, method, url, token, body=None):
        assert token == 't'
        if method == 'GET':
            return {'slides': [{'objectId': s} for s in self.slides]}
        self.posts.append(body['requests'])
        first = body['requests'][0]
        if self.fail_on and 'createSlide' in first and first['createSlide']['objectId'] == self.fail_on:
            raise d.SlidesError('HTTP 500')
        for r in body['requests']:
            if 'createSlide' in r: self.slides.append(r['createSlide']['objectId'])
            if 'deleteObject' in r and r['deleteObject']['objectId'] in self.slides: self.slides.remove(r['deleteObject']['objectId'])
            if 'updateSlidesPosition' in r:
                sid = r['updateSlidesPosition']['slideObjectIds'][0]; self.slides.remove(sid)
                self.slides.insert(r['updateSlidesPosition']['insertionIndex'], sid)
        return {}


def make(directory, ids):
    files = []
    for i, sid in enumerate(ids, 1):
        name = f'page-{i:03d}.json'
        (Path(directory) / name).write_text(json.dumps([{'createSlide': {'objectId': sid}}, {'insertText': {'objectId': sid, 'text': 'x'}}]))
        files.append({'file': name, 'request_count': 2})
    (Path(directory) / 'cleanup.json').write_text(json.dumps([{'deleteObject': {'objectId': 'tmpl1'}}, {'deleteObject': {'objectId': 'tmpl2'}}]))
    (Path(directory) / 'manifest.json').write_text(json.dumps({'files': files, 'cleanup': {'file': 'cleanup.json', 'request_count': 2}}))


class DeliverTests(unittest.TestCase):
    def test_sends_missing_pages_reorders_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            make(tmp, ['pageA', 'pageB', 'pageC'])
            fake = Fake(['tmpl1', 'tmpl2', 'pageC'])
            result = d.deliver(tmp, 'p', 't', transport=fake, log=lambda *_: None)
            self.assertEqual(result['skipped'], ['page-003.json'])
            self.assertEqual(fake.slides, ['pageA', 'pageB', 'pageC'])
            self.assertTrue(result['cleanup'])

    def test_failure_stops_before_cleanup_and_names_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            make(tmp, ['pageA', 'pageB'])
            fake = Fake(['tmpl1'], fail_on='pageB')
            with self.assertRaises(d.SlidesError) as ctx:
                d.deliver(tmp, 'p', 't', transport=fake, log=lambda *_: None)
            self.assertIn('page-002.json', str(ctx.exception))
            self.assertIn('tmpl1', fake.slides)

    def test_rerun_after_success_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            make(tmp, ['pageA'])
            fake = Fake(['pageA'])
            result = d.deliver(tmp, 'p', 't', transport=fake, log=lambda *_: None)
            self.assertEqual(result['sent'], [])
            self.assertEqual(fake.posts, [])

    def test_missing_token_exits_2(self):
        import os
        os.environ.pop('ORGCHART_SLIDES_TOKEN', None)
        self.assertEqual(d.main(['x', '--presentation-id', 'p']), 2)


if __name__ == '__main__':
    unittest.main()
