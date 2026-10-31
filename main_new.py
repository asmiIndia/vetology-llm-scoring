# main_new.py
# Vetology canine thorax scoring
#
# Reads a manually reviewed workbook, sends only Findings and Conclusions
# from each report to the selected LLM, and creates:
#   1. Scored_Data_Rows
#   2. Matrix_1_Radiologist
#   3. Matrix_2_Your_LLM
#
# Generated workbooks omit source report text. Keep all Vetology data local.

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import dotenv
import openpyxl
import pandas as pd
from openai import OpenAI
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


dotenv.load_dotenv()

OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_THINKING_LEVEL = "LOW"
GEMINI_MAX_OUTPUT_TOKENS = 512
# Bump this when the runtime prompt or scoring interpretation changes.
PROMPT_VERSION = "2026-10-29.2"

# Default to a small validation run; request the full cohort explicitly only
# after reviewing the test output.
TEST_CASE_LIMIT = 2

# The Gold Standard condition columns occupy zero-based positions 8 through
# 27 in the approved workbook layout.
GOLD_STANDARD_COLUMNS_START = 8
GOLD_STANDARD_COLUMNS_END = 28

ORIGINAL_REPORT_COLUMNS = (
    "Findings (original radiologist report)",
    "Conclusions (original radiologist report)",
)
EXISTING_AI_REPORT_COLUMNS = (
    "Findings (AI report)",
    "Conclusions (AI report)",
)

OUTPUT_PREFIX = "confusion_metrics_canine_thorax"


def retrieve_isolated_prompt_configs(profile_path):
    """Load the 20 condition-specific prompts from prompts.json."""
    with open(profile_path, "r", encoding="utf-8") as prompt_file:
        prompts = json.load(prompt_file)

    if not isinstance(prompts, dict):
        raise ValueError("prompts.json must contain a JSON object.")

    return prompts


def compile_diagnostic_instruction_template(prompt_templates, condition_names):
    """
    Build one ordered system prompt from the condition-specific JSON prompts.

    Only TASK and CLINICAL GROUNDING RULES are included; each prompt's
    individual output-format instructions are replaced by the shared output
    contract at the end of the assembled prompt.
    """
    condition_instructions = []

    for condition in condition_names:
        if condition not in prompt_templates:
            raise ValueError(f"Missing prompt for condition: {condition}")

        prompt_text = prompt_templates[condition]

        task_match = re.search(
            r"\[TASK\]\s*(.*?)\s*\[CLINICAL GROUNDING RULES\]",
            prompt_text,
            re.DOTALL,
        )
        rules_match = re.search(
            r"\[CLINICAL GROUNDING RULES\]\s*(.*?)\s*\[OUTPUT FORMAT\]",
            prompt_text,
            re.DOTALL,
        )

        if not task_match or not rules_match:
            raise ValueError(
                "Prompt format must contain [TASK], "
                "[CLINICAL GROUNDING RULES], and [OUTPUT FORMAT] "
                f"for condition: {condition}"
            )

        task_text = task_match.group(1).strip()
        clinical_rules = rules_match.group(1).strip()

        condition_instructions.append(
            f"CONDITION: {condition}\n"
            f"TASK:\n{task_text}\n"
            f"CLINICAL GROUNDING RULES:\n{clinical_rules}"
        )

    return (
        "You are an expert veterinary data scientist and radiologist "
        "scorer.\n\n"
        "Evaluate the supplied Findings and Conclusions text against each "
        "condition below. Any condition prompt that refers to 'findings' "
        "means all supplied report sections. "
        "Follow the "
        "condition-specific task and rules, subject to these master rules:\n"
        "1. Label an abnormality Positive when the report describes the "
        "target finding or a clear equivalent, even if it does not use the "
        "exact name. For this assignment, alternatives explicitly linked by "
        "'versus' are included possibilities and count as Positive. A "
        "diagnosis "
        "given lesser consideration also counts as Positive when the report "
        "still presents it as a possible explanation. Do not infer findings "
        "from clinical history or a test recommendation alone.\n"
        "2. Label a finding Negative when it is explicitly absent, normal, or "
        "resolved, or when the report explicitly excludes it. Do not turn an "
        "affirmed finding Negative solely because its cause is uncertain. "
        "Follow the advisor's condition-specific guidance for equivocal or "
        "suspected cardiomegaly below.\n"
        "3. Apply age exclusion only when the report explicitly characterizes "
        "the specific target finding as a normal/benign age-related variant. "
        "The patient's age alone, or age-related change listed as one "
        "possible "
        "cause among alternatives, is not sufficient to exclude an otherwise "
        "affirmed abnormal finding. This rule takes precedence over broader "
        "age wording in an individual condition prompt.\n"
        "4. Cardiomegaly means generalized or unspecified enlargement of the "
        "heart. A specifically left- or right-sided enlargement is scored in "
        "its corresponding side-specific condition, not by itself as "
        "generalized cardiomegaly. An equivocal left-sided cardiomegaly "
        "description is Negative for generalized cardiomegaly, Positive for "
        "left-sided cardiomegaly, and Negative for right-sided cardiomegaly. "
        "A suspected right-sided enlargement is Positive for right-sided "
        "cardiomegaly. If generalized cardiomegaly is Positive, both "
        "left-sided and right-sided cardiomegaly must be Positive, unless the "
        "finding was excluded as a normal age-related variant.\n"
        "5. Condition-specific advisor clarifications: diseased_lungs "
        "includes "
        "bronchitis, diffuse bronchial pattern, and viral or allergic lung "
        "disease; pulmonary_nodules includes a pulmonary mass or soft-tissue "
        "mass but not an osteoma; redundant tracheal membrane includes a "
        "slightly undulant, well-defined dorsal tracheal margin but does not "
        "include tracheal collapse or tracheomalacia; thoracic "
        "lymphadenopathy "
        "includes thoracic lymphadenomegaly or thoracic lymph-node/mass "
        "findings, but not findings outside the thorax; focal caudodorsal "
        "lung "
        "includes a focal caudal lung finding, and focal findings may be "
        "multifocal.\n"
        "Return one label for each condition in the exact order listed.\n\n"
        + "\n\n".join(condition_instructions)
        + "\n\n[OUTPUT FORMAT]\n"
        f"Return a JSON array containing exactly {len(condition_names)} "
        "strings. Each string must be Positive or Negative. Do not include "
        "explanations, numbering, or any text outside the JSON array."
    )


