#!/usr/bin/env python3
"""Directed regression for strict integer frontier-certificate indices.

The standalone checker must reject JSON floats and booleans that compare equal to
integers before any validated certificate is passed to the numeric evaluator.
This is a finite implementation regression, not a mechanized proof.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Callable

from countcuts.frontier_check import Rejected, check
from countcuts.frontier_eval import encode, evaluate

BASE = Path(__file__).resolve().parents[1]


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def retained(case_id: str) -> tuple[dict, dict]:
    record = json.loads(
        (BASE / "results" / "observed" / "frontier" / f"{case_id}.json").read_text(
            encoding="utf-8"
        )
    )
    return record["case"], record["certificate"]


def decode_frontier03(case: dict, certificate: dict) -> int:
    colors = certificate["witnesses"][0]["left"]
    blocks = encode(case, colors, certificate["cuts"])
    return evaluate(case, certificate, blocks, query_index=0, departed=22)


def expect_rejected(
    name: str,
    case: dict,
    certificate: dict,
    mutate: Callable[[dict], None],
    *,
    decoder: Callable[[dict, dict], int] | None = None,
) -> None:
    changed = deepcopy(certificate)
    mutate(changed)
    try:
        check(case, changed)
    except Rejected:
        return
    except Exception as error:
        raise AssertionError(
            f"{name}: malformed certificate escaped the rejection contract as "
            f"{type(error).__name__}: {error}"
        ) from error

    if decoder is not None:
        try:
            decoder(case, changed)
        except Exception as error:
            raise AssertionError(
                f"{name}: checker accepted the mutation and downstream decoding "
                f"raised {type(error).__name__}: {error}"
            ) from error
    raise AssertionError(f"{name}: checker accepted a malformed certificate")


def main() -> None:
    case03, cert03 = retained("frontier03")
    case07, cert07 = retained("frontier07")

    baseline = check(case03, deepcopy(cert03))
    ensure(baseline["states"] == 72 and baseline["transitions"] == 93,
           "frontier03 baseline checker metrics changed")
    ensure(decode_frontier03(case03, cert03) == 22,
           "frontier03 baseline query decoding changed")
    negative = check(case07, deepcopy(cert07))
    ensure(negative["states"] == 1553 and cert07["earliest_failure"] == 4,
           "frontier07 negative baseline changed")

    mutations: list[tuple[str, dict, dict, Callable[[dict], None], Callable[[dict, dict], int] | None]] = [
        ("merge_source_float", case03, cert03,
         lambda c: c["merge_word"][0].__setitem__(0, 0.0), decode_frontier03),
        ("merge_source_bool", case03, cert03,
         lambda c: c["merge_word"][0].__setitem__(0, False), decode_frontier03),
        ("merge_rank_float", case03, cert03,
         lambda c: c["merge_word"][0].__setitem__(1, 0.0), decode_frontier03),
        ("merge_token_structure", case03, cert03,
         lambda c: c["merge_word"].__setitem__(0, (0, 0)), decode_frontier03),
        ("merge_source_bound", case03, cert03,
         lambda c: c["merge_word"][0].__setitem__(0, len(case03["lengths"])), decode_frontier03),
        ("merge_rank_bound", case03, cert03,
         lambda c: c["merge_word"][0].__setitem__(1, case03["lengths"][0]), decode_frontier03),
        ("required_source_float", case03, cert03,
         lambda c: c["required"][0].__setitem__(0, 0.0), None),
        ("required_source_bool", case03, cert03,
         lambda c: c["required"][0].__setitem__(0, False), None),
        ("required_rank_float", case03, cert03,
         lambda c: c["required"][0].__setitem__(1, 11.0), None),
        ("required_structure", case03, cert03,
         lambda c: c["required"].__setitem__(0, [0]), None),
        ("required_rank_bound", case03, cert03,
         lambda c: c["required"][0].__setitem__(1, 0), None),
        ("cuts_source_float", case03, cert03,
         lambda c: c["cuts"][0].__setitem__(0, 0.0), None),
        ("cuts_source_bool", case03, cert03,
         lambda c: c["cuts"][0].__setitem__(0, False), None),
        ("cuts_rank_float", case03, cert03,
         lambda c: c["cuts"][0].__setitem__(1, 11.0), None),
        ("cuts_structure", case03, cert03,
         lambda c: c["cuts"].__setitem__(0, [0, 11, 12]), None),
        ("witness_cut_source_float", case03, cert03,
         lambda c: c["witnesses"][0]["cut"].__setitem__(0, 0.0), None),
        ("witness_cut_source_bool", case03, cert03,
         lambda c: c["witnesses"][0]["cut"].__setitem__(0, False), None),
        ("witness_cut_rank_float", case03, cert03,
         lambda c: c["witnesses"][0]["cut"].__setitem__(1, 11.0), None),
        ("witness_cut_rank_bound", case03, cert03,
         lambda c: c["witnesses"][0]["cut"].__setitem__(1, 0), None),
        ("witness_query_float", case03, cert03,
         lambda c: c["witnesses"][0].__setitem__("query", 0.0), None),
        ("witness_query_bool", case03, cert03,
         lambda c: c["witnesses"][0].__setitem__("query", False), None),
        ("witness_query_bound", case03, cert03,
         lambda c: c["witnesses"][0].__setitem__("query", len(case03["queries"])), None),
        ("witness_time_float", case03, cert03,
         lambda c: c["witnesses"][0].__setitem__("time", 24.0), None),
        ("witness_time_bool", case03, cert03,
         lambda c: c["witnesses"][0].__setitem__("time", True), None),
        ("witness_time_bound", case03, cert03,
         lambda c: c["witnesses"][0].__setitem__("time", 0), None),
        ("earliest_failure_float", case07, cert07,
         lambda c: c.__setitem__("earliest_failure", 4.0), None),
        ("earliest_failure_bool", case07, cert07,
         lambda c: c.__setitem__("earliest_failure", False), None),
        ("earliest_failure_bound", case07, cert07,
         lambda c: c.__setitem__("earliest_failure", case07["horizon"] + 1), None),
        ("negative_witness_time_float", case07, cert07,
         lambda c: c["witness"].__setitem__("time", 4.0), None),
        ("negative_witness_query_float", case07, cert07,
         lambda c: c["witness"].__setitem__("query", 4.0), None),
    ]

    for name, case, certificate, mutate, decoder in mutations:
        expect_rejected(name, case, certificate, mutate, decoder=decoder)

    print(json.dumps({
        "status": "strict_frontier_integer_contract_passed",
        "baseline_frontier03_decoded": 22,
        "baseline_frontier03_states": baseline["states"],
        "baseline_frontier07_states": negative["states"],
        "strict_mutations_rejected": len(mutations),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
