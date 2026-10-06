# Precision-minimal count abstractions

CountCuts is an offline bounded research artifact. Its primary method extracts
necessary initial-source histogram cuts from reachable departure frontiers in a
preloaded, class-blind, lossless tandem contention model. A separately implemented
checker verifies certificates and explicit packet witnesses. This is not a live
network analyzer, a Count-Buffy implementation, or a verified compiler.

## Reproduce the main scientific results

Use Python 3.10 or later on a POSIX/Linux environment with the standard library.
No Python package installation, network, solver, GPU, account, API, or external
input is needed. Run from this repository root. The runner uses one CPU worker,
2 GiB address space and a 110 CPU-second process cap. The included run completes
well below these caps; timings are not performance claims. Scientific consistency
checks use explicit exceptions rather than optimization-sensitive assertions, so
`python -O` does not remove them.

```sh
python reproduce.py --output results/reproduced
python compare_results.py results/observed results/reproduced
```

For a single isolated command that also runs the certificate CLI, all retained
pilots, the exhaustive frontier audit, the restricted negative-certificate
regression, the full fixed-interpreter cross-check, the strict frontier-certificate
integer-contract regressions, and JSON/CSV parsing, use:

```sh
python verify.py
```

`verify.py` works in a temporary copy and does not alter retained results. It
runs ordinary reproduction, a `python -O` reproduction with `PYTHONHASHSEED=17`,
and a second reproduction with `PYTHONHASHSEED=991`; all three must compare equal
to the retained scientific content. It also parses the production Python syntax,
rejects any optimization-sensitive `assert` statement outside the test suite, and
compares the deque-based producer with the location/timestamp checker on every one
of the 51 fixed cases: all 35,216 event records (as multisets) and 107,400
query-coefficient cells must agree.

`tests/frontier_integer_contract.py` separately checks that a valid F03 certificate
still decodes query 0 at departure frontier 22, while JSON floats, booleans,
malformed pairs, and out-of-range values in `merge_word`, `required`, `cuts`,
witness cuts, witness query/time fields, and `earliest_failure` are rejected before
numeric decoding. These directed checks are additional regressions; they do not
change the retained count of 23 campaign mutations or two incomplete controls.

`tests/fixed_restricted_integer_contract.py` checks the corresponding fixed and
restricted certificate fields. All 64 binary words in the six-position FIFO
example decode from the certified block indices and coefficients exactly as
direct colored execution does. Its 42 fixed-positive, four fixed-negative and
15 restricted malformed-field variants must raise the checker's rejection
exception, rather than accept numerically equal floats/booleans or fail later
on a slice index. These are separate directed regressions, not additions to the
retained campaign's 23 mutations.

For raw outputs and a retained isolation directory, use new, absent paths:

```sh
python -B verify.py --work-dir /tmp/countcuts-check --logs /tmp/countcuts-output
```

The verifier parses every Python source without producing bytecode, sets UTF-8
and bytecode-free execution for its subprocesses, and retains each command's raw
stdout/stderr when `--logs` is supplied. It bounds each command to 60 seconds.
The `.github/workflows/scientific-checks.yml` runs the whole verifier
from this flat artifact-repository root on Ubuntu 24.04, with one CPU, a
240-second whole-run timeout, a 2-GiB virtual-memory limit and a 110-second
per-process CPU limit. Raw outputs are uploaded even when a check fails; failures
remain failing gates.

The output directory must be new. The expected result is
`all_finite_checks_passed`: 51 fixed-schedule, eight symbolic-frontier and 19
restricted-support main cases; 51 adequate and 27 insufficient eligible
libraries; a separate exhaustive audit of 32 micro-models, 3,250 concrete
color/service traces and all 13,644 trace-candidate comparisons across 118
(model, candidate cut-set) pairs; 99,212 charged
obligations in total; zero oracle/audit disagreements; 23 rejected
certificate/schema mutations and two incomplete transition-limit controls. The
comparison requires all deterministic scientific JSON and table content to match. It deliberately excludes timings and memory, not witnesses or decisions.
A historical clean reproduction is recorded in
`results/clean_reproduction.json`. Generated model dictionaries must equal the
retained `inputs/cases.json` before a run proceeds.

The observations in `results/observed` and `results/clean_reproduction.json` are
retained historical host executions. Their CPU/RSS values are not measurements
of the current checker revision on every platform. Windows function-level
replays can test the finite semantics but do not execute the POSIX resource
guards in `reproduce.py`, the CLI or the three development-pilot entry points.

The current Python 3.12 Linux run completed all 16 verifier commands, including
the CLI and three development pilots. Normal execution, optimized execution with
hash seed 17, and normal execution with hash seed 991 each matched 82 JSON records
(81 non-summary records plus the summary) and all 59 rows of the single case-table
CSV. The data-only correspondence check excluded only named root timing/RSS fields
and CSV timing columns; operation counts, resume flags, per-invocation counts,
witnesses and negative results also matched. The fixed/restricted regression
checked 64 decoder words and rejected 61 malformed certificates, separately from
the historical 23 campaign mutations. Per-reproduction whole-process CPU ranged
from 0.472 to 0.581 seconds and peak RSS from 19,980 to 22,388 KiB; these are host
observations, not comparative speed results. The [Linux measurement receipt](results/measurements/linux-37438859887.json)
records the run identity, commands, exact measurements and regression outcomes.
Historical tables, results and measurements are retained unchanged.

