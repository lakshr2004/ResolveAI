"""Run retrieval evaluation against indexed documents; metrics are computed from live Qdrant results."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.vector_store import search_chunks

dataset=json.loads(Path(__file__).with_name("evaluation_dataset.json").read_text())
precisions=[]; recalls=[]; reciprocal=[]
for item in dataset:
    hits=search_chunks(item["question"],limit=5)
    retrieved={h["document_name"] for h in hits}
    relevant=set(item["relevant_documents"])
    relevant_rank=next((i+1 for i,h in enumerate(hits) if h["document_name"] in relevant),None)
    precisions.append(len(retrieved & relevant)/5)
    recalls.append(len(retrieved & relevant)/len(relevant))
    reciprocal.append(1/relevant_rank if relevant_rank else 0)
report={"queries":len(dataset),"precision_at_5":sum(precisions)/len(precisions),
        "recall_at_5":sum(recalls)/len(recalls),"mrr":sum(reciprocal)/len(reciprocal),
        "note":"Metrics are from current Qdrant contents; empty or unindexed collections produce zero scores."}
out=Path(__file__).with_name("retrieval_report.json")
out.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
