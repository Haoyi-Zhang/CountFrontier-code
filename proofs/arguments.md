# Proof arguments and semantic boundaries

These are complete handwritten mathematical arguments, not machine-checked proofs.
The implementation's finite checks test instances of these arguments. The generic
factor-through and discernibility principles are established background; the
queue-specific results concern reachable departure frontiers, adjacent rank cuts,
and a FIFO realization of arbitrary discernibility hypergraphs.

## 1. Ambient precision and the workload contract

There are m ordered source words X_g of lengths n_g over a common alphabet K with
at least two classes. Let P={(g,r): 1 <= r < n_g}. For S contained in P, H_S(X)
retains each source's total class histogram and its prefix histogram at every cut
in S. Equivalently it retains the histograms of all contiguous blocks delimited
by S. Define S <= T iff S is contained in T: the left candidate is coarser.

This is a faithful order of the maps on the AMBIENT product of all source words.
If S is contained in T, block summation reconstructs H_S from H_T. Conversely, if
(g,r) belongs to S but not T, interchange two distinct classes at positions r-1
and r of source g. The total and every prefix histogram except the one at r stay
unchanged. Thus H_S does not factor through H_T. Intersection and union are the
meet and join in the declared cut family. A library L selects the sublattice
2^L; it does not change this global refinement order.

A workload W restricts admitted words, separately from this order. For a visible
context z and numeric query family Q, adequacy means that for all x,y in W_z,
H_S(x)=H_S(y) implies Q(z,x)=Q(z,y). Context and color-free control are retained.
A precision-minimal candidate is adequate and has no adequate proper subset.
A least candidate is contained in EVERY adequate candidate. They are different
notions. On a restricted W, different ambient maps can induce the SAME partition
of W; our nonleast result is about the declared ambient cut lattice, not about
nonexistence of a semantic query quotient. This distinction is essential.

Preservation here is pointwise equality of declared numeric answers, not merely
equality of a verifier's Boolean SAT/UNSAT result. Numeric preservation implies
preservation of Boolean postprocessing, but its minimality need not survive such
postprocessing.

## 2. The affine shuffle lemma

Fix a class-blind finite event schedule. Token j's admission, routing and event
times are independent of its class. A finite family of integer-weighted event
queries therefore has the form Q_q(x)=beta_q+sum_j A[q,j,x_j]. This is an equality
obtained by interchanging finite sums of the event contributions, not an assumed
probabilistic approximation.

W is either the full product of class assignments, or, independently for each
source, ALL permutations of one fixed class histogram. Its active palette P_g
contains precisely the classes with positive multiplicity; for full support it
is K. Choose c_g in P_g. For position j of source g let
sigma_j(q,c)=A[q,j,c]-A[q,j,c_g], c in P_g. Let R contain exactly the cuts between
adjacent positions with unequal signatures.

THEOREM. H_S preserves every Q_q on W iff R is contained in S.

Sufficiency: adjacent signatures are equal throughout each S-block B. Choose its
common signature sigma_B. With b_q=beta_q+sum_j A[q,j,c_g],
Q_q(x)=b_q+sum_B sum_{c in P_g} sigma_B(q,c) h_B(c).
Every term on the right is determined by H_S; classes outside P_g never occur.
The position-dependent reference terms are in b_q, so they need not be equal.

Necessity: if r is in R but not S, some q,c have unequal centered coefficients at
the adjacent positions u,v. Use c and c_g at u,v and interchange them. Under full
support complete all other positions arbitrarily. Under fixed histograms remove
one copy of each of these two distinct active classes and fill the remaining
positions with the remaining multiset. Complete other sources with their allowed
histograms. The two words are admitted, have equal H_S, and their query difference
is sigma_u(q,c)-sigma_v(q,c), which is nonzero. This proves necessity. A singleton
palette gives an empty signature and needs no cut, as the same argument predicts.

