# Phase 2 Evaluation Guide

## Goal

This guide explains how to run the first labeled evaluation pass for the LLM-VulnHub multi-agent workflow.

Current scope:

- triage classification quality
- extraction exact-match quality on key fields
- extraction completeness

---

## Dataset

Labeled dataset file:

- `backend/app/evals/agent_eval_dataset.json`

Current sample mix:

- 6 positive AI-vulnerability samples
- 4 negative non-vulnerability / non-security samples
- merge expectations for positive samples

---

## Run

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.evals.run_agent_eval --verbose
```

Save a machine-readable report:

```powershell
.\.venv\Scripts\python.exe -m app.evals.run_agent_eval --output artifacts/evals/mock.json
```

---

## Metrics

The script currently reports:

- `triage_accuracy`
- `triage_precision`
- `triage_recall`
- `extraction_field_exact_match`
  - `vuln_type`
  - `severity`
  - `affected_component`
- `extraction_completeness`
- `merge_precision`

---

## How To Compare Models

Use the same dataset and switch environment variables before running:

- `LLM_PROVIDER=mock`
- `LLM_PROVIDER=deepseek`
- `LLM_PROVIDER=openai`

Recommended comparison method:

1. keep dataset fixed
2. run once per provider
3. save the JSON summary with `--output`
4. compare triage and extraction metrics side by side

---

## Current Limits

- merge precision is not yet labeled in the dataset
- extraction is evaluated only on core fields, not long-form text quality
- no historical evaluation result storage yet

These are the next natural extensions.
