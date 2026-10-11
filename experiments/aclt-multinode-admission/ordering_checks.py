import itertools
import pathlib


def _expected(order):
    state = {
        "failed": False,
        "conflict": False,
        "accepted": False,
        "receipt": None,
        "accepted_digest": None,
    }
    expected = []
    for event in order:
        status = None
        receipt = None
        if event == "wrong-ticket":
            status = "rejected"
        elif state["failed"]:
            status = "rejected"
        elif not state["accepted"] and event == "bad":
            status = "invalid"
            state["failed"] = True
        elif not state["accepted"] and event in ("good", "repeat"):
            status = "accepted"
            receipt = ("receipt", "GOOD")
            state["accepted"] = True
            state["accepted_digest"] = "GOOD"
            if state["receipt"] is None:
                state["receipt"] = receipt
        elif state["accepted"] and event in ("good", "repeat"):
            status = "duplicate"
            receipt = state["receipt"]
        elif state["accepted"] and event == "bad":
            status = "conflict"
            receipt = state["receipt"]
            state["conflict"] = True
        expected.append((event, status, receipt, dict(state)))
    return expected


def run_checks(Store, root: pathlib.Path) -> list:
    boot = "00000000-0000-0000-0000-000000000000"
    events = ["good", "repeat", "bad", "wrong-ticket"]
    results = []
    for i, order in enumerate(itertools.permutations(events)):
        path = root / f"case-{i}.sqlite"
        store = Store.create(str(path), "frozen")
        reservation=store.reserve("claim", "A", boot)
        status, ticket=reservation["status"],reservation["ticket"]
        actual_receipt=None
        assert status == "reserved", (i, "reserve status", status)
        assert ticket is not None, (i, "reserve ticket")

        expected = _expected(order)
        for step, (event, exp_status, exp_receipt, exp_state) in enumerate(expected):
            if event == "wrong-ticket":
                digest, valid, use_ticket = "GOOD", True, "invalid"
            elif event == "good" or event == "repeat":
                digest, valid, use_ticket = "GOOD", True, ticket
            else:
                digest, valid, use_ticket = "BAD", False, ticket

            out = store.submit("claim", "A", boot, use_ticket, digest, valid=valid)
            got_status = out.get("status")
            if got_status=="accepted": actual_receipt=out["receipt"]
            assert got_status == exp_status, (i, step, event, got_status, exp_status)

            audit = store.audit("claim")
            assert audit["count"] in (0, 1), (i, step, "count", audit["count"])
            assert audit["count"] == int(exp_state["accepted"]), (i, step, "count != 1", audit["count"])
            slot = audit["slots"][0]
            assert int(bool(slot.get("failed"))) == int(exp_state["failed"]), (i, step, "failed")
            assert int(bool(slot.get("conflict"))) == int(exp_state["conflict"]), (i, step, "conflict")
            assert slot.get("accepted_digest") == exp_state["accepted_digest"], (i, step, "accepted_digest")
            assert (slot.get("receipt") is None) == (exp_state["receipt"] is None), (i, step, "receipt none")
            if exp_state["receipt"] is not None:
                assert slot.get("receipt") == actual_receipt, (i, step, "receipt value")
            if exp_receipt is not None and got_status in ("accepted", "duplicate", "conflict"):
                assert out.get("receipt") == actual_receipt, (i, step, "out receipt", out.get("receipt"))

            r2 = store.reserve("claim", "A", boot)
            assert r2 == {"status":"consumed"}, (i, step, "reserve status", r2)
            assert "ticket" not in r2, (i,step,"reserve disclosed ticket")

        results.append({"order": list(order), "passed": True})

    return results