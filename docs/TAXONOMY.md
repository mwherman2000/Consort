# Consort Use-Case Taxonomy

This document extends the "Use Cases" section of the [README](../README.md): the
same evidence-driven, closed-loop coordination process, worked out across
every domain the README lists, not just the four given a full breakdown
there. Consort does not define this loop as part of its grammar — the
directives (`!` `#` `$` `%` `*` `@` `^` `|` `+`) are domain-agnostic — but
authors consistently reach for the same shape of process when using
Consort to coordinate real work, and naming that shape explicitly makes
it easier to write `|` pipelines and `^` fan-outs that follow it.

## The General Coordination Loop

Eight recurring phases, in roughly this order (real work loops back —
`Adapt` and `Follow-up` routinely feed back into `Understand` or
`Investigate` rather than ending the process):

**Table 0. General Coordination Loop**

| Phase | What happens |
| --- | --- |
| **Frame** | State the problem or question worth solving |
| **Understand** | Establish context, constraints, and stakeholders |
| **Investigate** | Gather evidence — research, testing, examination |
| **Decide** | Choose a course of action from the evidence |
| **Act** | Execute the decision |
| **Evaluate** | Assess the outcome against the original goal |
| **Adapt** | Revise the plan, decision, or approach based on evaluation |
| **Follow-up** | Sustain, monitor, or carry lessons into the next cycle |

Not every domain names all eight phases explicitly — some compress
adjacent phases into one step, or treat one phase as implicit — but all
twelve below map onto this same underlying loop.

## Domains

### Medical Care

Observe → Assess → Investigate → Diagnose → Plan → Treat → Monitor → Reassess → Adapt

### Menu Planning

Understand occasion → Assess constraints → Investigate options → Design menu → Select → Prepare → Serve → Evaluate → Adapt

### Trip Planning

Frame trip goals → Understand travelers' needs and budget → Investigate destinations and options → Choose itinerary → Book and prepare → Travel → Evaluate the experience → Adapt for next time

### Competitive Analysis

Frame strategic question → Understand market → Investigate competitors → Analyze → Decide → Act → Monitor → Reassess → Adapt

### Business Strategy

Frame strategic objective → Understand internal capabilities → Investigate market and environment → Decide strategic direction → Execute initiatives → Evaluate performance → Adapt strategy → Review periodically

### Software Quality

Define quality objectives → Understand system → Inspect/test → Diagnose defects → Prioritize → Remediate → Test → Evaluate → Adapt

### Engineering

Define requirements → Understand constraints → Investigate design options → Select design → Build → Test/validate → Adapt design → Monitor in service

### Procurement

Define sourcing need → Understand requirements and stakeholders → Investigate vendors and market → Select vendor → Contract and purchase → Evaluate delivery and performance → Adapt terms or vendor → Manage ongoing relationship

### Research

Frame research question → Understand prior work → Investigate via experiments or data → Interpret results → Publish or apply findings → Evaluate peer feedback and replication → Adapt hypothesis or method → Plan follow-on research

### Scientific Investigation

Formulate hypothesis → Understand background theory → Design and run experiments → Analyze results → Report findings → Evaluate reproducibility → Adapt hypothesis or method → Extend investigation

Distinct from Research above: Scientific Investigation is the narrower,
hypothesis-and-experiment loop (lab-style); Research is the broader
inquiry loop that also covers qualitative, market, or desk research
where there may be no formal hypothesis to test.

### Incident Response

Detect and frame incident → Understand impact and scope → Investigate root cause → Decide remediation → Contain and fix → Evaluate resolution → Adapt runbooks and systems → Follow up with preventive actions

### Personal Decision Making

Frame the decision → Understand values and constraints → Investigate options → Decide → Act → Reflect on the outcome → Adapt course → Track the long-term result

## Use Case Process/Activity/Task Decompoisition

Split into two tables of six domains each for readability — a single
thirteen-column table stops being scannable.

**Table 1. Use Case Process/Activity/Task Decompoisition (Part A)**

| General phase | Medical | Menu planning | Trip planning | Competitive analysis | Business strategy | Software quality |
| --- | --- | --- | --- | --- | --- | --- |
| **Frame** | Patient problem | Occasion & guests | Trip goals & budget | Strategic question | Strategic objective | Quality objective |
| **Understand** | History/symptoms | Preferences/constraints | Traveler needs/budget | Market situation | Internal capabilities | Architecture/codebase |
| **Investigate** | Tests/examination | Ingredients/options | Destination/option research | Competitor research | Market/environment scan | Testing/inspection |
| **Decide** | Diagnosis/treatment plan | Menu selection | Itinerary selection | Strategy | Strategic direction | Remediation priorities |
| **Act** | Treat | Cook/serve | Book & travel | Execute strategy | Execute initiatives | Fix/refactor/deploy |
| **Evaluate** | Clinical response | Guest response | Trip experience | Market response | Performance vs. goals | Test/quality results |
| **Adapt** | Change treatment | Adjust menu | Adjust plans mid-trip | Revise strategy | Revise strategy | Correct/retest |
| **Follow-up** | Continued care | Lessons for next event | Lessons for next trip | Ongoing monitoring | Periodic review | Regression/continuous quality |

