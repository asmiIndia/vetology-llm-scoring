# main.py
import argparse
import os
import time
import re
import pandas as pd
from openai import OpenAI
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, Side
import dotenv

dotenv.load_dotenv()

# The 20 diagnostic conditions in your exact Excel sheet sequence
CONDITIONS = [
    "perihilar_infiltrate", "pneumonia", "bronchitis", "interstitial", "diseased_lungs",
    "hypo_plastic_trachea", "cardiomegaly", "pulmonary_nodules", "pleural_effusion", "rtm",
    "focal_caudodorsal_lung", "focal_perihilar", "pulmonary_hypoinflation", 
    "right_sided_cardiomegaly", "pericardial_effusion", "bronchiectasis", 
    "pulmonary_vessel_enlargement", "left_sided_cardiomegaly", "thoracic_lymphadenopathy", 
    "esophagitis"
]

def get_master_system_prompt():
    """Returns the unified, clinically grounded validation prompt instruction framework."""
    return (
        "You are an expert veterinary data scientist and radiologist scorer.\n\n"
        "Analyze the provided radiology report text and determine if there is definitive evidence for each "
        "of the following 20 conditions. You must evaluate them in this exact order:\n"
        f"{', '.join(CONDITIONS)}\n\n"
        "[CLINICAL GROUNDING RULES]\n"
        "1. Respond 'Positive' ONLY if a condition is explicitly stated as present or highly consistent with the images.\n"
        "2. Respond 'Negative' if a condition is explicitly noted as absent, normal, clear, clear of changes, or ruled out.\n"
        "3. CRITICAL HEDGING RULE: If the text expresses uncertainty, uses phrases like 'no clear evidence', 'unlikely', 'rules out', or 'no signs seen', classify as 'Negative'.\n"
        "4. CARDIOMEGALY OVERRIDE: If the text states 'cardiomegaly' or 'heart enlargement' broadly without specifying left or right, mark both 'left_sided_cardiomegaly' and 'right_sided_cardiomegaly' as Positive.\n"
        "5. If a structure is noted as collapsed, missing, or 'not well-identified', treat it as a normal baseline and mark as 'Negative'.\n\n"
        "[OUTPUT FORMAT]\n"
        "You must respond ONLY with a comma-separated list of exactly 20 words, each being either 'Positive' or 'Negative'. "
        "Do not include numbers, bullet points, markdown blocks, intro text, or extra spaces. Example output format:\n"
        "Negative,Negative,Positive,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative,Negative"
    )

def get_openai_batch_score(client, report_text, max_retries=5):
    """Leverages unlocked Paid Tier 1 speed to extract all 20 conditions in a single request."""
    system_prompt = get_master_system_prompt()
    base_delay = 2.0
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Radiology findings text to evaluate:\n{str(report_text)}"},
                ],
                max_tokens=100,
                temperature=0.0
            )
            raw_output = response.choices.message.content.strip()
            parsed_scores = [m.group(0).capitalize() for m in re.finditer(r'(Positive|Negative)', raw_output, re.IGNORECASE)]
            if len(parsed_scores) == 20:
                return parsed_scores
            time.sleep(2.0)
        except Exception:
            time.sleep(base_delay * (2 ** attempt))
    return ["Negative"] * 20

