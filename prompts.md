# Canine Thorax Prompt Specification

## Purpose and scope

This document describes the prompt rules used to classify 20 thoracic
conditions in canine radiology reports. The model receives only the report's
Findings and Conclusions and returns one
`Positive` or `Negative` label per condition.

The condition-specific prompt text loaded by the applications is maintained
in [`prompts.json`](./prompts.json). The shared master instructions and prompt
assembly are implemented in [`main_new.py`](./main_new.py) and the separate
local-model runner [`main.py`](./main.py). `prompts.py` is a separate Python
prompt definition and is not loaded by either application; changes to the
runtime prompt should be made in `prompts.json`, and parallel edits to
`prompts.py` should be kept deliberate to avoid divergence.
[`main_gemini.py`](./main_gemini.py) is a separate batch utility with its own
system prompt and prompt hash; use `main_new.py` for the two-matrix study
evaluation.

## Shared master instructions

The following rules apply to all 20 conditions and take precedence over
conflicting or broader wording in an individual condition prompt.

1. **Use the approved report sections.** Evaluate Findings and Conclusions
   together. Recommendations are not sent to the model. References to
   "findings" in an individual condition prompt refer to both supplied report
   sections.
2. **Ground labels in the report.** Label a target abnormality `Positive` when
   the report describes it or a clear descriptive equivalent. The exact
   condition name is not required.
3. **Apply the advisor's interpretation of alternatives.** Diagnoses linked
   with "versus" are included possibilities and count as `Positive`. A
   diagnosis given lesser consideration also counts as `Positive` when the
   report still presents it as a possible explanation. Do not infer a finding
   from clinical history or a test recommendation alone.
4. **Distinguish uncertainty from an affirmed finding.** An explicitly absent,
   normal, resolved, or excluded finding is `Negative`. Do not turn an
   affirmed finding `Negative` only because its cause is uncertain. Follow the
   advisor's condition-specific examples for equivocal or suspected
   cardiomegaly.
5. **Apply age exclusion narrowly.** Exclude a finding as age-related only
   when the report explicitly characterizes the target finding itself as a
   normal or benign age-related variant. The patient's age alone is not
   sufficient reason to label a finding negative.
6. **Keep generalized and sided cardiomegaly distinct.** A specifically
   left-sided or right-sided enlargement is scored in its corresponding
   side-specific condition and does not, by itself, establish generalized
   cardiomegaly. When generalized or unspecified cardiomegaly is `Positive`,
   both left-sided and right-sided cardiomegaly are also set to `Positive`,
   unless the enlargement was excluded as a normal age-related variant.
   The advisor's Case 75 example is a specific exception for equivocal
   left-sided cardiomegaly: generalized cardiomegaly `Negative`, left-sided
   cardiomegaly `Positive`, and right-sided cardiomegaly `Negative`. A
   suspected right-sided enlargement is positive for the right-sided
   condition.
7. **Apply condition-specific advisor clarifications.** `diseased_lungs`
   includes bronchitis, diffuse bronchial pattern, and viral or allergic lung
   disease. `pulmonary_nodules` includes a pulmonary mass or soft-tissue mass,
   but not an osteoma. `rtm` includes a slightly undulant, well-defined dorsal
   tracheal margin, but excludes tracheal collapse and tracheomalacia.
   `thoracic_lymphadenopathy` includes thoracic lymphadenomegaly and thoracic
   lymph-node/mass findings only. `focal_caudodorsal_lung` includes a focal
   caudal lung finding; focal findings may be multifocal.

## Condition inventory

| Condition key | Target finding |
|---|---|
| `perihilar_infiltrate` | Active infiltrate in the perihilar region |
| `pneumonia` | Pneumonia |
| `bronchitis` | Bronchitis |
| `interstitial` | Interstitial lung pattern |
| `diseased_lungs` | Generalized lung disease or diseased lungs |
| `hypo_plastic_trachea` | Hypoplastic or abnormally narrowed trachea |
| `cardiomegaly` | Generalized or unspecified cardiac enlargement |
| `left_sided_cardiomegaly` | Left-sided cardiac enlargement |
| `right_sided_cardiomegaly` | Right-sided cardiac enlargement |
| `pulmonary_nodules` | Pulmonary nodules, masses, or nodular opacities |
| `pleural_effusion` | Pleural effusion |
| `rtm` | Redundant tracheal membrane |
| `focal_caudodorsal_lung` | Focal caudodorsal lung opacity or infiltrate |
| `focal_perihilar` | Focal perihilar opacity or change |
| `pulmonary_hypoinflation` | Pulmonary hypoinflation |
| `pericardial_effusion` | Pericardial effusion |
| `bronchiectasis` | Bronchiectasis |
| `pulmonary_vessel_enlargement` | Pulmonary vessel enlargement |
| `thoracic_lymphadenopathy` | Thoracic lymphadenopathy |
| `esophagitis` | Active esophagitis or esophageal disease |

The model must return exactly 20 labels, in the same order as the condition
columns selected from the input workbook. Each label must be `Positive` or
`Negative`, separated by commas, with no explanation or other text.

## Cardiomegaly decision rules

- Mark generalized `cardiomegaly` positive only when generalized or unspecified
  enlargement of the cardiac silhouette is affirmed.
- Score an explicitly sided enlargement in its matching side-specific
  condition. Do not infer generalized cardiomegaly from a one-sided finding
  alone.
- If generalized cardiomegaly is positive, the application enforces positive
  labels for both `left_sided_cardiomegaly` and `right_sided_cardiomegaly`.
- Apply age exclusion only if the enlargement itself is explicitly described
  as a normal or benign age-related variant. Age alone or a possible
  age-related cause is not enough to exclude an affirmed enlargement.