Consequences: R is the unique least adequate candidate in 2^P. In 2^L it is the
least candidate when R is contained in L; otherwise no candidate is adequate.
Every necessary cut has a two-position witness, unchanged at every other ambient
cut. Hamming distance two is minimal: changing one class changes a retained source
total. This statement is NOT a shortest-time theorem for general event schedules.

A simple offset example shows why raw coefficients are not the criterion. For one
six-position binary source, take reference class 0 and A[j,0]=j,
A[j,1]=j+1[j<=4]. Raw coefficients change at every neighboring position, but the
centered signature is 1 at ranks 1--4 and 0 at ranks 5--6. The query is 21 plus the
number of class-1 packets in the first four positions, so only cut 4 is needed.
The adjacent swap at ranks 4 and 5 proves its necessity. More generally, event terms
must be summed before signatures are compared: opposing signed terms can cancel.
The union of cuts needed by terms separately is sufficient but need not be least for
their sum; treating the terms as separate query-vector components prevents that
cancellation.

## 3. Separating packet order from service timing

The frontier model has preloaded, finite, nonempty source queues; no arrivals;
FIFO or LIFO source discipline; deterministic strict source priority, round robin,
or an explicitly specified weighted cyclic calendar. The arbiter changes its
cursor only upon an actual transfer (empty slots can be skipped during that
transfer). It depends on source identity/emptiness, never packet class. Initially
empty downstream storage is FIFO, capacity B, and uses LOSSLESS BACKPRESSURE.
At each tick downstream service happens before upstream transfer, each with its
own availability bit. A blocked transfer does not remove a source token and does
not change the arbiter. No packet can traverse both stages in one tick.

Construct a merge word M by draining the initial source tokens through this
arbiter, ignoring timing and downstream capacity. Each entry is a source/rank
identity. Let u transfers and d departures have actually completed.

LEMMA (merge-prefix invariant). After every tick, transferred identities are
M[0:u], departed identities are M[0:d], downstream contents in FIFO order are
M[d:u], each source has consumed exactly its identities in M[0:u], and the arbiter
is at the cursor reached after u transfers in the untimed drain.

Proof by induction on ticks. At zero all prefixes are empty, all sources and the
cursor agree with the drain, and the sink is empty. Suppose the statements hold
at a tick boundary. If downstream service is disabled or the sink is empty,
nothing changes. Otherwise FIFO removes the first entry M[d], increasing d by
one and leaving M[d+1:u]. Upstream now sees the same source contents, emptiness
set and cursor as the untimed drain after u transfers. If disabled, finished or
blocked, it changes none of them. Otherwise its chosen token is exactly M[u];
appending it to the FIFO sink extends the transferred prefix, source-consumption
prefix and cursor by one. Capacity permits that append. These cases establish all
invariants for the next tick. No statement depends on packet colors. QED.

Consequently, with availability (a,b), and N=sum n_g,
 d' = d + 1[b and d<u],
 u' = u + 1[a and u<N and u-d'<B].
A finite service automaton can be included in state e. The executable fragment
supports all availability pairs, or cumulative upstream/downstream disabled-slot
budgets at most two. The latter counts disabled slots even while a queue is empty.
Both languages are color-independent, and every admitted prefix extends to the
horizon by enabling both servers subsequently.

The exact layer recurrence V_0={(0,0,e_0)} and V_{t+1}=Post(V_t) enumerates only
COLOR-FREE states. It does not enumerate K^N words or all histogram states. Let
D_t={d:(u,d,e) in V_t}. Let F_g(d) count source-g entries in M[0:d]. Source g has
contributed its initial prefix of length F_g(d) if FIFO, or suffix of that length
if LIFO. This observation is independent of source/sink occupancy at query time.

## 4. Reachable-frontier cut theorem

The queries are counts of class c among final departures by a declared tick t.
For each query (t,c), each d in D_t, and each source g for which c is active and
at least one other class is active, include the interior boundary
 r=F_g(d) for FIFO, or r=n_g-F_g(d) for LIFO.
