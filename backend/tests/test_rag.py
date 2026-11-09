from app.rag.chunking import chunk_text
from app.services.llm_service import _json_object

def test_chunk_overlap_and_ids():
    words=" ".join(f"word{i}" for i in range(30))
    chunks=chunk_text(words,chunk_size=10,overlap=2)
    assert len(chunks)==4
    assert chunks[0]["chunk_id"]=="chunk_0001"
    assert chunks[0]["text"].split()[-2:]==chunks[1]["text"].split()[:2]

def test_json_parser_accepts_fenced_json():
    assert _json_object('```json\n{"ok":true}\n```')=={"ok":True}

def test_json_parser_rejects_non_json():
    try: _json_object("not json")
    except ValueError: return
    assert False, "Expected malformed JSON to fail"
