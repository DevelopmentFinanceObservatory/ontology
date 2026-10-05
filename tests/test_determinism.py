"""Determinism: the seam fixture must compile to byte-identical MCF, report, and codes.

Two axes are exercised. In-process: entity order, batch split, and per-entity claim
order are all permuted between three runs over the same fixture — re-emitting from one
`Graph` in one process would prove nothing, since ordering is only ever a hazard on the
way in. Out-of-process: one subprocess pair compiles the same fixture at differing
`PYTHONHASHSEED` values, so no accidental reliance on dict/set iteration order specific
to one hash seed can hide behind a passing in-process run.
"""

import json
import os
import subprocess
import sys

from .test_seam import (
    EXPECTED_CODES,
    EXPECTED_MCF,
    EXPECTED_REPORT,
    PAYLOADS,
    compile_payloads,
)


def _permute(
    payloads: list[dict], *, order: list[str], batches: list[int]
) -> list[dict]:
    """Reorder payloads by qid, reverse each entity's claim key order, split into batches.

    Args:
        payloads: the fixture payloads, in their canonical order.
        order: the qid order to emit payloads in.
        batches: chunk sizes to split the reordered list into before concatenating,
            simulating payloads arriving across differently-sized wbgetentities calls.
    """
    by_qid = {payload["id"]: payload for payload in payloads}
    reordered = []
    for qid in order:
        payload = dict(by_qid[qid])
        if "claims" in payload:
            claims = payload["claims"]
            payload["claims"] = {key: claims[key] for key in reversed(list(claims))}
        reordered.append(payload)

    chunks = []
    start = 0
    for size in batches:
        chunks.append(reordered[start : start + size])
        start += size
    chunks.append(reordered[start:])
    return [payload for chunk in chunks for payload in chunk]


_QIDS = [payload["id"] for payload in PAYLOADS]
_RUNS = [
    (_QIDS, [len(_QIDS)]),
    (list(reversed(_QIDS)), [5, 5, 4]),
    (_QIDS[7:] + _QIDS[:7], [3, 4, 3, 4]),
]


def test_permuted_entity_batch_and_claim_order_is_byte_identical() -> None:
    """Three permutations of the same fixture compile to the same three artifacts."""
    for order, batches in _RUNS:
        mcf, text, csv_text = compile_payloads(
            _permute(PAYLOADS, order=order, batches=batches)
        )
        assert mcf == EXPECTED_MCF
        assert text == EXPECTED_REPORT
        assert csv_text == EXPECTED_CODES


_SUBPROCESS_SCRIPT = """
import json
import sys

from dfo_ontology import codes, emit, reader, report, validate
from dfo_ontology.config import Config

config = Config(bench="testing")
payloads = json.loads(sys.stdin.read())
graph = reader.read(payloads, config=config)
result = validate.validate(graph)
sys.stdout.write(emit.emit(graph, config=config))
sys.stdout.write(chr(0))
sys.stdout.write(report.render(graph, result, config=config))
sys.stdout.write(chr(0))
sys.stdout.write(codes.render(graph))
"""


def _compile_at_hash_seed(seed: str) -> str:
    """Run the subprocess script over PAYLOADS with PYTHONHASHSEED set to seed."""
    process = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        input=json.dumps(PAYLOADS),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": seed},
        check=True,
    )
    return process.stdout


def test_hash_seed_pair_is_byte_identical() -> None:
    """PYTHONHASHSEED=0 and PYTHONHASHSEED=1 compile to the same three artifacts."""
    output_0 = _compile_at_hash_seed("0")
    output_1 = _compile_at_hash_seed("1")
    assert output_0 == output_1
    mcf, text, csv_text = output_0.split(chr(0))
    assert mcf == EXPECTED_MCF
    assert text == EXPECTED_REPORT
    assert csv_text == EXPECTED_CODES
