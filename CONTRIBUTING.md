# Contributing

Contributions are welcome when they improve physiological validity, auditability, file compatibility, or reporting clarity.

## Privacy first

Do not commit or attach real athlete exports, names, account identifiers, activity IDs, exact timestamps, coordinates, or identifiable health data. Build the smallest synthetic fixture that reproduces a problem. Redacting a filename alone is not sufficient.

## Development setup

```bash
git clone https://github.com/victory-c/analyze-cycling-hr-thresholds.git
cd analyze-cycling-hr-thresholds
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r scripts/requirements.txt
```

Run the test suite:

```bash
python -m unittest discover -s scripts/tests -v
```

If the OpenAI skill-creator utilities are installed locally, also validate the skill package:

```bash
python /path/to/skill-creator/scripts/quick_validate.py .
```

## Pull requests

- Keep `SKILL.md` concise and agent-facing; place detailed methods under `references/`.
- Add or update tests for deterministic script behavior.
- Treat automatic breakpoints and FTP outputs as candidates, not diagnoses.
- Cite primary research for new physiological or biomechanical claims.
- State assumptions, units, rounding, and validity gates explicitly.
- Preserve backward-compatible JSON fields when practical.
- Complete the privacy and validation checklist in the PR template.

## Bug reports

Use the GitHub issue form, but do not upload raw FIT, GPX, TCX, XLSX, HTML, PDF, or JSON health exports. Describe the schema and error, then provide synthetic rows if needed.
