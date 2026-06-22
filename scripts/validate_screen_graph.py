"""
Screen-graph validator. Checks the flow is correct and trackable:
  - every next/prev points at a real screen
  - edges are bidirectionally consistent (A.next has B  <=>  B.prev has A)
  - seq is contiguous 1..N and agrees with meta.flow
  - the linear flow is fully traversable from the entry screen to a terminal
  - every concept referenced by a screen exists, and concept.appears_on is valid
  - reports app step_map coverage (which of the 9 backend steps have a screen)
"""
import json
from pathlib import Path

GRAPH = Path("data/figma/screen_graph.json")

APP_STEP_MAP = {
    1: "SIM Binding / Verification",
    2: "KYC & Video Verification",
    3: "Address Confirmation",
    4: "FD Amount & Tenure Selection",
    5: "Bank Details Addition",
    6: "Nominee Selection",
    7: "Final FD Review",
    8: "Payment Processing",
    9: "Success / Active FD View",
}


def main():
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    screens = {s["id"]: s for s in g["screens"]}
    concepts = g["concepts"]
    ids = set(screens)
    problems, warns = [], []

    # 1. edge targets exist
    for sid, s in screens.items():
        for e in ("next", "prev"):
            for t in s.get(e, []):
                if t not in ids:
                    problems.append(f"{sid}.{e} -> unknown screen '{t}'")

    # 2. bidirectional consistency
    for sid, s in screens.items():
        for nxt in s.get("next", []):
            if nxt in ids and sid not in screens[nxt].get("prev", []):
                problems.append(f"{sid}.next has {nxt} but {nxt}.prev is missing {sid}")
        for pv in s.get("prev", []):
            if pv in ids and sid not in screens[pv].get("next", []):
                problems.append(f"{sid}.prev has {pv} but {pv}.next is missing {sid}")

    # 3. seq contiguous + agrees with meta.flow
    seqs = [s.get("seq") for s in g["screens"]]
    if any(x is None for x in seqs):
        problems.append("some screens are missing 'seq'")
    else:
        if sorted(seqs) != list(range(1, len(seqs) + 1)):
            problems.append(f"seq not contiguous 1..N: {sorted(seqs)}")
        flow = g.get("meta", {}).get("flow", [])
        by_seq = [sid for sid, _ in sorted(screens.items(), key=lambda kv: kv[1]["seq"])]
        if flow != by_seq:
            problems.append(f"meta.flow {flow} != screens ordered by seq {by_seq}")

    # 4. traversable entry -> terminal following next
    entries = [sid for sid, s in screens.items() if not s.get("prev")]
    terminals = [sid for sid, s in screens.items() if not s.get("next")]
    if len(entries) != 1:
        warns.append(f"expected exactly 1 entry screen, found {entries}")
    if not terminals:
        problems.append("no terminal screen (flow never ends)")
    if entries:
        seen, cur, chain = set(), entries[0], []
        while cur and cur not in seen:
            seen.add(cur); chain.append(cur)
            nxts = screens[cur].get("next", [])
            cur = nxts[0] if nxts else None
        unreached = ids - seen
        if unreached:
            warns.append(f"screens not reachable on the happy path from {entries[0]}: {sorted(unreached)}")
        print(f"Happy path: {' -> '.join(chain)}")

    # 5. concept refs
    for sid, s in screens.items():
        for c in s.get("concepts", []):
            if c not in concepts:
                problems.append(f"{sid} references unknown concept '{c}'")
    for cid, c in concepts.items():
        for sref in c.get("appears_on", []):
            if sref not in ids:
                problems.append(f"concept '{cid}'.appears_on -> unknown screen '{sref}'")

    # 5b. error screens: appears_on must reference a real screen (or "any")
    errors = g.get("error_screens", [])
    for e in errors:
        for sref in e.get("appears_on", []):
            if sref != "any" and sref not in ids:
                problems.append(f"error '{e['id']}'.appears_on -> unknown screen '{sref}'")
        if not e.get("appears_on"):
            warns.append(f"error '{e['id']}' has no appears_on link")
    print(f"\nError screens: {len(errors)} (linked to journey via appears_on)")

    # 6. app step_map coverage
    covered = {}
    for sid, s in screens.items():
        for st in s.get("app_steps_covered", []) or ([s["app_step"]] if s.get("app_step") else []):
            covered.setdefault(st, []).append(sid)
    print("\nApp step_map coverage:")
    for st in sorted(APP_STEP_MAP):
        scr = covered.get(st, [])
        tag = "OK " if scr else "GAP"
        print(f"  [{tag}] step {st} {APP_STEP_MAP[st]:<35} -> {scr or '(no Figma screen)'}")

    print("\n" + ("PROBLEMS:" if problems else "No structural problems."))
    for p in problems:
        print("  X " + p)
    if warns:
        print("WARNINGS:")
        for w in warns:
            print("  ! " + w)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
