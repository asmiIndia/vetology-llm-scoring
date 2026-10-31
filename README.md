# Vetology LLM Scoring

The current application scores canine thorax radiology reports against 20
conditions. It reads a local manually reviewed workbook and creates scored
labels, run metadata, and two comparison matrices:

- **Matrix 1:** Model labels from the radiologist report versus labels from
  the existing AI report.
- **Matrix 2:** Model labels from the radiologist report versus the Gold
  Standard.

## Local Ollama runner

[`main.py`](./main.py) runs the scoring workflow with Ollama's local API.
It defaults to the locally installed `qwen3:4b` model at
`http://localhost:11434`; keep Ollama running during scoring. No hosted-model
API key is required. Model files, checkpoints, and generated workbooks should
remain local.

Start with a small validation run and review the results before scoring a
larger cohort:

```powershell
python .\main.py --file ".\1_canine_thorax_gold.xlsx" --cases 2
python .\main.py --file ".\1_canine_thorax_gold.xlsx" --cases 100
```

The model and endpoint can optionally be overridden with `OLLAMA_MODEL` and
`OLLAMA_BASE_URL` in the process environment or a local `.env` file. Neither
setting needs to be added to `.env` when using the defaults.

Long runs save a local checkpoint after each completed case. If a run stops,
resume using the checkpoint path printed in the error message, with the same
input, model, and endpoint:

```powershell
python .\main.py --file ".\1_canine_thorax_gold.xlsx" --resume "<checkpoint path>"
```

The checkpoint contains case IDs, Gold Standard labels, model labels, status,
and run metadata, but not report text. Generated workbooks also omit report
text. Keep both local and do not publish them.

## Hosted-model runner

[`main_new.py`](./main_new.py) is a separate version that supports hosted
Gemini and OpenAI models. It requires the selected provider's API credentials
and is subject to that provider's terms, quotas, and pricing. It was not used
for the completed 100-case local Ollama run.

## Prompt and project documentation

- [`prompts.json`](./prompts.json) contains the runtime condition prompts.
- [`prompts.md`](./prompts.md) describes the prompt rules and evaluation.
- [`prompt_changelog.md`](./prompt_changelog.md) records prompt changes.