def execute_clinical_evaluation_loop(
    model_client,
    provider,
    model_name,
    operational_system_prompt,
    veterinary_report_content,
    expected_label_count,
    threshold_retries=5,
):
    """Score one report, validate its labels, and return labels plus model ID.

    Retry failures with exponential backoff. Error details deliberately avoid
    printing or persisting report text.
    """
    if pd.isna(veterinary_report_content):
        veterinary_report_content = ""
    veterinary_report_content = str(veterinary_report_content).strip()

    if not veterinary_report_content:
        raise ValueError("The report text is empty; cannot score this report.")

    backoff_seconds = 2.0
    last_error = "The model returned an invalid response."

    for retry_index in range(threshold_retries):
        try:
            if provider == "openai":
                response = model_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": operational_system_prompt,
                        },
                        {
                            "role": "user",
                            "content": (
                                "Radiology report text to evaluate:\n"
                                f"{veterinary_report_content}"
                            ),
                        },
                    ],
                    max_tokens=150,
                    temperature=0.0,
                )
                response_text = response.choices[0].message.content
                resolved_model_name = getattr(response, "model", None)
            elif provider == "gemini":
                from google.genai import types

                # Constrain the response to exactly one allowed label per
                # condition; this prevents partial or explanatory responses.
                response = model_client.models.generate_content(
                    model=model_name,
                    contents=(
                        "Radiology report text to evaluate:\n"
                        f"{veterinary_report_content}"
                    ),
                    config=types.GenerateContentConfig(
                        system_instruction=operational_system_prompt,
                        max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
                        temperature=0.0,
                        response_mime_type="application/json",
                        response_json_schema={
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["Positive", "Negative"],
                            },
                            "minItems": expected_label_count,
                            "maxItems": expected_label_count,
                        },
                        thinking_config=types.ThinkingConfig(
                            thinking_level=GEMINI_THINKING_LEVEL
                        ),
                    ),
                )
                response_text = response.text
                resolved_model_name = getattr(
                    response, "model_version", None
                )
                candidate_list = getattr(response, "candidates", None) or []
                first_candidate = (
                    candidate_list[0] if candidate_list else None
                )
                usage_metadata = getattr(response, "usage_metadata", None)
                finish_reason = getattr(
                    first_candidate, "finish_reason", None
                )
                output_tokens = getattr(
                    usage_metadata, "candidates_token_count", None
                )
                thinking_tokens = getattr(
                    usage_metadata, "thoughts_token_count", None
                )
                response_diagnostics = (
                    f"response_chars={len(response_text or '')}, "
                    f"finish_reason={finish_reason}, "
                    f"output_tokens={output_tokens}, "
                    f"thinking_tokens={thinking_tokens}"
                )
                if not response_text:
                    raise ValueError(
                        "Gemini returned an empty response "
                        f"({response_diagnostics})."
                    )
                try:
                    labels = json.loads(response_text)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "Gemini did not return valid JSON labels "
                        f"({response_diagnostics})."
                    ) from error
                if (
                    not isinstance(labels, list)
                    or len(labels) != expected_label_count
                    or any(
                        not isinstance(label, str)
                        or label not in {"Positive", "Negative"}
                        for label in labels
                    )
                ):
                    raise ValueError(
                        "Gemini returned an invalid label array: expected "
                        f"{expected_label_count} Positive/Negative strings "
                        f"({response_diagnostics})."
                    )
                return labels, resolved_model_name or model_name
            else:
                raise ValueError(f"Unsupported model provider: {provider}")

            if not response_text:
                raise ValueError("The model returned an empty response.")

            response_text = response_text.strip()
            labels = [
                match.group(1).capitalize()
                for match in re.finditer(
                    r"\b(Positive|Negative)\b",
                    response_text,
                    re.IGNORECASE,
                )
            ]

            # OpenAI uses text output here, so reject both missing labels and
            # any non-label content rather than silently accepting a parse.
            leftover = re.sub(
                r"\b(Positive|Negative)\b",
                "",
                response_text,
                flags=re.IGNORECASE,
            )
            leftover = re.sub(r"[\s,;:\-\d.\[\]()]", "", leftover)

            if len(labels) == expected_label_count and not leftover:
                return labels, resolved_model_name or model_name

            last_error = (
                f"Expected {expected_label_count} Positive/Negative labels, "
                f"received {len(labels)}. Extra text: {leftover[:80]!r}"
            )

        except Exception as error:
            last_error = str(error)

            # A free-tier daily quota error will not recover with a short
            # retry delay; save the checkpoint and let the next run resume.
            if provider == "gemini" and (
                "RESOURCE_EXHAUSTED" in last_error or "429" in last_error
            ):
                break

        if retry_index < threshold_retries - 1:
            delay_seconds = backoff_seconds * (2 ** retry_index)
            print(
                f"Model request failed; retrying in {delay_seconds} seconds "
                f"({retry_index + 2}/{threshold_retries})."
            )
            time.sleep(delay_seconds)

    raise RuntimeError(
        f"Scoring failed after {retry_index + 1} attempt(s). "
        f"Last error: {last_error}"
    )


