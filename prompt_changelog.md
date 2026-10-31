
Master Veterinary Radiology Prompt Definitions Repository

Project: Vetology AI Training Program — Thoracic Diagnostic Classification
Author: Asmita
Active Baseline Scope: 20 Target Conditions (Canine Thorax Cohort Validation)
Configuration Reference File: prompts.json (Decoupled application configuration profile)

2026-10-29 Advisor Guidance and Gemini Output Update

1. Submit only Findings and Conclusions from the radiologist and existing AI reports to the LLM; Recommendations are excluded.
2. Use Gemini by default with `gemini-3.8-flash` as the configurable default model. The advisor approved use of the free-tier service and its data-use terms; verify current model availability and terms before a run.
3. Request an exact JSON array of 20 Positive/Negative labels using Gemini's structured output schema, a 512-token output limit, and LOW thinking. The model rejects MINIMAL thinking. This avoids truncated label lists observed with the earlier 150-token limit. Invalid responses report finish reason and token counts without including report text. Failed calls retry up to five times with exponential backoff to handle transient high-demand responses.
4. Generated workbooks no longer include source report text. They record provider, requested and resolved model identifiers, prompt version/hash, temperature, thinking level, output token limit, report sections, and UTC run time.
5. Matrix 1 compares AI-scored LLM labels from the radiologist report against AI-scored LLM labels from the AI report. Matrix 2 compares radiologist-report LLM labels against the Gold Standard.
6. Do not publish Vetology data or include patient reports or identifiable case-level information in papers or project records.

Prompt Review Update

The shared scoring instructions in main_new.py now clarify the following:
1. Evaluate Findings, Conclusions, and Recommendations together. References to "findings" in an individual condition prompt mean all supplied report sections.
2. Count an affirmatively described target finding, including a clear descriptive equivalent, as Positive without requiring the exact condition name. Do not infer a finding from history, a recommendation, or a differential alone.
3. Apply age exclusion only when the report explicitly identifies the target finding itself as a normal or benign age-related variant. Age alone or an age-related cause listed as one possibility does not exclude an otherwise affirmed abnormality.
4. Treat generalized cardiomegaly separately from one-sided enlargement. A Positive generalized cardiomegaly label is propagated to both left- and right-sided cardiomegaly labels in code.
5. Apply the Week 2 advisor's condition-specific guidance: "versus" alternatives and diagnoses given lesser consideration remain positive possibilities; diseased_lungs includes bronchitis, diffuse bronchial pattern, and viral/allergic disease; pulmonary masses count as nodules but osteoma does not; RTM includes an undulant dorsal membrane but not collapse/tracheomalacia; thoracic lymph-node terminology applies only within the thorax; focal caudal findings and multifocal focal findings are included; and cardiomegaly labels follow the advisor's equivocal-left and suspected-right examples.
6. Added selectable OpenAI and Gemini providers. Provider/model identifiers are saved in output metadata and filenames so results remain attributable for the methods section; OpenAI remains the default provider.

The active runtime configuration is prompts.json; prompts.py is a separate prompt definition and is not loaded by main_new.py. The generalized age-interpretation rules above take precedence over broader wording in individual prompts. The cardiomegaly rule was clarified in both prompt files.

1. Global Prompting Guardrails

The shared scoring instructions and condition-specific rules are applied together:
1. An affirmatively described target abnormality or clear descriptive equivalent may be Positive even when the exact condition name is not used.
2. Explicitly absent, normal, resolved, equivocal, or unlikely findings are Negative. A differential diagnosis alone is not sufficient evidence.
3. Age exclusion applies only when the target finding itself is explicitly characterized as a normal or benign age-related variant. Patient age alone or an age-related differential does not negate an affirmed abnormality.
4. Generalized cardiomegaly is distinct from one-sided enlargement. A Positive generalized cardiomegaly label sets both side-specific labels to Positive.

2. Deep-Dive Condition Engineering Definitions