Let R be the union over the entire locked query family and all such frontiers.

THEOREM. R is the unique least adequate cut set in the declared ambient cut
lattice on full or independently fixed-histogram shuffle-complete workloads.
If a library omits any member of R, no member of that library's cut sublattice
preserves the full query family.

Sufficiency: at each reachable queried control state, every source contribution
is either zero, its retained total, a constant due to a singleton/absent palette,
or a prefix/suffix class count at a retained boundary. Block summation therefore
reconstructs the complete query answer. The same histograms persist through the
run, so this reconstructs the joint family, not just its marginal answer ranges.

Necessity: take a missing boundary exposed by query (t,c) and reachable d. Choose
one concrete availability prefix reaching it. Swap c and another active class
across that boundary in that source; complete the words as in the shuffle lemma.
Exactly one of the swapped positions is in M[0:d], while all other departed token
classes agree. The numeric query differs by one. The words have the same H_S and
under the common availability prefix the same control trace. Thus S fails.

An explicit transition abstraction uses an immutable initial word as ghost state:
concrete state (t,X,u,d,e), abstract state (t,H_S(X),u,d,e). Transitions act only on
(t,u,d,e) and have exactly the recurrence above. Every abstract path from a
realizable initial histogram lifts, using any realizing X, to a concrete path.
The theorem supplies exact query labels at declared times. This is NOT a claim
that arbitrary class-labeled per-tick output events are preserved when their
counts were not included in the query family, nor a replacement of dynamic
Count-Buffy windows with the same semantics. The histogram is of the immutable
source words, not necessarily of the current physical queue.

Three closure facts follow directly from the formula for R. First, for fixed model,
workload and service language, R(Q1 union Q2)=R(Q1) union R(Q2): an exposing query
on either side is exactly an exposing query in the union. The same color-free
reachability layers can therefore be reused, although the cut set and each witness
must be regenerated and checked for the new query family. Deleting queries preserves
adequacy but can destroy leastness; adding queries can invalidate both adequacy and
an old earliest-witness claim.

Second, if one full-horizon service language is contained in another while the merge
order and workload are unchanged, every queried departure prefix reachable in the
smaller language is reachable in the larger. Its required cut set is therefore a
subset of the larger language's set. This monotonicity does not compare changes that
alter the merge, event order, or admission behavior.

Third, at one endpoint the class counts sum to the retained departure total d. Hence
any |K|-1 numeric class answers and d determine the last answer. Asking for all class
counts at that endpoint requires no more cuts than asking for any complement of one
class. This is an equality of declared numeric answers, not a balance assumption.

## 5. Earliest distinguishing execution prefixes

For any inadequate S, define t* as the earliest declared query time that exposes
a reachable boundary outside S. Breadth layers identify t*, and predecessor
choices give a concrete action prefix of length t*. The necessity construction
above gives two admitted executions with equal abstract control/count histories
and unequal query answers at t*. Both prefixes extend to the horizon.

Suppose a shorter pair of extendible prefixes were a witness. Its endpoint must
be a declared query time t<t*. Every boundary needed at that time and any equal
retained control state is in S. The sufficiency proof therefore gives equal
answers for the two histories, a contradiction. Thus t* is the shortest COMMON
TICK LENGTH of distinguishing extendible prefixes for the locked query family
and retained control observation. This is not an unbounded shortest-counterexample
claim, and is not the length of full-horizon traces (which all have length H).
For adequate R, apply the same reasoning to R\{r} for each necessity witness.

## 6. Uniform-window arithmetic

For a fixed-origin common positive integer width w, its source-g interior cuts
are positive multiples of w below n_g. By the cut theorem, it is adequate iff w
divides every required local rank. If R is nonempty, these widths are exactly
the divisors of gcd{r:(g,r) in R}; if R is empty every width is adequate. Uniform
widths are not a refinement chain ordered by their numerical values. For n=6 and
required cut 4, widths 1,2,4 preserve the query and widths 3,5,6 do not.