**Table 2. Use Case Process/Activity/Task Decompoisition (Part B)**

| General phase | Engineering | Procurement | Research | Scientific investigation | Incident response | Personal decision making |
| --- | --- | --- | --- | --- | --- | --- |
| **Frame** | Requirements | Sourcing need | Research question | Hypothesis | Incident detected | The decision to make |
| **Understand** | Constraints | Requirements & stakeholders | Prior work | Background theory | Impact & scope | Values & constraints |
| **Investigate** | Design options | Vendors & market | Experiments/data | Run experiments | Root cause | Options |
| **Decide** | Select design | Select vendor | Interpret results | Analyze results | Remediation plan | Choose |
| **Act** | Build | Contract & purchase | Publish/apply findings | Report findings | Contain & fix | Act |
| **Evaluate** | Test/validate | Delivery & performance | Peer feedback/replication | Reproducibility | Resolution | Reflect on outcome |
| **Adapt** | Revise design | Renegotiate/switch vendor | Revise hypothesis/method | Revise hypothesis/method | Revise runbooks/systems | Adjust course |
| **Follow-up** | Monitor in service | Manage relationship | Plan follow-on research | Extend investigation | Preventive actions | Track long-term result |

## Case Study: Consort Diagnostic Process (CDP)

### End-to-end Process Decomposition (Medical Care)

**Table 3. Process Decomposition (Medical Care)**

| Stage | Core question | Typical activity |
|---|---|---|
| **1. Observe** | *What is happening?* | Symptoms, signs, history, patient-reported information |
| **2. Assess** | *How significant is it?* | Clinical assessment, risk, severity, urgency, differential considerations |
| **3. Investigate** | *What evidence do we need?* | Physical examination, labs, imaging, tests, consultations |
| **4. Diagnose** | *What is causing it?* | Interpret evidence; establish or revise diagnosis |
| **5. Plan** | *What should we do?* | Goals, options, risks/benefits, treatment strategy |
| **6. Prescribe / Order** | *What specifically is to be done?* | Medication, procedure, therapy, referral, monitoring orders |
| **7. Treat / Intervene** | *Execute the plan.* | Medication, surgery, therapy, behavioral intervention, etc. |
| **8. Monitor** | *Is it working?* | Response, side effects, new evidence, adherence, measurements |
| **9. Reassess** | *What have we learned?* | Compare outcome with expected outcome |
| **10. Adapt** | *What should change?* | Continue, modify, escalate, de-escalate, or stop treatment |
| **11. Follow up / Close** | *What happens next?* | Recovery, maintenance, prevention, surveillance—or return to assessment |

### Closed-loop Control Process

The important architectural point is that these processes aren't a linear pipeline.

> Observe → Assess → Investigate → Diagnose → Plan → Order → Treat → Monitor → Reassess → Adapt → Follow up → Observe

And several loops can occur inside it. For example:

> Assess → Investigate → Diagnose

may loop repeatedly as new evidence appears.

> Treat → Monitor → Reassess → Adapt → Treat

is the therapeutic feedback loop.

### Orthogonal Process Abstraction

The Orthogonal Process Abstraction reduces these use case processes to six fundamental functions:

> 1. SENSE — acquire information
> 2. UNDERSTAND — interpret information and establish the clinical state
> 3. DECIDE — select what ought to happen
> 4. ACT — intervene
> 5. MONITOR — measure consequences
> 6. ADAPT — modify the course based on consequences

Then:

> Sense → Understand → Decide → Act → Monitor → Adapt

That abstraction is interesting in the context of the coordination architecture you've been developing because diagnosis and treatment become instances of a much more general sense–understand–decide–act–feedback cycle, rather than being treated as uniquely medical operations.

### CDP Actor Sample Roles/Personas

> - Patient
> - Observer
> - Clinician
> - Investigator
> - Diagnostician
> - Planner
> - Prescriber
> - Treatment Provider
> - Monitor
> - Follow-up Coordinator

## Patient Medical Care Process: Prototype Consort 0.20 Prompt

