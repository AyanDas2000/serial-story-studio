"""Build the zip that people try the desk from.

    python scripts/make_trial_zip.py          dist/serial-story-studio-trial.zip  (practice mode only)
    python scripts/make_trial_zip.py --beta   dist/serial-story-studio-beta.zip   (practice mode, plus a live launcher
                                              that reads the tester's own key from a file they create)

Neither zip holds a database, a key, a spend log or a local work file. The beta zip holds `.env.example`, which has
an empty key line, and never `.env`.
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {'__pycache__'}
SKIP_SUFFIXES = {'.pyc', '.db', '.db-wal', '.db-shm', '.jsonl'}
SKIP_PREFIXES = ('logic-',)

TRIAL_EXTRAS = {
    ROOT / 'try_it.py': 'try_it.py',
    ROOT / 'try-it.bat': 'try-it.bat',
    ROOT / 'try-it.sh': 'try-it.sh',
    ROOT / 'README.md': 'README.md',
}
BETA_EXTRAS = {
    ROOT / 'try_it.py': 'try_it.py',
    ROOT / 'try-it.bat': 'try-it.bat',
    ROOT / 'try-it.sh': 'try-it.sh',
    ROOT / 'run_shelf_live.py': 'run_shelf_live.py',
    ROOT / 'live-it.bat': 'live-it.bat',
    ROOT / 'live-it.sh': 'live-it.sh',
    ROOT / '.env.example': '.env.example',
    ROOT / 'README.md': 'README.md',
}


def keep(path: Path) -> bool:
    if SKIP_PARTS & set(path.parts) or path.suffix in SKIP_SUFFIXES:
        return False
    return not path.name.startswith(SKIP_PREFIXES)


def trial_text(path: Path) -> bytes | None:
    """The logic-review pages are not shipped, so their links are removed from the shipped copy of the desk."""
    if path.name == 'v1.html':
        text = re.sub(r'\s*<details class="support">.*?</details>', '', path.read_text(encoding='utf-8'), flags=re.S)
    elif path.name == 'v1.js':
        text = re.sub(r"\n\s*add\('Review the writing logic'.*?\n", '\n', path.read_text(encoding='utf-8'))
    else:
        return None
    return text.encode('utf-8')


def build(out: Path, extras: dict[Path, str]) -> int:
    out.parent.mkdir(exist_ok=True)
    files = [p for p in sorted((ROOT / 'serial_story').rglob('*')) if p.is_file() and keep(p.relative_to(ROOT))]
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files:
            name = 'serial-story-studio/' + p.relative_to(ROOT).as_posix()
            changed = trial_text(p)
            z.writestr(name, changed) if changed is not None else z.write(p, name)
        for src, name in extras.items():
            z.write(src, 'serial-story-studio/' + name)
    print(f'{out} ({out.stat().st_size // 1024} KB, {len(files) + len(extras)} files)')
    return 0


def main() -> int:
    if '--beta' in sys.argv[1:]:
        return build(ROOT / 'dist' / 'serial-story-studio-beta.zip', BETA_EXTRAS)
    return build(ROOT / 'dist' / 'serial-story-studio-trial.zip', TRIAL_EXTRAS)


if __name__ == '__main__':
    sys.exit(main())