def normalize_label(value):
    """Map supported manual/model encodings to labels; unknowns return None.

    Returning None lets the matrix calculation exclude invalid pairs and
    report their counts instead of treating them as negative.
    """
    if pd.isna(value):
        return None

    value = str(value).strip().upper()

    # Handle numeric values exported as text, such as "1.0" and "0.0".
    value = re.sub(r"\.0$", "", value)

    if value in {"POSITIVE", "ABNORMAL", "1", "TRUE", "POS"}:
        return "Positive"

    if value in {"NEGATIVE", "NORMAL", "0", "FALSE", "NEG"}:
        return "Negative"

    return None


def enforce_generalized_cardiomegaly_consistency(labels, conditions):
    """Propagate positive generalized cardiomegaly to both sided labels.

    This enforces the study's master rule after the model returns labels.
    Side-specific positives do not, on their own, change generalized
    cardiomegaly.
    """
    required_conditions = (
        "cardiomegaly",
        "left_sided_cardiomegaly",
        "right_sided_cardiomegaly",
    )
    missing_conditions = [
        condition
        for condition in required_conditions
        if condition not in conditions
    ]
    if missing_conditions:
        raise ValueError(
            "Cannot enforce cardiomegaly consistency; missing condition(s): "
            + ", ".join(missing_conditions)
        )

    consistent_labels = list(labels)
    if len(consistent_labels) != len(conditions):
        raise ValueError(
            "The number of labels does not match the number of conditions."
        )

    if consistent_labels[conditions.index("cardiomegaly")] == "Positive":
        left_index = conditions.index("left_sided_cardiomegaly")
        right_index = conditions.index("right_sided_cardiomegaly")
        consistent_labels[left_index] = "Positive"
        consistent_labels[right_index] = "Positive"

    return consistent_labels


