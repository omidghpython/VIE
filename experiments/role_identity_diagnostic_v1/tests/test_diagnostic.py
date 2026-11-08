import copy
import json
from pathlib import Path
import unittest

from role_identity_diagnostic import diagnose

FIXTURES = json.loads((Path(__file__).parent / 'fixtures.json').read_text(encoding='utf-8'))


class DiagnosticTests(unittest.TestCase):
    def test_labeled_synthetic_cases(self):
        for case in FIXTURES:
            with self.subTest(case=case['id']):
                result = diagnose(case['question'], case['plan'])
                self.assertEqual(result['status'], case['expected_status'])
                self.assertEqual(result['reason'], case['expected_reason'])
                self.assertTrue(result['advisory_only'])

    def test_inputs_never_mutated(self):
        for case in FIXTURES:
            before = copy.deepcopy(case)
            diagnose(case['question'], case['plan'])
            self.assertEqual(case, before)

    def test_case_and_whitespace_do_not_change_findings(self):
        for case in FIXTURES:
            if not isinstance(case['question'], str):
                continue
            changed = copy.deepcopy(case)
            changed['question'] = '  ' + changed['question'].upper().replace(' ', '\n ') + '  '
            self.assertEqual(diagnose(changed['question'], changed['plan']),
                             diagnose(case['question'], case['plan']))

    def test_entity_renaming_does_not_change_findings(self):
        for case in FIXTURES:
            changed = json.loads(json.dumps(case).replace('The Lantern', 'A Distant Shore'))
            self.assertEqual(diagnose(changed['question'], changed['plan']),
                             diagnose(case['question'], case['plan']))

    def test_node_storage_order_does_not_change_findings(self):
        for case in FIXTURES:
            if not isinstance(case['plan'], dict):
                continue
            changed = copy.deepcopy(case['plan'])
            changed['nodes'].reverse()
            self.assertEqual(diagnose(case['question'], changed),
                             diagnose(case['question'], case['plan']))

    def test_bad_graph_field_types_abstain_without_crashing(self):
        case = FIXTURES[0]
        for field, value in [('answer_type', []), ('id', []), ('question', None), ('dependencies', [])]:
            p = copy.deepcopy(case['plan'])
            p['nodes'][0][field] = value
            self.assertEqual(diagnose(case['question'], p)['status'], 'unknown')
        for value in [[], {}, None, 2]:
            p = copy.deepcopy(case['plan'])
            p['final'] = value
            self.assertEqual(diagnose(case['question'], p)['status'], 'unknown')

    def test_duplicate_ids_and_wrong_dependency_types_abstain(self):
        case = FIXTURES[1]
        p = copy.deepcopy(case['plan'])
        p['nodes'][0]['id'] = 'q2'
        self.assertEqual(diagnose(case['question'], p)['status'], 'unknown')
        p = copy.deepcopy(case['plan'])
        p['nodes'][-1]['dependencies']['q1'] = 'work'
        self.assertEqual(diagnose(case['question'], p)['status'], 'unknown')

    def test_negated_filter_not_treated_as_both_roles(self):
        case = copy.deepcopy(next(c for c in FIXTURES if c['id'] == 'candidate_filter'))
        case['plan']['nodes'][-1]['question'] = 'Which person among {{q1}} is not a composer?'
        self.assertEqual(diagnose(case['question'], case['plan'])['status'], 'unknown')

    def test_different_person_leaves_are_not_enough_to_flag(self):
        case = copy.deepcopy(FIXTURES[1])
        case['plan']['nodes'][1]['question'] = 'Which director was credited for The Lantern?'
        self.assertEqual(diagnose(case['question'], case['plan'])['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