## Synthesize and check a certificate

The example below uses the retained 48-position round-robin case. The output file
must not already exist. The synthesis command checks its own output using the
separate checker; the second command imports no producer and checks the file again.

```sh
python -m countcuts synthesize --family frontier --case frontier03 --output results/example-certificate.json
python -m countcuts check --family frontier --case frontier03 --certificate results/example-certificate.json
```

The command-line interface accepts `fixed`, `frontier`, or `restricted` families.
It can also read a standalone case dictionary through `--input` instead of an
exact retained case identifier. Certificate/model schemas are defined by the
corresponding validators. Input files are limited to 2 MiB. Exit 0 means the
requested computation/check completed; a completed certificate may say
`insufficient_library`, which is a valid negative answer. Exit 2 means rejection
or incomplete computation and carries no positive scientific conclusion.

## Retained development pilots

The development pilots were run before the main input selection was frozen. They
are not held-out tests. These commands reproduce their finite content, overwriting
only their named pilot result files; preserve a copy of recorded measurements
when comparing machines. No unpublished project state is used.

```sh
PYTHONPATH=. python tests/algebraic_pilot.py
PYTHONPATH=. python tests/end_to_end_pilot.py
PYTHONPATH=. python tests/frontier_pilot.py
PYTHONPATH=. python tests/restricted_negative.py
```

The three development pilots charge 8,816, 374, and 6,525 obligations respectively. The restricted negative test separately confirms that a genuine insufficient-library certificate is accepted and a forged one is rejected. The
exhaustive audit can also be run directly with
`PYTHONPATH=. python tests/exhaustive_frontier_audit.py`; unlike the development
pilots, it is part of the retained 99,212-obligation campaign. The first
end-to-end attempt was repaired during development; a conservative 277-obligation
charge remains in the resource account, but no obsolete execution is needed for
reproduction. The retained scripts reproduce the current scientific pilot claims.

## Models and guarantees

`countcuts/frontier.py` constructs an immutable merge word and exact service
layers `(transferred, departed, upstream_stalls, downstream_stalls)`.
`frontier_check.py` independently reconstructs merge order, successor-set equality,
adjacent membership, and explicit colored witnesses. It imports no producer.
`frontier_audit.py` adds a third, deliberately small-model path: direct packet
execution and independently constructed abstraction keys are compared against the
producer and checker for every admitted coloring, valid service word, and ambient
cut subset. For missing-cut negatives it also recomputes the earliest semantic
failure rather than trusting the certificate.
The schemas allow one to four preloaded FIFO/LIFO source queues, lengths 1–24,
2–4 classes, horizon 1–48, at most 32 departure-prefix queries, and at most six
eligible cuts. The downstream queue is initially empty FIFO with backpressure.
Only class-blind source priority, round robin, or a weighted cyclic calendar is
accepted. Service is free or has at most two disabled slots per server.

`engine.py` and `checker.py` are distinct fixed-schedule implementations. They
support arrivals, tail drops, FIFO/LIFO sinks, and affine signed event queries.
Their immutable offered-position summary is schedule-specific. It is not the
symbolic-service frontier abstraction and not a current physical queue window.

`restricted.py` and `restricted_check.py` implement finite visible-context FIFO
supports and classical discernibility. The campaign checks all 128 three-cut
hypergraphs via 19 canonical antichain workloads. It does not call these 128
separate physical system experiments. Greedy deletion returns an inclusion-minimal
candidate, not a minimum-cardinality one.

`proofs/arguments.md` contains complete handwritten general arguments. They are
not mechanically verified. The ambient precision order is cut inclusion on all
class words, while a workload separately restricts admitted assignments. In the
restricted-support negative construction, incomparable ambient maps can have the
same induced partition on the admitted workload. A least semantic quotient is not
claimed impossible. Witnesses are shortest at declared queried endpoints under
the retained control and extendibility contract, not unbounded shortest traces.

## Evidence and boundaries

- `inputs/`: exact generated model dictionaries and retained pilot inputs.
- `results/observed/`: original main-run certificates, controls, oracles, tables.
- `results/clean_reproduction.json`: clean-extraction comparison and measurements.
- `results/measurements/linux-37438859887.json`: current Linux execution and scientific-correspondence receipt; separate from historical measurements.
- `claim_evidence_ledger.csv`: theorem/test/data support for material claims.
- `reference_audit.csv`: publisher/first-party identifier and manuscript-role audit for every cited bibliography entry.
- `external_resources.csv`, `literature.csv`: lawful provenance and reading scope.
- `proofs/arguments.md`, `tests/`: general arguments and finite development checks.

No runtime improvement over an external verifier, stochastic error rate,
production-network fidelity, minimum implementation cost, independent human
review, or machine-checked general proof is asserted. Synthetic examples validate
the method and its boundaries; their count is not practical workload breadth.
The accompanying manuscript is a separate deliverable, but this repository does
not need its sources, figures, private paths, or caches to reproduce the science.

Original repository materials are offered under the
included MIT license. No upstream scientific code or copyrighted paper PDF is
redistributed here; cited works retain their own rights.