def combine_report_sections(report_row, columns):
    """Combine only the explicitly supplied report sections for an API call.

    Callers pass the radiologist or existing-AI Findings/Conclusions columns;
    Recommendations and all other workbook fields are intentionally omitted.
    """
    sections = []
    for column in columns:
        value = report_row[column]
        if pd.isna(value):
            continue

        text = str(value).strip()
        if text:
            section_name = column.split(" (", maxsplit=1)[0]
            sections.append(f"{section_name}:\n{text}")

    return "\n\n".join(sections)


def compute_metrics_and_render_tab(
    worksheet,
    ground_truth_dataframe,
    prediction_dataframe,
    conditions,
    prediction_prefix,
    reference_is_gold_standard,
):
    """Write per-condition confusion-matrix metrics, aligning by CaseID.

    `ground_truth_dataframe` supplies the reference labels; `prediction_prefix`
    selects the prediction columns. Matrix 1 uses radiologist-report LLM
    labels as reference and AI-report LLM labels as predictions. Matrix 2 uses
    Gold Standard labels as reference and radiologist-report LLM labels as
    predictions. Matrix 1 therefore measures agreement, not truth accuracy.
    """

    if reference_is_gold_standard:
        reference_count_headers = [
            "Positive Ground Truth",
            "Negative Ground Truth",
            "Ground Truth Check",
        ]
    else:
        reference_count_headers = [
            "Positive LLM Reference",
            "Negative LLM Reference",
            "LLM Reference Check",
        ]

    headers = [
        "condition",
        "True Positive",
        "False Negative",
        "True Negative",
        "False Positive",
        "Sensitivity",
        "Specificity",
        "Check",
        *reference_count_headers,
    ]
    worksheet.append(headers)

    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(
        start_color="2EA3F2",
        end_color="2EA3F2",
        fill_type="solid",
    )
    thin_border = Border(
        left=Side(style="thin", color="000000"),
        right=Side(style="thin", color="000000"),
        top=Side(style="thin", color="000000"),
        bottom=Side(style="thin", color="000000"),
    )

    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )
        cell.border = thin_border

    if "CaseID" not in ground_truth_dataframe.columns:
        raise ValueError("Reference dataframe is missing CaseID.")

    if "CaseID" not in prediction_dataframe.columns:
        raise ValueError("Prediction dataframe is missing CaseID.")

    # Fail rather than silently discard duplicate records.
    if ground_truth_dataframe["CaseID"].duplicated().any():
        raise ValueError("Reference dataframe contains duplicate CaseIDs.")

    if prediction_dataframe["CaseID"].duplicated().any():
        raise ValueError("Prediction dataframe contains duplicate CaseIDs.")

    # Align records by ID rather than relying on workbook row order.
    truth_by_case = ground_truth_dataframe.set_index("CaseID")
    predictions_by_case = prediction_dataframe.set_index("CaseID")

    common_case_ids = truth_by_case.index.intersection(
        predictions_by_case.index
    )

    if len(common_case_ids) == 0:
        raise ValueError("No matching CaseIDs found for the comparison.")

    for condition in conditions:
        prediction_column = f"{prediction_prefix}{condition}"

        if condition not in truth_by_case.columns:
            raise ValueError(f"Reference column is missing: {condition}")

        if prediction_column not in predictions_by_case.columns:
            raise ValueError(
                f"Prediction column is missing: {prediction_column}"
            )

        tp = fn = tn = fp = 0
        positive_ground_truth = 0
        negative_ground_truth = 0
        invalid_truth = 0
        invalid_prediction = 0

        for case_id in common_case_ids:
            truth = normalize_label(
                truth_by_case.at[case_id, condition]
            )
            prediction = normalize_label(
                predictions_by_case.at[case_id, prediction_column]
            )

            # Count reference labels independently of prediction validity.
            if truth == "Positive":
                positive_ground_truth += 1
            elif truth == "Negative":
                negative_ground_truth += 1
            else:
                invalid_truth += 1

            if prediction is None:
                invalid_prediction += 1

            # A confusion-matrix entry requires both labels to be valid.
            if truth is None or prediction is None:
                continue

            if truth == "Positive" and prediction == "Positive":
                tp += 1
            elif truth == "Positive" and prediction == "Negative":
                fn += 1
            elif truth == "Negative" and prediction == "Negative":
                tn += 1
            elif truth == "Negative" and prediction == "Positive":
                fp += 1

        # Sensitivity is undefined with no positive references; specificity
        # is undefined with no negative references.
        sensitivity_denominator = tp + fn
        specificity_denominator = tn + fp

        sensitivity = (
            tp / sensitivity_denominator
            if sensitivity_denominator
            else None
        )
        specificity = (
            tn / specificity_denominator
            if specificity_denominator
            else None
        )

        # Check = number of cases included in the confusion matrix.
        check = tp + fn + tn + fp

        # Ground Truth Check = valid positive + valid negative references.
        ground_truth_check = (
            positive_ground_truth + negative_ground_truth
        )

        worksheet.append([
            condition,
            tp,
            fn,
            tn,
            fp,
            sensitivity,
            specificity,
            check,
            positive_ground_truth,
            negative_ground_truth,
            ground_truth_check,
        ])

        row_number = worksheet.max_row

        for cell in worksheet[row_number]:
            cell.border = thin_border
            cell.alignment = Alignment(
                horizontal="left" if cell.column == 1 else "center",
                vertical="center",
            )

        for column_number in (6, 7):
            worksheet.cell(
                row=row_number,
                column=column_number,
            ).number_format = "0.00%"

        # Preserve diagnostic information without adding extra matrix columns.
        if invalid_truth or invalid_prediction:
            print(
                f"WARNING: {condition} | "
                f"invalid reference labels={invalid_truth}, "
                f"invalid prediction labels={invalid_prediction}, "
                f"matched cases={len(common_case_ids)}, "
                f"scored cases={check}"
            )

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    worksheet.row_dimensions[1].height = 34

    for column_cells in worksheet.columns:
        first_cell = column_cells[0]
        column_letter = get_column_letter(first_cell.column)
        max_width = max(
            len(str(cell.value or "")) for cell in column_cells
        )
        worksheet.column_dimensions[column_letter].width = min(
            max(max_width + 2, 12), 30
        )