## Label interpretation

| Report evidence | Labeling principle |
|---|---|
| Target finding is affirmed, including by a clear descriptive equivalent | `Positive` |
| Target finding is explicitly absent, normal, or resolved | `Negative` |
| Target finding is explicitly equivocal, unlikely, or inconclusive | `Negative` |
| Finding is affirmed, but its cause is uncertain | Label the finding itself; do not treat cause uncertainty as absence |
| Diagnoses linked by "versus" | Count each included possible diagnosis as `Positive` |
| A diagnosis receives lesser consideration but remains a possible explanation | `Positive` |
| Finding is mentioned only in history or as a reason for a recommended test | `Negative` unless the report independently supports the finding |
| Target finding itself is explicitly described as a normal or benign age-related variant | `Negative` |
| Patient is older, but the report does not explicitly classify the target finding as a normal age-related variant | Do not apply age exclusion |

## Evaluation and quality assurance

Prompt changes should be evaluated against reviewed cases with known
Gold Standard labels. Inspect false positives and false negatives by condition,
and verify that age-related exclusions and the cardiomegaly consistency rule
behave as intended. A higher true-positive count alone is not evidence of
improved performance; changes must be checked against both missed positives
and false positives.

After changing prompt text, score a small test batch again and review its
Scored_Data_Rows and confusion matrices before processing a larger cohort.
Previously generated workbooks are not updated when the prompt changes.

## Provider, privacy, and reproducibility

The repository supports two execution paths. The original
[`main_new.py`](./main_new.py) uses hosted Gemini by default
(`gemini-3.8-flash`) or selectable OpenAI; these require API credentials and
are subject to provider terms, quotas, and pricing. Verify current availability
and data-use terms before using either hosted provider.

The 100-case cohort run completed on 2026-10-30 with the separate local
Ollama runner [`main.py`](./main.py), using **`qwen3:4b`** at
`http://localhost:11434` (Ollama's native local API). This model was installed
locally; the run did not use a hosted-model API key or incur per-request API
charges. Local inference still uses the computer's memory, CPU/GPU, and
electricity. Record the exact model and runner with results; the model can be
overridden with `OLLAMA_MODEL`.

Both runners use the condition prompts in `prompts.json` and send only
Findings and Conclusions from each scored report. The local runner scores the
radiologist report and existing AI report; `main_new.py` does the same when
using a hosted provider. Recommendations are not sent. Do not upload Vetology
data, source workbooks, or generated results to GitHub or another publicly
accessible location. Generated workbooks omit source report text; study
workbooks contain case IDs, Gold Standard labels, model labels, evaluation
matrices, and run metadata. Do not include patient reports or identifiable
case-level information in papers or other project records.

The completed local run used prompt version `2026-10-29.2` and produced
[`confusion_metrics_canine_thorax_Ollama_qwen3_4b_100cases_20261030_114434.xlsx`](./confusion_metrics_canine_thorax_Ollama_qwen3_4b_100cases_20261030_114434.xlsx).
Matrix 1 compares model labels from the radiologist report with model labels
from the AI report. Matrix 2 compares radiologist-report model labels with
the Gold Standard.

## Prompt change record

- Added atomic, per-case local checkpoints and `--resume` support for quota-
  limited runs. Resume checks the source workbook hash and model/prompt/run
  metadata, skips completed cases, and only generates matrices after the
  requested cohort is complete. Checkpoints exclude report text.
- Stop retrying immediately on Gemini `RESOURCE_EXHAUSTED`/429 responses;
  short exponential retries cannot recover a daily quota.
- Aligned report input with advisor guidance: only Findings and Conclusions
  are submitted; Recommendations are excluded.
- Made Gemini the default provider and selected `gemini-3.8-flash` as the
  default model, with local model overrides retained.
- Changed Gemini output to a schema-constrained JSON array, increased the
  output budget to 512 tokens, and set low thinking to avoid truncated
  label lists. Invalid responses report safe response metadata, not report
  content.
- Increased transient-failure retries to five attempts with exponential
  backoff after observing Gemini 503 high-demand responses.
- Added run metadata for the resolved model identifier, prompt version and
  hash, report sections, temperature, thinking level, output budget, and UTC
  timestamp.
- Removed source report text from generated workbooks; only case IDs, labels,
  evaluation matrices, and run metadata are exported.
- Applied the same report-section, structured-output, and export safeguards
  to the standalone `main_gemini.py` batch utility; its distinct prompt has a
  separate version identifier and hash.

### 

- Added instructions to evaluate Findings, Conclusions, and
  Recommendations together.
- Clarified that descriptive equivalents can support a positive label, while
  history, recommendations, and differential diagnoses alone cannot.
- Narrowed age exclusion so that age alone or an age-related cause listed as a
  possibility does not override an affirmed abnormality.
- Distinguished generalized cardiomegaly from left- and right-sided
  enlargement and enforced side-label propagation when generalized
  cardiomegaly is positive.
- Incorporated the Week 2 advisor examples: "versus" alternatives and
  diagnoses given lesser consideration count as positive possibilities;
  diseased-lung scope includes bronchitis, diffuse bronchial pattern, and
  viral/allergic lung disease; pulmonary masses count as nodules but osteoma
  does not; RTM includes an undulant dorsal membrane but not collapse or
  tracheomalacia; thoracic node terminology is limited to the thorax; focal
  caudal findings and multifocal focal findings are included; and the
  cardiomegaly labels follow the advisor's equivocal/suspected examples.
- Retained `prompts.json` as the application runtime prompt source. The
  change rationale is also recorded in [`prompt_changelog.md`](./prompt_changelog.md).
