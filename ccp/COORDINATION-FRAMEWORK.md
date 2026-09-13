# Consort Coordination Process (CCP) Framework

The Consort Coordination Process (CCP) is a reusable pattern for using
Consort's `|` pipeline to coordinate any evidence-driven, closed-loop
process — diagnosing and treating a patient, planning a menu, running a
competitive analysis, and so on. CCP is not part of Consort's grammar
(Consort itself is domain-agnostic and has no concept of "coordination
processes"); it is a convention for *how* to structure a `|` pipeline,
expressed at three independent, separately-maintained levels:

1. **Consort** — the language itself (currently v0.20; see
   [`../CHANGELOG.md`](../CHANGELOG.md)).
2. **The CCP framework** (this document plus
   [`ccp.consort`](ccp.consort)) — the
   domain-agnostic pattern: six orthogonal functions every coordinated
   process passes through, and the conventions for expanding them into
   concrete stages.
3. **A domain-specific CCP prompt** (e.g.
   [`medical-care.consort`](medical-care.consort)) — a concrete Consort
   `|` pipeline that instantiates the framework for one specific process,
   in that domain's own vocabulary.

Each level is maintained independently. A domain-specific prompt names
which framework it instantiates; the framework doesn't know or care how
many domain prompts exist, or what any of them contain.

## The Six Orthogonal Functions

| Function | Core question | What happens |
| --- | --- | --- |
| **SENSE** | What is happening? | Frame the question and gather the evidence needed to answer it |
| **UNDERSTAND** | What does the evidence mean? | Interpret the evidence and establish the current state |
| **DECIDE** | What ought to happen? | Choose a course of action from the established state |
| **ACT** | — | Carry out the chosen action |
| **MEASURE** | What were the consequences? | Observe and assess the effect of the action |
| **ADAPT** | What should change? | Revise the course, and carry lessons into the next cycle |

These six are deliberately minimal and non-overlapping — every step in a
coordinated process should belong clearly to exactly one of them. They
are the *only* thing CCP standardizes; everything else (how many `|`
stages a function becomes, what to call them, what each stage's task
description says) is a domain-specific choice.

## Expanding a Function Into Concrete Stages

A domain-specific prompt does not need one `|` stage per function — a
function may expand into as many stages as the domain genuinely needs,
or collapse into none if it doesn't apply. For example, a medical-care
instantiation expands SENSE into three stages (`observe`, `assess`,
`investigate`) because clinical evidence-gathering has three distinct,
separately-useful moments; a simpler domain might cover SENSE in a
single stage.

There is no naming convention forcing a stage to mention its function by
name — `observe`, not `sense-observe`. The function names exist for
design-time reasoning (which function does this stage serve?) and don't
need to appear in the dispatched prompt at all, unless a domain author
specifically wants a stage to have access to a function's own definition
as working input — in which case, expressing the function as a labeled
`#` block (spec 2.5) that the relevant stage names explicitly is the
correct mechanism: a labeled block is only part of a stage's working
input when that stage's task text names it (2.3/2.5), unlike plain `#`
content, which reaches every stage automatically.

## Delivery Order

A CCP-based prompt is delivered to the interpreting model in three
sequential parts, each building on the last:

1. **The Consort specification**
   (`CONSORT Markdown for Intelligent Coordination.txt`) — teaches the
   model the DSL itself.
2. **`ccp.consort`** — a complete, standalone Consort message
   establishing the CCP framework generically: the six functions, and
   constraints that apply to any CCP-based process regardless of domain
   (distinguishing observed fact from interpretation, preserving
   uncertainty, treating the process as closed-loop rather than strictly
   linear). It deliberately contains no `|` entries — the concrete
   stages are a domain-specific decision, supplied next.
3. **A domain-specific prompt** (e.g. `medical-care.consort`) — the
   actual `!`/`|` work order in domain vocabulary, relying on the prior
   message to have already established the general framework and
   constraints.

This mirrors how the Consort spec itself is already delivered (as a
system-prompt-like foundation before any actual Consort message) — CCP
just adds one more such layer.

## Closed-Loop Processes

Consort's `|` pipeline expresses a single linear pass (spec 2.9) — it has
no loop-back or branching construct, and CCP does not attempt to add one.
A CCP process that conceptually loops (e.g., MEASURE finding an outcome
that sends the process back to SENSE or DECIDE) is still just a
single-pass `|` pipeline: the loop-back condition is named as ordinary
prose (in a stage's task description or a `$` constraint), and whether
or when to actually re-invoke the pipeline is the responsibility of
whatever system drives the interpreting model across turns — not Consort
or CCP.

A practical way to implement this: the orchestrator checkpoints each
completed stage's output to disk, keyed by stage label and process
instance. On loop-back, it does not resume any in-flight state (there
isn't any — Consort messages are self-contained) — it constructs a fresh
domain-specific message covering only the remaining stages, with the
checkpointed prior results supplied as `#` context, ideally in framed
form (spec 2.10), since it is another turn's output being re-injected
and should not be re-scanned as live syntax.

## Background

[`TAXONOMY.md`](TAXONOMY.md) in this folder captures the exploratory
thinking that led here — multiple, not-fully-reconciled perspectives on
the underlying loop, a twelve-domain use-case survey, and the original
medical case study `medical-care.consort` is derived from (though
rebuilt, not copied, to fit the three-level split above). It predates
this framework, is not kept in sync with it, and should be treated as
informal background, not a second source of truth.
