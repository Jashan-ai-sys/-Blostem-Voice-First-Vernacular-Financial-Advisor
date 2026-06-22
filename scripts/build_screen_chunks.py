"""
Screen knowledge-graph → retrieval chunks.
Turns data/figma/screen_graph.json into JSONL chunks in the SAME schema as
data/chunks/retrieval_chunks.jsonl (chunk_id / text / metadata), so the existing
hybrid retrieval (BM25 + Pinecone) can surface screen-aware answers.

- One "screen" chunk per UI screen (purpose + fields + actions + FAQs + concepts).
- One "concept" chunk per financial term (definition + where it appears).

Writes a standalone file for inspection AND merges into the canonical corpus,
replacing any prior screen_graph chunks (idempotent — safe to re-run).
"""
import json
from pathlib import Path

GRAPH = Path("data/figma/screen_graph.json")
STANDALONE = Path("data/chunks/screen_graph_chunks.jsonl")
CORPUS = Path("data/chunks/retrieval_chunks.jsonl")
DOC_TYPE = "screen_graph"
SOURCE = "figma_screen_graph"


def _names(ids: list, screens: dict) -> str:
    return ", ".join(screens[i]["name"] for i in ids if i in screens) or "—"


def screen_text(s: dict, concepts: dict, screens: dict, total: int, errors: list) -> str:
    prev_n = _names(s.get("prev", []), screens)
    next_n = _names(s.get("next", []), screens)
    # Errors that can appear here: those scoped to this screen + global ("any").
    here = [e["title"] for e in errors
            if s["id"] in e.get("appears_on", []) or e.get("appears_on") == ["any"]]
    lines = [
        f"# Screen: {s['name']} ({s['app_step_label']})",
        f"Also known as: {', '.join(s.get('aliases', []))}.",
        "",
        f"Purpose: {s['purpose']}",
        f"What the user does here: {s['what_user_does']}",
        "",
        f"Journey position: step {s['seq']} of {total} in the FD booking flow. "
        f"Previous screen: {prev_n}. Next screen: {next_n}.",
    ]
    if here:
        lines.append("Possible errors on this screen: " + ", ".join(here) + ".")
    if s.get("fields"):
        lines.append("\nFields on this screen:")
        lines += [f"- {f['label']}: {f['desc']}" for f in s["fields"]]
    if s.get("actions"):
        lines.append("\nActions / buttons:")
        lines += [f"- {a['label']}: {a['desc']}" for a in s["actions"]]
    if s.get("concepts"):
        names = [concepts[c]["term"] for c in s["concepts"] if c in concepts]
        lines.append("\nRelated concepts: " + ", ".join(names) + ".")
    if s.get("faqs"):
        lines.append("\nCommon questions on this screen:")
        for fq in s["faqs"]:
            lines.append(f"Q: {fq['q']}\nA: {fq['a']}")
    return "\n".join(lines)


def concept_text(c: dict) -> str:
    lines = [
        f"# Term: {c['term']}",
        f"Also called: {', '.join(c.get('aliases', []))}.",
        "",
        c["definition"],
    ]
    if c.get("appears_on"):
        lines.append("\nShown on screens: " + ", ".join(c["appears_on"]) + ".")
    return "\n".join(lines)


def _appears_on_names(ids: list, screens: dict) -> str:
    if not ids or ids == ["any"]:
        return "any screen in the FD journey"
    return ", ".join(screens[i]["name"] for i in ids if i in screens) or "—"


def error_text(e: dict, screens: dict) -> str:
    lines = [
        f"# Error screen: {e['title']}",
        f"Also said as: {', '.join(e.get('aliases', []))}.",
        "",
        f"On-screen message: {e['message']}",
        f"When it appears: {e.get('triggers', '')}",
        f"Appears on: {_appears_on_names(e.get('appears_on', []), screens)}.",
        f"What to tell the user / what to do: {e['what_to_do']}",
    ]
    if e.get("actions"):
        lines.append("Buttons: " + ", ".join(e["actions"]) + ".")
    return "\n".join(lines)


def build() -> list[dict]:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    concepts = graph["concepts"]
    screens = {s["id"]: s for s in graph["screens"]}
    errors = graph.get("error_screens", [])
    total = len(graph["screens"])
    chunks = []

    for s in graph["screens"]:
        chunks.append({
            "chunk_id": f"screen__{s['id']}",
            "text": screen_text(s, concepts, screens, total, errors),
            "metadata": {
                "source": SOURCE,
                "chunk_type": "screen",
                "doc_type": DOC_TYPE,
                "screen_id": s["id"],
                "figma_node_id": s["figma_node_id"],
                "seq": s["seq"],
                "app_step": s["app_step"],
                "app_step_label": s["app_step_label"],
                "prev": s.get("prev", []),
                "next": s.get("next", []),
            },
        })

    for cid, c in concepts.items():
        chunks.append({
            "chunk_id": f"concept__{cid}",
            "text": concept_text(c),
            "metadata": {
                "source": SOURCE,
                "chunk_type": "concept",
                "doc_type": DOC_TYPE,
                "concept_id": cid,
            },
        })

    for e in errors:
        chunks.append({
            "chunk_id": f"error__{e['id']}",
            "text": error_text(e, screens),
            "metadata": {
                "source": SOURCE,
                "chunk_type": "error_screen",
                "doc_type": DOC_TYPE,
                "error_id": e["id"],
                "figma_node_id": e.get("figma_node_id"),
                "appears_on": e.get("appears_on", []),
                "copy_source": e.get("copy_source"),
            },
        })
    return chunks


def merge_into_corpus(new_chunks: list[dict]) -> tuple[int, int]:
    """Append new chunks to the canonical corpus, dropping any prior screen_graph
    chunks first so re-runs replace rather than duplicate."""
    existing = []
    if CORPUS.exists():
        for line in CORPUS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("metadata", {}).get("doc_type") == DOC_TYPE:
                continue  # drop old screen-graph chunks
            existing.append(row)
    merged = existing + new_chunks
    with CORPUS.open("w", encoding="utf-8") as fh:
        for row in merged:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(existing), len(new_chunks)


def main():
    chunks = build()
    with STANDALONE.open("w", encoding="utf-8") as fh:
        for row in chunks:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    kept, added = merge_into_corpus(chunks)
    n_screen = sum(1 for c in chunks if c["metadata"]["chunk_type"] == "screen")
    n_concept = sum(1 for c in chunks if c["metadata"]["chunk_type"] == "concept")
    n_error = sum(1 for c in chunks if c["metadata"]["chunk_type"] == "error_screen")
    print(f"Built {len(chunks)} chunks ({n_screen} screens, {n_concept} concepts, {n_error} error screens)")
    print(f"  standalone -> {STANDALONE}")
    print(f"  corpus     -> {CORPUS}  ({kept} existing kept + {added} screen-graph added)")


if __name__ == "__main__":
    main()
