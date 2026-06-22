"""
OKF PRODUCER — convert the curated screen knowledge graph into a conformant Open
Knowledge Format bundle (markdown + YAML frontmatter, cross-linked).

Input:  data/figma/screen_graph.json  (8 screens, 21 concepts, 14 error screens)
Output: data/okf/                      (an OKF bundle)
  index.md
  screens/{index.md, <id>.md}      type: Screen
  concepts/{index.md, <id>.md}     type: Concept
  errors/{index.md, <id>.md}       type: Error Screen

Concepts cross-link to the screens they appear on and vice-versa (markdown links =
the OKF knowledge graph). Run:  python scripts/build_okf_from_screen_graph.py
Then the bundle is consumable via app.okf.okf_to_chunks("data/okf").
"""
import datetime
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(ROOT, "data", "figma", "screen_graph.json")
OUT = os.path.join(ROOT, "data", "okf")
TS = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def frontmatter(d: dict) -> str:
    body = yaml.safe_dump(d, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{body}\n---\n"


def write(relpath: str, fm: dict, body: str) -> None:
    path = os.path.join(OUT, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter(fm) + "\n" + body.strip() + "\n")


def link(label: str, rel: str) -> str:
    return f"[{label}]({rel})"


def build():
    g = json.load(open(GRAPH, encoding="utf-8"))
    screens = g.get("screens", [])
    concepts = g.get("concepts", {})
    errors = g.get("error_screens", [])

    # name lookups for friendly link labels
    screen_name = {s["id"]: s.get("name", s["id"]) for s in screens}
    concept_name = {cid: c.get("term", cid) for cid, c in concepts.items()}
    # reverse map: concept -> screens it appears on (from concept.appears_on)
    err_appears = {}
    for e in errors:
        for sid in (e.get("appears_on") or []):
            err_appears.setdefault(sid, []).append(e)

    # ── Screens ──────────────────────────────────────────────────────────────
    for s in screens:
        sid = s["id"]
        b = []
        if s.get("what_user_does"):
            b.append(f"**What the user does:** {s['what_user_does']}\n")
        if s.get("fields"):
            b.append("## Fields\n")
            b.append("| Field | Detail |\n|---|---|")
            for f in s["fields"]:
                b.append(f"| {f.get('label','')} | {f.get('desc','')} |")
            b.append("")
        if s.get("actions"):
            b.append("## Actions\n")
            for a in s["actions"]:
                b.append(f"- **{a.get('label','')}** — {a.get('desc','')}")
            b.append("")
        if s.get("concepts"):
            b.append("## Concepts\n")
            for cid in s["concepts"]:
                b.append(f"- {link(concept_name.get(cid, cid), f'../concepts/{cid}.md')}")
            b.append("")
        if s.get("faqs"):
            b.append("## FAQs\n")
            for qa in s["faqs"]:
                b.append(f"**Q: {qa.get('q','')}**\n\n{qa.get('a','')}\n")
        # flow
        flow = []
        for pid in (s.get("prev") or []):
            flow.append(f"- Previous: {link(screen_name.get(pid, pid), f'{pid}.md')}")
        for nid in (s.get("next") or []):
            flow.append(f"- Next: {link(screen_name.get(nid, nid), f'{nid}.md')}")
        if flow:
            b.append("## Flow\n")
            b.extend(flow)
            b.append("")
        # errors that can appear here
        errs = err_appears.get(sid) or err_appears.get("any") or []
        if errs:
            b.append("## Possible errors here\n")
            for e in errs:
                eid_ = e["id"]
                b.append("- " + link(e.get("title", eid_), f"../errors/{eid_}.md"))
            b.append("")

        tags = ["screen", "journey"]
        if s.get("seq"):
            tags.append(f"step-{s['seq']}")
        write(f"screens/{sid}.md", {
            "type": "Screen",
            "title": s.get("name", sid),
            "description": s.get("purpose", ""),
            "tags": tags + (s.get("aliases") or [])[:4],
            "timestamp": TS,
        }, "\n".join(b))

    # ── Concepts ─────────────────────────────────────────────────────────────
    for cid, c in concepts.items():
        b = [c.get("definition", ""), ""]
        appears = c.get("appears_on") or []
        if appears:
            b.append("## Appears on\n")
            for sid in appears:
                b.append(f"- {link(screen_name.get(sid, sid), f'../screens/{sid}.md')}")
        write(f"concepts/{cid}.md", {
            "type": "Concept",
            "title": c.get("term", cid),
            "description": (c.get("definition", "") or "")[:200],
            "tags": ["concept"] + (c.get("aliases") or [])[:5],
            "timestamp": TS,
        }, "\n".join(b))

    # ── Error screens ────────────────────────────────────────────────────────
    for e in errors:
        eid = e["id"]
        b = []
        if e.get("message"):
            b.append(f"**Message:** {e['message']}\n")
        if e.get("what_to_do"):
            b.append(f"**What to do:** {e['what_to_do']}\n")
        if e.get("actions"):
            b.append("**Actions:** " + ", ".join(e["actions"]) + "\n")
        if e.get("triggers"):
            b.append(f"**Triggers:** {e['triggers']}\n")
        appears = e.get("appears_on") or []
        if appears and appears != ["any"]:
            b.append("## Appears on\n")
            for sid in appears:
                b.append(f"- {link(screen_name.get(sid, sid), f'../screens/{sid}.md')}")
        elif appears == ["any"]:
            b.append("_Global — can appear on any screen._")
        write(f"errors/{eid}.md", {
            "type": "Error Screen",
            "title": e.get("title", eid),
            "description": e.get("message", ""),
            "tags": ["error"],
            "timestamp": TS,
        }, "\n".join(b))

    # ── Index files (progressive disclosure) ─────────────────────────────────
    def index(relpath, title, desc, items):
        body = "\n".join(f"- {link(lbl, rel)}" for lbl, rel in items)
        write(relpath, {"type": "Index", "title": title, "description": desc, "timestamp": TS}, body)

    index("screens/index.md", "Screens", "FD onboarding journey screens.",
          [(s.get("name", s["id"]), f"{s['id']}.md") for s in screens])
    index("concepts/index.md", "Concepts", "Financial terms used across the journey.",
          [(c.get("term", cid), f"{cid}.md") for cid, c in concepts.items()])
    index("errors/index.md", "Error Screens", "Runtime errors and their remedies.",
          [(e.get("title", e["id"]), f"{e['id']}.md") for e in errors])
    index("index.md", g.get("meta", {}).get("name", "Blostem Knowledge"),
          g.get("meta", {}).get("purpose", "FD advisor knowledge bundle (OKF)."),
          [("Screens", "screens/index.md"), ("Concepts", "concepts/index.md"), ("Error Screens", "errors/index.md")])

    n = len(screens) + len(concepts) + len(errors) + 4
    print(f"[okf] wrote {n} files to {OUT}")
    print(f"[okf]   screens={len(screens)}  concepts={len(concepts)}  errors={len(errors)}  + 4 index files")


if __name__ == "__main__":
    build()
