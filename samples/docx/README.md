# DOCX Samples

This directory stores reusable, openable DOCX fixtures for manual checks and
scenario experiments. The file set mirrors
`src/config/scene_sample_fixture_registry.py`: each fixture is stored as
`<fixture_id>.docx`.

Current boundary:

- Keep source-like sample fixtures here.
- Keep generated outputs under `artifacts/`, `tests/output/`, or a local
  temporary directory.
- Do not place ad hoc customer documents or release outputs in this directory.

Validation:

```powershell
python scripts\verify_scene_sample_fixtures.py
python -c "from pathlib import Path; from zipfile import is_zipfile; files=sorted(Path('samples/docx').glob('*.docx')); bad=[str(p) for p in files if not is_zipfile(p)]; print(len(files), bad)"
python -c "from pathlib import Path; import sys; sys.path.insert(0,str(Path('.').resolve())); from src.config.scene_sample_fixture_registry import list_scene_sample_fixtures; registry=sorted(f'{f.fixture_id}.docx' for f in list_scene_sample_fixtures()); disk=sorted(p.name for p in Path('samples/docx').glob('*.docx')); print(sorted(set(registry)-set(disk))); print(sorted(set(disk)-set(registry)))"
```