```
! coordinate an end-to-end clinical diagnosis and treatment process from initial presentation through follow-up and adaptive care

# The process concerns one patient presenting with a health concern. The objective is to establish the patient's current clinical state, determine an appropriate diagnosis, select and execute an appropriate intervention, evaluate the response, and adapt or conclude care based on subsequent evidence.

$ Treat patient safety, uncertainty, contraindications, and escalation requirements as first-class considerations.
$ Do not invent clinical findings, test results, diagnoses, medications, treatment responses, or other patient facts.
$ Distinguish observed facts, patient-reported information, clinical interpretations, hypotheses, decisions, actions, and outcomes.
$ Preserve uncertainty when the available evidence does not justify a definitive conclusion.
$ A diagnosis is a clinical conclusion supported by the available evidence, not merely a label inferred from symptoms.
$ A treatment decision must be appropriate to the established or currently most-supported clinical state and the available evidence.
$ Monitoring and reassessment may require returning to investigation, diagnosis, planning, or treatment when new evidence warrants it.
$ If the available information indicates an emergency or potentially life-threatening condition, prioritize appropriate urgent escalation over completion of the normal sequence.
% final clinical coordination record containing the current clinical state, evidence, diagnosis or differential diagnosis, treatment plan, interventions, response, unresolved uncertainty, and required follow-up

| observe: collect and organize the patient's presenting symptoms, signs, history, relevant background, patient-reported concerns, and other available observations. Clearly distinguish observed or reported information from assumptions.

| assess: evaluate the significance, severity, urgency, risk, and completeness of the available information. Identify immediate concerns, relevant risk factors, missing information, and whether urgent escalation is indicated.

| investigate: determine and obtain the additional clinical evidence needed to distinguish among plausible explanations. Consider physical examination, laboratory testing, imaging, monitoring, specialist consultation, and other appropriate investigations. Interpret the resulting evidence without treating unperformed investigations as completed.

| diagnose: synthesize the observations, assessment, and investigation results into the most-supported clinical diagnosis or differential diagnosis. State the supporting evidence, contradictory evidence, significant uncertainty, and any findings that require further investigation.

| plan: establish the objectives of care and select the appropriate management strategy based on the diagnosis, differential diagnosis, patient circumstances, risks, benefits, alternatives, preferences, and remaining uncertainty.

| prescribe: translate the treatment plan into specific clinical orders, prescriptions, referrals, procedures, therapies, monitoring requirements, precautions, and patient instructions as appropriate. Distinguish recommendations from actions that have actually been ordered or authorized.

| treat: execute or coordinate the authorized interventions. Record what intervention was actually performed, by whom, when relevant, and any immediate observations or complications.

| monitor: observe the patient's response to treatment and collect relevant follow-up evidence, including clinical status, measurements, symptoms, adverse effects, adherence, and other indicators of treatment effectiveness or deterioration.

| reassess: compare the patient's current state with the expected response and the original clinical assessment. Determine whether the evidence indicates improvement, deterioration, no meaningful change, an adverse effect, a new condition, or unresolved uncertainty.

| adapt: determine the appropriate next action from the reassessment. Continue the current treatment when appropriate; modify, escalate, de-escalate, discontinue, or replace treatment when warranted; or return to investigation, diagnosis, or planning when new evidence changes the clinical picture. Explicitly identify the reason for any change.

| followup: establish the next clinical checkpoint, monitoring requirements, preventive or maintenance care, unresolved issues, escalation criteria, and conditions under which the patient should return for reassessment. Conclude the episode only when the available evidence supports closure or transition to ongoing care.
```

## Two-Level CDP Process Architecture

The following provides a useful two-level architecture: the six orthogonal coordination functions are generic, while Observe, Assess, Investigate, Diagnose, Plan, Prescribe, Treat, etc. are a particular domain's decomposition of them.

- SENSE
  → Observe + Assess + Investigate  
- UNDERSTAND
  → Diagnose  
- DECIDE
  → Plan + Prescribe  
- ACT
  → Treat  
- MONITOR
  → Monitor  
- ADAPT
  → Reassess + Adapt + Follow-up

## Problem-solving/coordination Cycle: A Generalization

While the domain supplies the vocabulary and specialized operations, the general pattern I would abstract the medical workflow to something like:

> FRAME → UNDERSTAND → INVESTIGATE → DECIDE → ACT → EVALUATE → ADAPT

or, even more fundamentally:

> UNDERSTAND → DECIDE → ACT → LEARN → ADAPT

The key is that this is not a waterfall. It is a closed-loop process.

## Concluding Thoughts 

> “Consort coordinates the process by which intelligent participants understand, decide, act, learn, and adapt.”

That makes the medical example not just one application of Consort, but a useful test case for discovering the underlying coordination primitives. And the fact that the same structure naturally fits a dinner menu, competitive analysis, and software quality is a pretty strong signal.