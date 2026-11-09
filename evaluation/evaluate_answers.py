"""Evaluate saved AI result fixtures without calling a live LLM.

Input: evaluation/answer_results.json, one object per dataset query with
sources, expected_sources, answer_claims_supported (boolean), and
escalation_expected/escalation_required booleans. This deliberately refuses
 to invent metrics when no executed answer results are supplied.
"""
import json
from pathlib import Path
source=Path(__file__).with_name('answer_results.json')
if not source.exists():
    raise SystemExit('No answer_results.json found. Export actual AI outputs and human-reviewed labels first; no metrics calculated.')
rows=json.loads(source.read_text())
if not rows:
    raise SystemExit('answer_results.json is empty; no metrics calculated.')
citation_total=sum(len(r.get('sources',[])) for r in rows)
citation_valid=sum(1 for r in rows for s in r.get('sources',[]) if s in r.get('retrieved_sources',[]))
report={
 'evaluated_answers':len(rows),
 'citation_validity':citation_valid/citation_total if citation_total else None,
 'answer_groundedness':sum(bool(r.get('answer_claims_supported')) for r in rows)/len(rows),
 'escalation_accuracy':sum(bool(r.get('escalation_expected'))==bool(r.get('escalation_required')) for r in rows)/len(rows),
 'labeling_note':'Groundedness and escalation metrics require human-reviewed labels.'
}
out=Path(__file__).with_name('answer_evaluation_report.json');out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
