import unittest, logging
logging.basicConfig(level=logging.WARN)
logging.getLogger('rdflib').setLevel(logging.WARN)

from queryparams import queryFromParams

class TestQueryFromParams(unittest.TestCase):
    def test_transforms_simple_params(self):
        self.assertDictEqual(
            {
                'filter': {
                    'type': 'image',
                    'withoutTags': ['nsfw'],
                    'onlyTagged': ['t1'],
                },
                'paging': {
                    'limit': 2,
                    'skip': 3,
                },
            },
            queryFromParams(dict(
                type='image',
                onlyTagged='t1',
                limit='2',
                skip='3',
            ).items()))
        
    def test_tag_is_repeatable(self):
        tt = lambda p: queryFromParams(p).get('filter', {}).get('tags', None)
        self.assertEqual(None, tt([('tag', '')]))
        self.assertEqual(['t1'], tt([('tag', 't1')]))
        self.assertEqual(['t1', 't2'], tt([('tag', 't1'), ('tag', 't2')]))
        
    def test_withoutTag_is_repeatable(self):
        wt = lambda p: queryFromParams(
            p).get('filter', {}).get('withoutTags', None)
        self.assertEqual(['nsfw'], wt([]))
        self.assertEqual(['nsfw'], wt([('withoutTag', '')]))
        self.assertEqual(['nsfw', 't1'], wt([('withoutTag', 't1')]))
        
    def test_hidden_none_removes_default_tags(self):
        wt = lambda p: queryFromParams(
            p).get('filter', {}).get('withoutTags', None)
        self.assertEqual(None, wt([('hidden', 'none')]))

    def test_errors_on_unknown_key(self):
        self.assertRaises(ValueError, queryFromParams, [('foo', '1')])

    def test_errors_on_improper_hidden(self):
        self.assertRaises(ValueError, queryFromParams, [('hidden', 'foo')])

    def test_errors_on_unknown_type(self):
        self.assertRaises(ValueError, queryFromParams, [('type', 'foo')])

    def test_parses_random(self):
        self.assertEqual([{'random': 0}],
                         queryFromParams([('sort', 'random')])['sort'])
        self.assertEqual([{'random': 123}],
                         queryFromParams([('sort', 'random+123')])['sort'])
