import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from modules.file_memory import record_file_event


def _resolve_path(raw_path: str, cwd: str | None) -> Path:
    raw_path = raw_path.strip()
    if raw_path.startswith(("~", "/")):
        return Path(os.path.expanduser(raw_path)).resolve()
    base = Path(cwd or os.getcwd())
    return (base / raw_path).resolve()


def _read_lines(path: Path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines(keepends=True)


def _write_lines(path: Path, lines):
    try:
        if path.exists() and path.stat().st_size > 0:
            base_dir = Path(__file__).resolve().parent.parent
            backup_dir = base_dir / "logs" / "file_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{path.name}.{stamp}.bak"
            shutil.copy2(path, backup_path)
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def _ensure_insert_text(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def _insert_at(lines, idx, text):
    ins = _ensure_insert_text(text)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] = lines[-1] + "\n"
    lines.insert(idx, ins)
    return lines


def _hash_line(line: str) -> str:
    if not line:
        return "#\n"
    prefix = re.match(r"^\s*", line).group(0)
    rest = line[len(prefix):]
    if rest.startswith("#"):
        return line
    return prefix + "#" + rest


def _parse_text_after_path(raw: str) -> tuple[str, str] | None:
    raw = raw.strip()
    m = re.match(r"^(\S+)\s+(.+)$", raw)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def handle_file_command(cmd: str, cwd: str | None = None):
    raw = cmd.strip()

    m = re.match(r"^dodaj na koncu\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        payload = _parse_text_after_path(m.group(1))
        if not payload:
            return "Uzycie: dodaj na koncu <plik> \"<tekst>\""
        path_raw, text = payload
        path = _resolve_path(path_raw, cwd)
        lines = _read_lines(path)
        lines.append(_ensure_insert_text(_strip_quotes(text)))
        _write_lines(path, lines)
        record_file_event("append_end", str(path), f"bytes:{len(text)}")
        return f"Dodano na koncu: {path}"

    m = re.match(r"^dodaj na poczatku\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        payload = _parse_text_after_path(m.group(1))
        if not payload:
            return "Uzycie: dodaj na poczatku <plik> \"<tekst>\""
        path_raw, text = payload
        path = _resolve_path(path_raw, cwd)
        lines = _read_lines(path)
        lines = _insert_at(lines, 0, _strip_quotes(text))
        _write_lines(path, lines)
        record_file_event("prepend", str(path), f"bytes:{len(text)}")
        return f"Dodano na poczatku: {path}"

    m = re.match(r"^dodaj w srodku\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        payload = _parse_text_after_path(m.group(1))
        if not payload:
            return "Uzycie: dodaj w srodku <plik> \"<tekst>\""
        path_raw, text = payload
        path = _resolve_path(path_raw, cwd)
        lines = _read_lines(path)
        idx = len(lines) // 2
        lines = _insert_at(lines, idx, _strip_quotes(text))
        _write_lines(path, lines)
        record_file_event("insert_middle", str(path), f"bytes:{len(text)}")
        return f"Dodano w srodku: {path}"

    m = re.match(r"^dodaj w linii numer\s+(\d+)\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        line_no = int(m.group(1))
        payload = _parse_text_after_path(m.group(2))
        if not payload:
            return "Uzycie: dodaj w linii numer <N> <plik> \"<tekst>\""
        path_raw, text = payload
        path = _resolve_path(path_raw, cwd)
        lines = _read_lines(path)
        idx = max(0, min(line_no - 1, len(lines)))
        lines = _insert_at(lines, idx, _strip_quotes(text))
        _write_lines(path, lines)
        record_file_event("insert_line", str(path), f"line:{line_no}")
        return f"Dodano w linii {line_no}: {path}"

    m = re.match(r"^zahaszuj linie nr\s+(\d+)\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        line_no = int(m.group(1))
        path = _resolve_path(m.group(2), cwd)
        lines = _read_lines(path)
        if line_no < 1 or line_no > len(lines):
            return "Poza zakresem linii."
        lines[line_no - 1] = _hash_line(lines[line_no - 1])
        _write_lines(path, lines)
        record_file_event("hash_line", str(path), f"line:{line_no}")
        return f"Zahaszowano linie {line_no}: {path}"

    m = re.match(r"^zahaszuj linie od\s+(\d+)\s+do\s+(\d+)\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        path = _resolve_path(m.group(3), cwd)
        if start > end:
            start, end = end, start
        lines = _read_lines(path)
        start = max(1, start)
        end = min(len(lines), end)
        if not lines or start > end:
            return "Poza zakresem linii."
        for i in range(start - 1, end):
            lines[i] = _hash_line(lines[i])
        _write_lines(path, lines)
        record_file_event("hash_range", str(path), f"{start}-{end}")
        return f"Zahaszowano linie {start}-{end}: {path}"

    m = re.match(r"^zacznij plik\s+\"?([a-zA-Z]+)\"?\s+(.+)$", raw, flags=re.IGNORECASE)
    if m:
        kind = m.group(1).lower()
        path = _resolve_path(m.group(2), cwd)
        if path.exists() and path.stat().st_size > 0:
            return f"Plik juz istnieje i nie jest pusty: {path}"
        header = ""
        if kind == "bash":
            header = "#!/usr/bin/env bash\n\n"
        elif kind == "python":
            header = "#!/usr/bin/env python3\n\n"
        elif kind in ("tekstowy", "text", "txt"):
            header = ""
        else:
            return "Nieznany typ. Uzyj: bash, python, tekstowy"
        _write_lines(path, [header] if header else [])
        record_file_event("start_file", str(path), f"type:{kind}")
        return f"Utworzono plik: {path}"

    return None


def tool_FILE_EDIT(arg: str, system_run=None, log_fn=None):
    msg = handle_file_command(arg, os.getcwd())
    return msg or "Nie rozpoznano komendy plikowej."