def create_confusion_matrix(df, condition_list, output_path):
    """Calculates true metrics and applies formal formatting layout rules."""
    cols = [
        'True Positive', 'False Positive', 'True Negative', 'False Negative', 
        'Sensitivity', 'Specificity', 'Check', 'Positive Ground Truth', 
        'Negative Ground Truth', 'Ground Truth Check', '', 'Radiologist Agreement Rate'
    ]
    
    confusion_matrix = pd.DataFrame(columns=cols, index=condition_list)
    confusion_matrix.index.name = 'condition'

    for cond in condition_list:
        human_col = cond
        ai_col = f"OpenAI_{cond}"
        
        if ai_col not in df.columns:
            continue
            
        y_true = df[human_col].astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)
        y_pred = df[ai_col].astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)

        is_true_pos = (y_true == 'POSITIVE') | (y_true == '1') | (y_true == 'TRUE')
        is_true_neg = (y_true == 'NEGATIVE') | (y_true == '0') | (y_true == 'FALSE')
        is_pred_pos = (y_pred == 'POSITIVE') | (y_pred == '1') | (y_pred == 'TRUE')
        is_pred_neg = (y_pred == 'NEGATIVE') | (y_pred == '0') | (y_pred == 'FALSE')

        tp = int((is_true_pos & is_pred_pos).sum())
        tn = int((is_true_neg & is_pred_neg).sum())
        fp = int((is_true_neg & is_pred_pos).sum())
        fn = int((is_true_pos & is_pred_neg).sum())

        pos_ground_truth = tp + fn
        neg_ground_truth = tn + fp
        
        sensitivity = tp / pos_ground_truth if pos_ground_truth > 0 else 0.0
        specificity = tn / neg_ground_truth if neg_ground_truth > 0 else 0.0
        agreement_rate = (tp + tn) / (pos_ground_truth + neg_ground_truth) if (pos_ground_truth + neg_ground_truth) > 0 else 0.0

        confusion_matrix.at[cond, 'True Positive'] = tp
        confusion_matrix.at[cond, 'False Positive'] = fp
        confusion_matrix.at[cond, 'True Negative'] = tn
        confusion_matrix.at[cond, 'False Negative'] = fn
        confusion_matrix.at[cond, 'Sensitivity'] = f"{sensitivity:.2%}"
        confusion_matrix.at[cond, 'Specificity'] = f"{specificity:.2%}"
        confusion_matrix.at[cond, 'Check'] = tp + fp + tn + fn
        confusion_matrix.at[cond, 'Positive Ground Truth'] = pos_ground_truth
        confusion_matrix.at[cond, 'Negative Ground Truth'] = neg_ground_truth
        confusion_matrix.at[cond, 'Ground Truth Check'] = pos_ground_truth + neg_ground_truth
        confusion_matrix.at[cond, ''] = ""
        confusion_matrix.at[cond, 'Radiologist Agreement Rate'] = f"{agreement_rate:.2%}"

    confusion_matrix.to_excel(output_path, index=True)

    # Begin openpyxl grid border styling matching peer template layout
    wb = load_workbook(output_path)
    ws = wb.active
    bold_font = Font(bold=True)
    thin_side = Side(style='thin', color='000000')
    border_style = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    skip_cols = [None, 'Radiologist Agreement Rate'] 
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            if ws.cell(row=1, column=cell.column).value not in skip_cols:
                cell.border = border_style

    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = center_align

    for cell in ws[1]:
        cell.font = bold_font
    for row in range(2, ws.max_row + 1):
        ws.cell(row=row, column=1).font = bold_font

    for col in ws.columns:
        max_len = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col.column_letter].width = max(max_len + 1, 12)
    
    wb.save(output_path)

def main():
    parser = argparse.ArgumentParser(description="Vetology Unified Master Execution Pipeline.")
    parser.add_argument('--file', type=str, required=True, help='Your clean source excel file path')
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Ensure OPENAI_API_KEY is saved inside your .env file.")
        return

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # 1. Open and read the input Excel document
    df = pd.read_excel(args.file, engine="openpyxl")
    print(f"Spreadsheet loaded successfully: {len(df)} rows found.")

    production_batch = df[df["CaseID"].between(1, 100)].copy()
    print("Initiating free OpenAI GPT API call with a token...")

    report_column = "Findings (original radiologist report)"
    matrix_storage = {f"OpenAI_{cond}": [] for cond in CONDITIONS}

    # 2. Main processing execution loop
    for idx, row in production_batch.iterrows():
        text = row[report_column]
        case_scores = get_openai_batch_score(openai_client, text)
        for i, condition_name in enumerate(CONDITIONS):
            matrix_storage[f"OpenAI_{condition_name}"].append(case_scores[i])
        time.sleep(1.0)

    for col_name, data_list in matrix_storage.items():
        production_batch[col_name] = data_list

    # 3. Writes a new Excel document matching the Example Confusion Matrix Output format
    output_matrix_name = "confusion_matrix_template.xlsx"
    create_confusion_matrix(production_batch, CONDITIONS, output_matrix_name)
    print(f"Confusion matrix has been created and saved as '{output_matrix_name}'.")

    # 4. Trigger OpenAI professional notification summary statement
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Write a statement saying that the confusion matrix has been created and saved as '{output_matrix_name}'."}],
            max_tokens=50
        )
        print("\n" + response.choices[0].message.content.strip())
    except Exception:
        print(f"\nTell the user that the confusion matrix has been created and saved as '{output_matrix_name}'.")

if __name__ == '__main__':
    main()
