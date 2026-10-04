# livermore
## Japanese tutor agent

```
pip install -r jp_tutor/requirements.txt   # voice/LLM deps are optional
export OPENAI_API_KEY=...                  # optional: LLM-generated questions & grading
python -m jp_tutor.tutor
```
Pick a JLPT level (N5–N1) and session focus; get alternating verbal/written questions,
speak answers (mic, Google ja-JP recognition) or type them, receive corrections read back
aloud, and all results are stored in SQLite (`~/.jp_tutor.db`). Type `h` to review mistakes.
Without an API key a small built-in question bank and similarity-based grading are used.
