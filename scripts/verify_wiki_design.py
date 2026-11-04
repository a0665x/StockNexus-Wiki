#!/usr/bin/env python3
"""Offline design-fixture checks, not runtime compiler or financial validation.

Requires development-only jsonschema; never opens the news DB or calls a model.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'schema' / name).read_text())


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print('PASS: ' + description)


def main():
    schema = read('temporal-wiki.relation.schema.json')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    example = read('examples/temporal-wiki.relation.synthetic.json')
    validator.validate(example)
    check(example['is_fixture'], 'synthetic relation conforms to Draft 2020-12 schema')
    span = example['evidence_refs'][0]
    check(span['start'] == 0 and span['end'] == len(span['quote']) and
          hashlib.sha256(span['quote'].encode()).hexdigest() == span['content_hash'],
          'synthetic quote offsets and hash agree (no real DB reference check)')

    mutations = [
        ('CAUSES rejected', lambda x: x.update(relation_type='CAUSES')),
        ('unversioned evidence rejected', lambda x: x['evidence_refs'][0].pop('article_revision_id')),
        ('unsupported citation-free SUPPORTS rejected', lambda x: x.update(evidence_refs=[])),
        ('merged confidence rejected', lambda x: x['scores'].update(confidence=.9)),
        ('timezone-free timestamp rejected', lambda x: x.update(produced_at='2026-01-02T22:00:00')),
        ('wrong DEPENDS_ON direction rejected', lambda x: x.update(relation_type='DEPENDS_ON')),
        ('LLM cannot self-verify', lambda x: x.update(status='verified')),
        ('replay must carry simulated time', lambda x: x.update(simulated_effective_at=None)),
    ]
    for label, mutate in mutations:
        invalid = copy.deepcopy(example)
        mutate(invalid)
        check(bool(list(validator.iter_errors(invalid))), label)

    fixture = read('examples/temporal-wiki.returns.synthetic.json')
    check(fixture['is_fixture'], 'returns input explicitly synthetic')
    returns = [close / fixture['entry'] - 1 for close in fixture['closes']]
    for n in (1, 3):
        check(math.isclose(returns[n-1], fixture['expected'][f'terminal_return_{n}'], abs_tol=1e-12)
              and math.isclose(sum(returns[:n])/n, fixture['expected'][f'mean_path_return_{n}'], abs_tol=1e-12),
              f'contract arithmetic N={n}: terminal and path returns')
    analogs = fixture['analogs']
    weighted = sum(w*r for w, r in zip(analogs['weights'], analogs['terminal_returns'])) / sum(analogs['weights'])
    check(math.isclose(weighted, analogs['expected_mean_terminal_return'], abs_tol=1e-12),
          'contract arithmetic: weighted historical terminal return')
    forecast = read('examples/temporal-wiki.forecast.synthetic.json')
    check(forecast['is_fixture'] and forecast['signal']['action'] == 'INSUFFICIENT_EVIDENCE'
          and forecast['signal']['execution_enabled'] is False
          and all(forecast['forecast'][key] is None for key in ('p_up','p_down','p_neutral','expected_terminal_return')),
          'synthetic missing-evidence example does not invent a probability or enable execution')
    print('Design checks only. Runtime acceptance tests 1–20 remain pending.')


if __name__ == '__main__':
    main()
