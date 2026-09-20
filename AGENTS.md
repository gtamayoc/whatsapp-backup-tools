# AGENTS.md

## Repo layout

Two CLI tools plus shared code, all top-level packages (importable from repo root):

- `wab_archiver/` — archives WhatsApp media into a structured folder tree. Console script `wab-archiver`.
- `wab_viewer/` — Flask web UI for browsing an archive. Console script `wab-viewer`.
- `shared/` — cross-cutting helpers. `db`/`hashing` are imported as `from shared import db, hashing`; `source_detection` is imported as `from shared.source_detection import WA_DATABASES_DIR_NAME`.
- `tests/` — two large files: `test_wa_media_archiver.py` (archiver) and `test_wa_chat_viewer.py` (viewer).

The PyPI package name is `wabtools` (`pyproject.toml`), which does **not** match the package dirs. `_get_version()` in both tools reads `wabtools` from importlib.metadata, falling back to `pyproject.toml`. Bump `version` in `pyproject.toml` when releasing.

## Commands

```bash
pip install -e .            # registers wab-archiver / wab-viewer entry points
python -m wab_archiver ...  # run without install (must be from repo root so `shared` imports)
python -m wab_viewer <output_root> ...   # output_root is a positional arg, not a flag
```

- `archive` is the **default** archiver subcommand and can be omitted (`wab-archiver --wa-root ... -o ...`). Other subcommands: `restore`, `config generate`.
- `wab-archiver config generate` writes `example-config.toml` and exits.
- Tests require Flask (viewer imports it). Install dev deps: `pip install pytest pytest-cov flask`.

## Testing

```bash
pytest                                   # runs everything (testpaths=tests in pytest.ini)
pytest tests/test_wa_media_archiver.py   # archiver only
pytest tests/test_wa_media_archiver.py::TestSanitizeFilename::test_empty_string   # single test
```

- `pytest.ini` sets `addopts = -p no:pytest_homeassistant_custom_component` — the plugin is disabled by design; don't "fix" this.
- No external services, fixtures, or real WhatsApp data needed. Tests build synthetic SQLite DBs and `tmp_path` dirs.
- CI (`tests.yml`) runs `pytest tests/ -v --cov=wab_archiver --cov=wab_viewer --cov=shared --cov-report=term-missing` on ubuntu/macos/windows with **Python 3.12**.

## Architecture notes

- `wab_archiver/main.py` and `wab_viewer/main.py` are each 2000+ lines and hold all orchestration. Per-platform logic is split out: `android_handler.py`, `ios_handler.py`, `adb_extractor.py`, `backup_reader.py` (iOS backup extraction), `archive_db.py` (persistent state schema).
- Platform is detected at runtime by table name: iOS DBs have `ZWAMESSAGE`, Android DBs have `message` (`detect_db_platform` in `wab_archiver/main.py`). Every DB-query code path is duplicated per platform — mirror changes across both.
- `.wa_media_archiver.db` (created in the archive output dir) stores all persistent state: contact/group folder indexes and the file→archive-path map. Deleting it resets rename-tracking and duplicate/restore data.
- `.wa_viewer.db` (output dir) is the viewer's FTS/cache index; `wab-viewer --rescan` forces a rebuild. Source changes are detected via mtime+size stamps in `sync_meta`.

## Conventions & gotchas

- Python **3.11+** required (code uses `tomllib` and `X | None` unions). CI tests against 3.12.
- Optional deps are in `[project.optional-dependencies] archiver`: `wa-crypt-tools` (Android `.crypt15` decrypt), `iphone-backup-decrypt` (encrypted iOS backups). `tzdata` is needed for `--timezone` on Windows. These are checked lazily at runtime (`check_dependencies`), not imported at module top.
- Backslashes in `config.toml` paths are auto-converted to forward slashes and the file rewritten (`_load_toml`). Don't surprise users by breaking this.
- Year folders use the machine's **local time**, not UTC — intentional (`get_year`/README "Known Limitations"). Don't "fix" this to UTC.
- Config file supports `wa_root` as string **or** list; internally normalized to `wa_roots`. `--limit` and `--dry-run` are intentionally excluded from config keys.
- Frontend assets live in `wab_viewer/chat_viewer/` (`template.py` holds the single-page HTML via `HTML_TEMPLATE`, plus `app.js`/`app.css`). No JS build step.