def create_unique_output_path(
    project_folder, provider_name, model_name, case_count
):
    """Choose a timestamped output filename and refuse to overwrite a run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model_name = re.sub(r"[^A-Za-z0-9._-]", "_", model_name)
    base_name = (
        f"{OUTPUT_PREFIX}_{provider_name}_{safe_model_name}_"
        f"{case_count}cases_{timestamp}.xlsx"
    )
    output_path = project_folder / base_name

    if output_path.exists():
        raise FileExistsError(
            f"Output file already exists; refusing to overwrite: {output_path}"
        )

    return output_path


def calculate_file_sha256(file_path):
    """Hash the input workbook so a resume cannot silently use changed data."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_scored_checkpoint(scored_rows, output_path):
    """Atomically save labels and metadata without copying report text."""
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.stem}_",
            suffix=".xlsx",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        with pd.ExcelWriter(temporary_path, engine="openpyxl") as writer:
            scored_rows.to_excel(
                writer, sheet_name="Scored_Data_Rows", index=False
            )

        os.replace(temporary_path, output_path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Score Vetology canine thorax reports against the manual "
            "Gold Standard."
        )
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to the local manually reviewed Gold Standard workbook.",
    )
    parser.add_argument(
        "--cases",
        type=int,
        default=None,
        help=(
            "Number of lowest CaseIDs to score (default: 2 for a new run; "
            "a resumed run uses its saved cohort size)."
        ),
    )
    parser.add_argument(
        "--resume",
        type=str,
        help=(
            "Resume an interrupted run from its local checkpoint workbook. "
            "The input workbook, provider, model, and prompts must match."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini"),
        default="gemini",
        help="LLM provider to use (default: gemini).",
    )
    args = parser.parse_args()

    # Validate local inputs and credentials before reading or sending data.
    if args.cases is not None and args.cases < 1:
        parser.error("--cases must be at least 1.")

    if args.provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        model_name = OPENAI_MODEL_NAME
    else:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        model_name = GEMINI_MODEL_NAME

    if not api_key:
        if args.provider == "openai":
            key_message = "Set OPENAI_API_KEY in your local .env file."
        else:
            key_message = (
                "Set GEMINI_API_KEY or GOOGLE_API_KEY in your local .env file."
            )
        raise EnvironmentError(
            f"API key for {args.provider} was not found. {key_message}"
        )

    input_path = Path(args.file).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {input_path}")

    project_folder = Path(__file__).resolve().parent
    prompt_profile_path = project_folder / "prompts.json"
    if not prompt_profile_path.is_file():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_profile_path}"
        )

    prompt_templates = retrieve_isolated_prompt_configs(prompt_profile_path)
    if len(prompt_templates) != 20:
        raise ValueError(
            "Expected 20 condition prompts in prompts.json; "
            f"found {len(prompt_templates)}."
        )

    print(f"Loaded {len(prompt_templates)} condition prompts.")
    print(f"Reading Gold Standard workbook: {input_path}")

    gold_standard_dataframe = pd.read_excel(input_path, engine="openpyxl")
    required_columns = {
        "CaseID",
        *ORIGINAL_REPORT_COLUMNS,
        *EXISTING_AI_REPORT_COLUMNS,
    }
    missing_columns = required_columns - set(gold_standard_dataframe.columns)
    if missing_columns:
        raise ValueError(
            "Input workbook is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if gold_standard_dataframe["CaseID"].duplicated().any():
        raise ValueError(
            "Duplicate CaseID values were found in the input workbook."
        )

    if len(gold_standard_dataframe.columns) < GOLD_STANDARD_COLUMNS_END:
        raise ValueError(
            "Expected 20 Gold Standard condition columns at positions 8–27."
        )

    print("Excel columns with positions:")
    for i, name in enumerate(gold_standard_dataframe.columns, start=1):
        print(i, repr(name))

    # The input workbook schema defines the authoritative condition order;
    # the prompt output order and matrix columns follow this slice.
    conditions = gold_standard_dataframe.columns[
        GOLD_STANDARD_COLUMNS_START:GOLD_STANDARD_COLUMNS_END
    ].tolist()

    print("\nSelected condition columns:")
    for condition in conditions:
        print(repr(condition))

    if len(conditions) != 20:
        raise ValueError(
            f"Expected 20 conditions, but found {len(conditions)}."
        )

    system_prompt = compile_diagnostic_instruction_template(
        prompt_templates, conditions
    )
    if args.provider == "openai":
        client = OpenAI(api_key=api_key)
    else:
        try:
            from google import genai
        except ImportError as error:
            raise ImportError(
                "Gemini support requires the google-genai package. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from error
        client = genai.Client(api_key=api_key)

    prompt_sha256 = hashlib.sha256(
        system_prompt.encode("utf-8")
    ).hexdigest()
    source_sha256 = calculate_file_sha256(input_path)

    provider_label = "OpenAI" if args.provider == "openai" else "Gemini"
    radiologist_prefix = f"{provider_label}_Radiologist_"
    ai_report_prefix = f"{provider_label}_AI_"
    prediction_columns = [
        f"{prefix}{condition}"
        for prefix in (radiologist_prefix, ai_report_prefix)
        for condition in conditions
    ]
    metadata_values = {
        "LLM_Provider": args.provider,
        "LLM_Model": model_name,
        "LLM_Prompt_Version": PROMPT_VERSION,
        "LLM_Prompt_SHA256": prompt_sha256,
        "LLM_Temperature": 0.0,
        "LLM_Max_Output_Tokens": (
            GEMINI_MAX_OUTPUT_TOKENS
            if args.provider == "gemini"
            else 150
        ),
        "LLM_Thinking_Level": (
            GEMINI_THINKING_LEVEL if args.provider == "gemini" else "N/A"
        ),
        "LLM_Report_Sections": "Findings; Conclusions",
        "LLM_Source_SHA256": source_sha256,
    }

    if args.resume:
        output_path = Path(args.resume).expanduser().resolve()
        if output_path == input_path:
            raise ValueError("Checkpoint path must not be the input workbook.")
        if not output_path.is_file():
            raise FileNotFoundError(
                f"Checkpoint workbook not found: {output_path}"
            )

        checkpoint_workbook = openpyxl.load_workbook(
            output_path, read_only=True
        )
        try:
            if {
                "Matrix_1_Radiologist",
                "Matrix_2_Your_LLM",
            }.intersection(checkpoint_workbook.sheetnames):
                raise ValueError(
                    "This workbook is already finalized and cannot be resumed."
                )
            if "Scored_Data_Rows" not in checkpoint_workbook.sheetnames:
                raise ValueError(
                    "Checkpoint is missing the Scored_Data_Rows sheet."
                )
        finally:
            checkpoint_workbook.close()

        scored_rows = pd.read_excel(
            output_path,
            sheet_name="Scored_Data_Rows",
            engine="openpyxl",
            keep_default_na=False,
        )
        checkpoint_columns = {
            "CaseID",
            *conditions,
            *prediction_columns,
            *metadata_values,
            "LLM_Resolved_Model",
            "LLM_Cases_Requested",
            "LLM_Run_Timestamp_UTC",
            "Scoring_Status",
        }
        missing_checkpoint_columns = checkpoint_columns - set(
            scored_rows.columns
        )
        if missing_checkpoint_columns:
            raise ValueError(
                "Checkpoint is missing required columns: "
                + ", ".join(sorted(missing_checkpoint_columns))
            )

        saved_case_count = int(scored_rows["LLM_Cases_Requested"].iloc[0])
        if args.cases is not None and args.cases != saved_case_count:
            raise ValueError(
                "The --cases value must match the checkpoint cohort size "
                f"({saved_case_count})."
            )
        args.cases = saved_case_count

        for column, expected_value in metadata_values.items():
            if scored_rows[column].isna().any():
                raise ValueError(
                    f"Checkpoint metadata is incomplete: {column}."
                )
            if not scored_rows[column].eq(expected_value).all():
                raise ValueError(
                    f"Checkpoint {column} does not match this run."
                )

        if scored_rows["CaseID"].duplicated().any():
            raise ValueError("Checkpoint contains duplicate CaseIDs.")
        if not scored_rows["Scoring_Status"].isin(
            {"pending", "complete"}
        ).all():
            raise ValueError("Checkpoint contains an invalid scoring status.")

        checkpoint_case_ids = scored_rows["CaseID"].tolist()
        selected_cases = (
            gold_standard_dataframe[
                gold_standard_dataframe["CaseID"].isin(checkpoint_case_ids)
            ]
            .sort_values("CaseID")
            .copy()
        )
        if selected_cases["CaseID"].tolist() != checkpoint_case_ids:
            raise ValueError(
                "Checkpoint CaseIDs do not match the selected source workbook."
            )

        for _, row in scored_rows[
            scored_rows["Scoring_Status"] == "complete"
        ].iterrows():
            if any(
                normalize_label(row[column]) is None
                for column in prediction_columns
            ):
                raise ValueError(
                    "A completed checkpoint case has invalid predictions."
                )

        resolved_model_names = {
            name
            for value in scored_rows["LLM_Resolved_Model"].dropna()
            for name in str(value).split("; ")
            if name
        }
        print(f"Resuming checkpoint: {output_path.name}")
    else:
        args.cases = args.cases or TEST_CASE_LIMIT
        selected_cases = (
            gold_standard_dataframe.sort_values("CaseID")
            .head(args.cases)
            .copy()
        )
        if len(selected_cases) != args.cases:
            raise ValueError(
                f"Requested {args.cases} cases, but only "
                f"{len(selected_cases)} are available."
            )
        if selected_cases.empty:
            raise ValueError("No cases were found in the input workbook.")

        # Checkpoints contain IDs, Gold Standard labels, predictions, and run
        # metadata only; report content is never written to disk.
        scored_rows = selected_cases[["CaseID", *conditions]].copy()
        for column in prediction_columns:
            scored_rows[column] = None
        scored_rows["Scoring_Status"] = "pending"
        for column, value in metadata_values.items():
            scored_rows[column] = value
        scored_rows["LLM_Resolved_Model"] = ""
        scored_rows["LLM_Cases_Requested"] = args.cases
        scored_rows["LLM_Run_Timestamp_UTC"] = datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds")
        resolved_model_names = set()
        output_path = create_unique_output_path(
            project_folder,
            provider_label,
            model_name,
            args.cases,
        )
        save_scored_checkpoint(scored_rows, output_path)
        print(f"Created local checkpoint: {output_path.name}")

    completed_count = int(
        (scored_rows["Scoring_Status"] == "complete").sum()
    )
    print(
        f"Scoring {len(selected_cases)} cases; "
        f"{completed_count} already complete."
    )

    # Store each completed case immediately. If quota or network errors stop
    # the run, resume from this workbook rather than repeating successful API
    # calls.
    for _, case in selected_cases.iterrows():
        case_id = case["CaseID"]
        row_index = scored_rows.index[
            scored_rows["CaseID"] == case_id
        ][0]
        if scored_rows.at[row_index, "Scoring_Status"] == "complete":
            continue

        try:
            print(
                f"Scoring original radiologist report for CaseID {case_id}..."
            )
            (
                original_labels,
                original_model_name,
            ) = execute_clinical_evaluation_loop(
                client,
                args.provider,
                model_name,
                system_prompt,
                combine_report_sections(case, ORIGINAL_REPORT_COLUMNS),
                expected_label_count=len(conditions),
            )
            original_labels = enforce_generalized_cardiomegaly_consistency(
                original_labels, conditions
            )

            print(f"Scoring existing AI report for CaseID {case_id}...")
            ai_labels, ai_model_name = execute_clinical_evaluation_loop(
                client,
                args.provider,
                model_name,
                system_prompt,
                combine_report_sections(case, EXISTING_AI_REPORT_COLUMNS),
                expected_label_count=len(conditions),
            )
            ai_labels = enforce_generalized_cardiomegaly_consistency(
                ai_labels, conditions
            )
        except Exception as error:
            save_scored_checkpoint(scored_rows, output_path)
            raise RuntimeError(
                "Scoring stopped. Completed cases are saved in the local "
                f"checkpoint: {output_path}. Resume with --resume "
                f"\"{output_path}\"."
            ) from error

        for condition, label in zip(conditions, original_labels):
            scored_rows.at[
                row_index, f"{radiologist_prefix}{condition}"
            ] = label
        for condition, label in zip(conditions, ai_labels):
            scored_rows.at[
                row_index, f"{ai_report_prefix}{condition}"
            ] = label

        resolved_model_names.update(
            {original_model_name, ai_model_name}
        )
        resolved_models_text = "; ".join(sorted(resolved_model_names))
        scored_rows["LLM_Resolved_Model"] = resolved_models_text
        scored_rows.at[row_index, "Scoring_Status"] = "complete"
        save_scored_checkpoint(scored_rows, output_path)
        completed_count += 1
        print(
            f"Checkpoint saved ({completed_count}/{len(selected_cases)} "
            f"cases complete)."
        )
        time.sleep(0.4)

    resolved_models_text = "; ".join(sorted(resolved_model_names))
    scored_rows["LLM_Resolved_Model"] = resolved_models_text
    save_scored_checkpoint(scored_rows, output_path)
    print(f"All case labels are complete. Finalizing: {output_path.name}")

    workbook = openpyxl.load_workbook(output_path)

    # Reuse the radiologist predictions as Matrix 1's reference labels.
    radiologist_reference = scored_rows[
        ["CaseID"]
        + [
            f"{radiologist_prefix}{condition}"
            for condition in conditions
        ]
    ].copy()
    radiologist_reference = radiologist_reference.rename(
        columns={
            f"{radiologist_prefix}{condition}": condition
            for condition in conditions
        }
    )

    # MATRIX 1: Reference = LLM labels from the radiologist report;
    # prediction = LLM labels from the existing AI report.
    matrix1 = workbook.create_sheet("Matrix_1_Radiologist")
    compute_metrics_and_render_tab(
        matrix1,
        radiologist_reference,
        scored_rows,
        conditions,
        prediction_prefix=ai_report_prefix,
        reference_is_gold_standard=False,
    )

    # MATRIX 2: Reference = Gold Standard; prediction = LLM labels from the
    # original radiologist report.
    matrix2 = workbook.create_sheet("Matrix_2_Your_LLM")
    compute_metrics_and_render_tab(
        matrix2,
        selected_cases,
        scored_rows,
        conditions,
        prediction_prefix=radiologist_prefix,
        reference_is_gold_standard=True,
    )

    workbook.save(output_path)
    workbook.close()

    print("\nTest completed successfully.")
    print(f"Workbook: {output_path}")
    print(f"Cases scored: {len(selected_cases)}")
    print(
        "Matrix 1 compares AI-scored LLM labels from the radiologist report "
        "against AI-scored LLM labels from the AI report."
    )
    print(
        "Matrix 2 compares this model's radiologist-report labels "
        "against the Gold Standard."
    )


if __name__ == "__main__":
    main()