For independent uniform widths per source, apply the same gcd separately to each
source's required ranks. Choosing that gcd (or n_g when no cut is needed) minimizes
the number of uniform blocks in that source; this elementary baseline is stronger
than requiring a common width. It is a representation-count baseline, not an
implementation-time optimality theorem.

Running example: two 24-token FIFO sources, round robin starting at source 0,
FIFO sink capacity 2, 24 ticks, upstream always enabled and at most one disabled
downstream slot. Exactly D_24={22,23}. The required boundaries are (0,11),
(0,12), (1,11). They induce 5 histograms. A common uniform width must be 1 and
uses 48 histograms. Independently chosen source widths 1 and 11 use 24+3=27.
The comparison is not 5 versus 48 for the stronger source-specific baseline.
The count of histogram records is not the number of reachable abstract states.

## 7. Arbitrary-support boundary and classical discernibility

For an explicitly enumerated workload with retained context, consider every pair
x,y with the same context and retained source totals but different query vectors.
Its separator E(x,y) consists of the eligible prefix cuts at which their class
histograms differ. S is adequate iff it intersects each separator. This is the
classical discernibility/hitting-set characterization, not a new abstraction
algorithm. If a separator is empty, the library is insufficient. Otherwise, a
minimal adequate S has, for every s in S, a private pair with E(x,y) intersect S
exactly {s}; these pairs also certify failure of every strict subset of S.
Checking all pairs proves sufficiency; private pairs alone do not.

FIFO REALIZATION THEOREM. Every finite hypergraph with m vertices and nonempty
edges is the family of bad-pair separators of a single FIFO construction with
binary classes, capacity m+1, horizon m, one terminal class-count query, and a
retained finite context selecting one pair and its class-blind service schedule.

Proof. Identify vertices with ranks 1,...,m. For an edge E, set d_0=d_{m+1}=0 and
d_i=1[i in E]. At word position i=1,...,m+1 set x_i=1 iff d_i-d_{i-1}=1, and set
y_i=1 iff d_i-d_{i-1}=-1; all remaining positions are zero. Both words are binary.
Telescoping gives sum_{i<=r}(x_i-y_i)=d_r and equal totals at r=m+1. Their class-1
prefix counts differ exactly at cuts in E (class-0 differences are their negatives).
Under visible context E admit exactly these two words. Serve min(E) packets in the
first min(E) ticks and then idle until tick m. The terminal query difference is
one. Context separates different edges, so there are no cross-context bad pairs.
The construction takes O(m |edges|) bits apart from context identifiers, and
produces exactly the claimed separators. For the empty edge family admit a
single all-zero word and serve nothing. QED.

The construction proves that a common FIFO discipline and one counter query do
not force singleton necessities once arbitrary correlated workload restrictions
and retained modes are permitted. Edges {1,3} and {2,3} have incomparable ambient
minimal candidates {3} and {1,2}. They nevertheless induce the same (discrete)
partition on each admitted two-word context, as Section 1 requires us to state.
This is not a contradiction to the existence of a most abstract strongly
preserving domain in a richer domain lattice.

For a nonempty-edge hypergraph, a least hitting set exists iff the set U of all
vertices that occur as singleton edges itself hits every edge. Indeed, a vertex
belongs to every hitting set exactly when its singleton is an edge: otherwise
all other vertices form a hitting set. Thus U is the intersection of all hitting
sets, and it is a least hitting set exactly when adequate. Finding one inclusion-
minimal hitting set by greedy deletion is different from finding a minimum-
cardinality one. No hardness result is required by this paper's retained claims.

## 8. Checker argument

The frontier checker validates the supported source model, independently derives
the untimed merge order by consumption counters, and requires the supplied
reachable layers to equal the complete successor image at each tick. Induction
on layers proves that this certificate admits neither an omitted nor an invented
reachable control state. It derives necessary cuts from differences in adjacent
token membership in departed prefixes, rather than from the producer's F_g table.
The reachable-frontier theorem therefore establishes all adequacy decisions.

Every reported necessity/failure witness is replayed through explicit packet
lists with the event order, backpressure and service-language constraints. Its
colors must belong to the workload, all other ambient cut observations and totals
must agree, the histories must have the same color-free states, and the declared
answer must differ. The checker also recomputes the earliest exposing declared query time and
explicitly replays every strictly earlier declared query against the same pair,
rejecting a witness if any earlier answer already differs. Thus an accepted
certificate has exactly the stated semantic consequences,
conditional on this mathematical argument and correct checker execution. Finite
mutation tests do not prove that the checker implementation is bug-free.

The certificate deliberately separates universal and existential evidence. Adequacy
quantifies over every admitted coloring and service path, so a list of successful
runs is insufficient; exact successor-layer equality and the shuffle proof discharge
that part. Necessity for one cut needs only one admitted pair and one common path, so
an explicit replay is appropriate. One predecessor per reached state is enough to
extract a path because future behavior depends only on the retained time-indexed
control state, but every successor must appear in the next certified layer.

For a negative library decision, a pair that differs only at a required cut outside
the library agrees on the library's top element and therefore on every eligible
coarsening; one pair defeats the whole sublattice. Transition-system consumption is
valid only from realizable initial histograms. Prefix histograms must be monotone with
block differences of the declared lengths, and fixed-histogram workloads also fix
source totals. The checker verifies witness membership rather than treating arbitrary
nonnegative counter tuples as queues.

For fixed schedules, the checker uses location/timestamp packet replay, a
term-first event coefficient matrix, all active class-pair comparisons, exact
block-formula checks and directly evaluated colored witnesses. It does not import
the synthesizer. Restricted-support validation exhausts the declared finite
support and verifies the selected private pairs. For an insufficient-library
certificate it additionally checks that two admitted words agree under the full
eligible library yet disagree on the query; this single collision defeats every
eligible coarsening. A regression test also rejects that certificate once the
missing separator is added to the library. None of these implementations
claims independent human authorship or independent blind review.

## 9. Countermodels to overextension

Tail-drop admission breaks the merge-prefix property: with sink capacity one,
transfer token 0, drop token 1 while service is disabled, then serve 0 and transfer
2, and finally serve 2. The departure sequence [0,2] is not a prefix of [0,1,2].
Downstream LIFO can serve token 1 before token 0 after two transfers. New arrivals
can change which source priority selects, depending on timing, so a single
preloaded untimed merge word no longer suffices. These are countermodels to a
universal extension, not assertions that every model outside the fragment fails.

Class-sensitive selection can also destroy the affine form: two one-token
sources with priority to class 1 have first-departure class-1 count OR(x_1,x_2).
Its mixed difference Q(1,1)-Q(1,0)-Q(0,1)+Q(0,0) is -1, while every additive form
has mixed difference zero. None of these extensions is silently accepted by the
frontier input schema. Fixed-schedule tail-drop/LIFO examples use the separate
affine mechanism and make no symbolic-frontier claim.

## 10. Removing redundant restricted-support constraints

If nonempty edges E and F satisfy E contained in F, every set hitting E also hits
F. Deleting F therefore preserves the full adequate-candidate family. Iteratively
retain only inclusion-minimal edges to obtain a canonical antichain. Conversely
every deleted edge contains a retained one (the edge family is finite), so the
retained constraints imply every deleted constraint. This proves equivalence in
both directions. The empty family remains empty. The campaign maps all 128
three-vertex nonempty-edge families to their 19 distinct antichains and checks
each mapping on every one of the eight candidate cut sets. It replays only those
19 canonical FIFO supports. This is a redundancy elimination, not a claim to have
run the omitted physical workload instances or a new hitting-set algorithm.