Perihilar Infiltrate (perihilar_infiltrate)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of an active perihilar infiltrate.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if a perihilar infiltrate is explicitly stated as present, visible, increased, or highly consistent with the images.
	2. Respond 'Negative' if a perihilar infiltrate is explicitly noted as absent, normal, clear, or resolved.
	3. MASTER AGE EXCLUSION RULE: If the finding or opacity is explicitly described as a normal 'age-related condition', 'age-related change', or normal variant for an older animal, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Pneumonia (pneumonia)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of active pneumonia.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if pneumonia is explicitly stated as present, visible, highly likely, or consistent with the images.
	2. Respond 'Negative' if pneumonia is explicitly noted as absent, normal, clear, or ruled out.
	3. MASTER AGE EXCLUSION RULE: If the finding or opacity is explicitly described as a normal 'age-related condition', 'age-related change', or normal variant for an older animal, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Bronchitis (bronchitis)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of active bronchitis.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if bronchitis is explicitly stated as present, visible, chronic, or highly consistent with the images.
	2. Respond 'Negative' if bronchitis is explicitly noted as absent, normal, clear, or ruled out.
	3. MASTER AGE EXCLUSION RULE: If the finding or airway pattern is explicitly described as a normal 'age-related condition', 'age-related change', or normal variant for an older animal, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Interstitial Lung Pattern (interstitial)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of an active interstitial lung pattern.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if an interstitial pattern, markings, or lung changes are explicitly stated as present, visible, or highly consistent with the images.
	2. Respond 'Negative' if the interstitial space is explicitly noted as normal, clear, unaffected, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If the lung markings are explicitly described as a normal 'age-related condition', 'age-related change', or normal variant for an older animal, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Unspecified/Generalized Cardiomegaly (cardiomegaly)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of active cardiomegaly (heart enlargement).[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if cardiomegaly, generalized cardiac enlargement, or specific left/right heart enlargement is explicitly stated as present or consistent with the images.
	2. Respond 'Negative' if the heart size is explicitly noted as normal, clear, or unremarkable.
	3. MASTER CARDIOMEGALY RULE: If generalized or unspecified cardiomegaly is 'Positive', then BOTH left-sided and right-sided cardiomegaly must be considered positive in your evaluation assessment.
	4. MASTER AGE EXCLUSION RULE: If cardiomegaly or cardiac changes are explicitly described as a normal age-related change, senile variation, or expected change due to old age, you MUST classify this as 'Negative' and rule it out.
	5. CRITICAL HEDGING RULE: If the report expresses absolute uncertainty, states the condition is 'equivocal left-sided cardiomegaly' without general enlargement, or uses 'cardiomegaly is unlikely', classify this main general category as 'Negative'.
	6. If the text is completely missing or inconclusive, respond 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Left-Sided Cardiomegaly (left_sided_cardiomegaly)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of left-sided cardiomegaly.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' if left-sided cardiac enlargement, left atrial enlargement, left ventricular enlargement, or generalized 'cardiomegaly' is explicitly stated as present.
	2. Respond 'Negative' if the left side of the heart is normal, clear, or unaffected.
	3. MASTER OVERRIDE RULE: If generalized 'cardiomegaly' is confirmed positive anywhere in the report, this specific left-sided chamber column MUST also be marked as 'Positive'.
	4. MASTER AGE EXCLUSION RULE: If the change is explicitly described as a normal age-related condition or senile change, classify as 'Negative' and rule it out.
	5. If the text is completely missing, irrelevant, or inconclusive, respond 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Right-Sided Cardiomegaly (right_sided_cardiomegaly)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of right-sided cardiomegaly.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' if right-sided cardiac enlargement, right atrial enlargement, right ventricular enlargement, or generalized 'cardiomegaly' is explicitly stated as present.
	2. Respond 'Negative' if the right side of the heart is normal, clear, or unaffected.
	3. MASTER OVERRIDE RULE: If generalized 'cardiomegaly' is confirmed positive anywhere in the report, this specific right-sided chamber column MUST also be marked as 'Positive'.
	4. MASTER AGE EXCLUSION RULE: If the change is explicitly described as a normal age-related condition or senile change, classify as 'Negative' and rule it out.
	5. If the text is completely missing, irrelevant, or inconclusive, respond 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Diseased Lungs (diseased_lungs)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of active generalized lung disease or diseased lungs.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if the lungs are explicitly stated as diseased, showing generalized severe pathology, or diffuse abnormal lung tissue changes.
	2. Respond 'Negative' if the lungs are explicitly noted as normal, clear, healthy, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If the pulmonary field change is explicitly described as a normal 'age-related condition', 'age-related change', or normal variant for an older animal, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Pulmonary Nodules (pulmonary_nodules)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of pulmonary nodules.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if pulmonary nodules, soft tissue masses, or nodular opacities are explicitly stated as present or highly consistent with the images.
	2. Respond 'Negative' if nodules are explicitly noted as absent, normal, clear, or ruled out.
	3. MASTER AGE EXCLUSION RULE: If the finding or opacity is explicitly stated to be a normal age-related condition, heterotopic bone/osteoma, or change due to aging, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Pleural Effusion (pleural_effusion)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of pleural effusion.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if pleural effusion, fluid in the pleural space, or pleural thickening is explicitly stated as present.
	2. Respond 'Negative' if the pleural space is explicitly noted as normal, clear, clear of fluid, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If the fluid signature is explicitly stated to be a normal age-related variation, or if the report uses phrases like 'no evidence of pleural effusion', you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Redundant Tracheal Membrane (rtm)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of Redundant Tracheal Membrane (RTM).[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if a redundant dorsal tracheal membrane or RTM is explicitly stated as present, visible, or redundant.
	2. Respond 'Negative' if the tracheal membrane is normal, taut, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If the membrane signature is explicitly stated to be a normal age-related change, laxity due to age, or normal variant, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Focal Caudodorsal Lung Opacity (focal_caudodorsal_lung)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of a focal caudodorsal lung opacity/infiltrate.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if an opacity, infiltrate, or lesion is explicitly stated as present within the caudodorsal lung field.
	2. Respond 'Negative' if the caudodorsal fields are explicitly noted as clear, normal, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If the structural opacity is explicitly stated to be a normal age-related change, senile variation, or expected old age variant, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Focal Perihilar Opacity (focal_perihilar)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of a focal perihilar opacity/change.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if a localized, focal opacity or lesion is explicitly stated as present in the perihilar region.
	2. Respond 'Negative' if the perihilar fields are explicitly noted as clear, normal, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If the localized density is explicitly stated to be a normal age-related change, senile modification, or age variant, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Pulmonary Hypoinflation (pulmonary_hypoinflation)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of pulmonary hypoinflation (under-inflated lungs).[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if pulmonary hypoinflation, shallow inspiration, or under-inflation is explicitly stated as present.
	2. Respond 'Negative' if lung inflation is noted as adequate, fully inspired, normal, or clear.
	3. MASTER AGE EXCLUSION RULE: If the under-inflation is explicitly noted as a normal age-related baseline change or senile elasticity loss, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Pericardial Effusion (pericardial_effusion)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of pericardial effusion (fluid around the heart).[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if pericardial effusion, fluid in the pericardial sac, or global cardiac enlargement consistent with fluid is explicitly stated as present.
	2. Respond 'Negative' if the pericardium is explicitly noted as normal, clear, or clear of fluid.
	3. MASTER AGE EXCLUSION RULE: If the fluid signature is explicitly stated to be a normal age-related variant, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Bronchiectasis (bronchiectasis)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of bronchiectasis (irreversible destruction and dilation of airways).[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if bronchiectasis or severe permanent bronchial dilation is explicitly stated as present.
	2. Respond 'Negative' if the bronchi are explicitly noted as uniform, normal, or clear.
	3. MASTER AGE EXCLUSION RULE: If the airway dilation is explicitly described as a normal age-related change/ectasia rather than active pathology, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Pulmonary Vessel Enlargement (pulmonary_vessel_enlargement)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of pulmonary vessel enlargement.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if pulmonary arteries, pulmonary veins, or general pulmonary vasculature is explicitly stated as enlarged, distended, congested, or prominent.
	2. Respond 'Negative' if the pulmonary vessels are noted as normal in caliber, unremarkable, or clear.
	3. MASTER AGE EXCLUSION RULE: If prominent vessels are explicitly noted as a normal age-related variation, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Thoracic Lymphadenopathy (thoracic_lymphadenopathy)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of thoracic lymphadenopathy (enlarged lymph nodes inside the chest).[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if thoracic, sternal, mediastinal, or tracheobronchial lymph nodes are explicitly stated as enlarged, reactive, or mass-like.
	2. Respond 'Negative' if the thoracic lymph nodes are noted as normal, not seen, clear, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If a node change is explicitly described as a benign age-related condition or structural aging, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report uses phrases like 'no clear evidence', 'unlikely', or 'no signs seen', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:

Esophagitis (esophagitis)

• Prompt Architecture Block:
You are an expert veterinary data scientist and radiologist scorer.[TASK]
Analyze the provided radiology report text and determine if there is definitive evidence of active esophagitis or esophageal disease.[CLINICAL GROUNDING RULES]
	1. Respond 'Positive' ONLY if esophagitis, esophageal dilation, megaesophagus, or active esophageal inflammation is explicitly stated as present.
	2. Respond 'Negative' if the esophagus is explicitly noted as normal, clear, empty, or unremarkable.
	3. MASTER AGE EXCLUSION RULE: If structural esophageal dilation or changes are explicitly noted as a benign age-related condition or senile loss of muscle tone, you MUST classify this as 'Negative' and rule it out.
	4. CRITICAL HEDGING RULE: If the report uses phrases like 'no signs of esophagitis', classify as 'Negative'.
[OUTPUT FORMAT]
Respond ONLY with either the single word 'Positive' or 'Negative'. Do not include punctuation, introductory text, or spaces.[DATA TO ANALYZE]
Below is the radiologist text. Evaluate it now:
