import curses
import os
import subprocess
import textwrap
import time
import shutil
import re
import json
from datetime import datetime
import shlex
from pathlib import Path

from modules.model_router import query_model
from modules.file_edit_tools import handle_file_command
from modules.memory_commands import handle_memory_command, build_memory_context
from modules.model_switcher import get_active_local_model_name

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
def _get_cloud_consent():
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return (data.get("cloud_consent") or "ask").lower()
    except Exception:
        pass
    return "ask"


def _wrap_lines(text, width):
    lines = []
    for raw in text.splitlines() if text is not None else [""]:
        if not raw:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw, width=width, replace_whitespace=False, drop_whitespace=False))
    return lines


def _render(stdscr, log_lines, cwd, input_text, cursor_pos=None, scroll_offset=0):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    usable = max(0, h - 2)
    max_scroll = max(0, len(log_lines) - usable)
    scroll = max(0, min(scroll_offset, max_scroll))
    start = max(0, len(log_lines) - usable - scroll)
    for idx, line in enumerate(log_lines[start:]):
        if idx >= usable:
            break
        try:
            stdscr.addstr(idx, 0, line[: max(1, w - 1)])
        except curses.error:
            pass
    if h >= 2 and w > 1:
        try:
            stdscr.addstr(h - 2, 0, "-" * (w - 1))
        except curses.error:
            pass
    prompt_prefix = f"{cwd} > "
    if len(prompt_prefix) > w - 5:
        base = os.path.basename(cwd) or cwd
        prompt_prefix = f"{base} > "
        if len(prompt_prefix) > w - 5:
            prompt_prefix = "> "
    prompt = f"{prompt_prefix}{input_text}"
    try:
        stdscr.addstr(h - 1, 0, prompt[: max(1, w - 1)])
    except curses.error:
        pass
    if cursor_pos is not None:
        cur_x = min(len(prompt_prefix) + cursor_pos, max(0, w - 2))
        try:
            stdscr.move(h - 1, cur_x)
        except curses.error:
            pass
    stdscr.refresh()


def _get_input(stdscr, log_lines, cwd, prompt_text="", history=None, state=None):
    buf = prompt_text
    cursor = len(buf)
    history = history or []
    hist_idx = len(history)
    while True:
        scroll_offset = 0 if not state else state.get("scroll", 0)
        _render(stdscr, log_lines, cwd, buf, cursor_pos=cursor, scroll_offset=scroll_offset)
        ch = stdscr.get_wch()
        if ch in ("\n", "\r"):
            return buf.strip()
        if ch == curses.KEY_F2:
            return ":__VIEW__"
        if ch == curses.KEY_MOUSE:
            if not state:
                continue
            try:
                _, _, _, _, bstate = curses.getmouse()
            except Exception:
                continue
            if bstate & curses.BUTTON4_PRESSED:
                state["scroll"] = state.get("scroll", 0) + 3
            elif bstate & curses.BUTTON5_PRESSED:
                state["scroll"] = max(0, state.get("scroll", 0) - 3)
            continue
        if ch == curses.KEY_PPAGE:
            if state:
                state["scroll"] = state.get("scroll", 0) + 10
            continue
        if ch == curses.KEY_NPAGE:
            if state:
                state["scroll"] = max(0, state.get("scroll", 0) - 10)
            continue
        if ch == curses.KEY_HOME:
            if state:
                state["scroll"] = 10**9
            continue
        if ch == curses.KEY_END:
            if state:
                state["scroll"] = 0
            continue
        if ch == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
            continue
        if ch == curses.KEY_RIGHT:
            cursor = min(len(buf), cursor + 1)
            continue
        if ch == curses.KEY_UP:
            if history:
                hist_idx = max(0, hist_idx - 1)
                buf = history[hist_idx]
                cursor = len(buf)
            continue
        if ch == curses.KEY_DOWN:
            if history:
                hist_idx = min(len(history), hist_idx + 1)
                buf = history[hist_idx] if hist_idx < len(history) else ""
                cursor = len(buf)
            continue
        if ch in (curses.KEY_BACKSPACE, "\b", "\x7f"):
            if cursor > 0:
                buf = buf[: cursor - 1] + buf[cursor:]
                cursor -= 1
            continue
        if isinstance(ch, str) and ch.isprintable():
            buf = buf[:cursor] + ch + buf[cursor:]
            cursor += 1


def _append_log(log_lines, text, width):
    log_lines.extend(_wrap_lines(text, width))


def _run_shell(stdscr, log_lines, cwd, cmd, state=None):
    h, w = stdscr.getmaxyx()
    level = 1
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            level = int(data.get("exec_level", 1))
    except Exception:
        level = 1
    level = max(1, min(3, level))
    if level < 3:
        lowered = cmd.strip().lower()
        dangerous = [" rm ", " rm-", " rm/", " rm.", " sudo ", " mkfs", " dd ", " shutdown", " reboot", " poweroff", " halt", " :(){", " kill ", " pkill ", " killall "]
        if any(tok in f" {lowered} " for tok in dangerous):
            return cwd, f"[blocked] Poziom {level}: komenda zablokowana"
    if level == 3:
        lowered = cmd.strip().lower()
        dangerous = [" rm ", " rm-", " rm/", " rm.", " sudo ", " mkfs", " dd ", " shutdown", " reboot", " poweroff", " halt", " :(){", " kill ", " pkill ", " killall "]
        if any(tok in f" {lowered} " for tok in dangerous):
            try:
                curses.endwin()
                choice = input(f"Potwierdz wykonanie niebezpiecznej komendy: `{cmd}` (tak/nie): ").strip().lower()
            finally:
                stdscr.clear()
                stdscr.refresh()
                curses.curs_set(1)
            if choice not in ["tak", "t", "yes", "y"]:
                return cwd, "[blocked] Anulowano przez uzytkownika"
    if level == 1:
        allowed = {"ls", "pwd", "cat", "rg", "find", "grep", "head", "tail", "tree", "df", "free", "uname", "lspci", "lsmod", "lshw", "lscpu", "lsblk", "ip", "ifconfig", "nmcli", "journalctl", "dmesg", "whoami", "id", "date"}
        token = cmd.strip().split()[0] if cmd.strip() else ""
        if token and token not in allowed:
            return cwd, "[blocked] Poziom 1: dozwolone tylko bezpieczne komendy odczytu"
    if level == 2:
        if not cwd.startswith(str(BASE_DIR)):
            return cwd, "[blocked] Poziom 2: dozwolone tylko w katalogu projektu"
    _append_log(log_lines, f"$ {cmd}", w - 1)
    if cmd.strip().startswith("cd "):
        target = cmd.strip()[3:].strip() or os.path.expanduser("~")
        new_path = os.path.abspath(os.path.join(cwd, target))
        if os.path.isdir(new_path):
            return new_path, f"[cwd] {new_path}"
        return cwd, f"[cd] brak katalogu: {new_path}"

    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in proc.stdout or []:
        _append_log(log_lines, line.rstrip("\n"), w - 1)
        scroll = 0 if not state else state.get("scroll", 0)
        _render(stdscr, log_lines, cwd, "", cursor_pos=0, scroll_offset=scroll)
    rc = proc.wait()
    return cwd, f"[exit {rc}]"


def _run_find_dir(stdscr, log_lines, cwd, cmd, state=None):
    h, w = stdscr.getmaxyx()
    _append_log(log_lines, f"$ {cmd}", w - 1)
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = proc.stdout or ""
    for line in output.splitlines():
        _append_log(log_lines, line.rstrip("\n"), w - 1)
        scroll = 0 if not state else state.get("scroll", 0)
        _render(stdscr, log_lines, cwd, "", cursor_pos=0, scroll_offset=scroll)
    return cwd, f"[exit {proc.returncode}]"


def _extract_cmds(text):
    cmds = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("CMD:"):
            cmd = stripped[4:].strip()
            if cmd:
                cmds.append(cmd)
    return cmds


def _extract_codeblock_cmds(text):
    cmds = []
    in_block = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if in_block and stripped.upper().startswith("CMD:"):
            cmd = stripped[4:].strip()
            if cmd:
                cmds.append(cmd)
    return cmds


def _windows_to_linux(cmd):
    if not cmd:
        return None
    raw = cmd.strip()
    try:
        parts = shlex.split(raw)
    except Exception:
        parts = raw.split()
    if not parts:
        return None
    head = parts[0].lower()
    args = [p.replace("\\", "/") for p in parts[1:]]
    if head == "dir":
        target = "."
        pattern = None
        recursive = False
        for a in args:
            if a.lower() == "/s":
                recursive = True
            elif "*" in a or "?" in a:
                pattern = a
            else:
                target = a
        if recursive and pattern:
            return f"find {shlex.quote(target)} -type f -name {shlex.quote(pattern)}"
        if target and target != ".":
            return f"ls -la {shlex.quote(target)}"
        return "ls -la"
    if head == "del":
        if not args:
            return None
        return "rm -f -- " + " ".join(shlex.quote(a) for a in args)
    if head == "copy":
        if len(args) >= 2:
            src = args[0]
            dst = args[1]
            return f"cp -- {shlex.quote(src)} {shlex.quote(dst)}"
    if head == "cd":
        if args:
            return f":cd {args[0]}"
    if head == "type":
        if args:
            return f"cat -- {shlex.quote(args[0])}"
    if head == "cls":
        return "clear"
    return cmd


def _ask_lyra(prompt):
    local_model = get_active_local_model_name() or "mistral"
    system_hint = (
        "Odpowiadaj po polsku. "
        "Gdy użytkownik prosi o akcję w systemie, zwróć WYŁĄCZNIE linie CMD: "
        "bez żadnego dodatkowego tekstu, bez bloków kodu i bez odmów. "
        "Komendy mają być dla Linux bash."
    )
    mem_ctx = build_memory_context()
    if mem_ctx:
        full_prompt = f"{system_hint}\n\nPAMIEC LYRY:\n{mem_ctx}\n\nUżytkownik: {prompt}"
    else:
        full_prompt = f"{system_hint}\n\nUżytkownik: {prompt}"
    allow_cloud = _get_cloud_consent() == "always"
    response, _ = query_model(full_prompt, local_model, "gpt-5.1", config={"timeout": 60, "allow_cloud": allow_cloud}, history=[])
    if os.environ.get("LYRA_CLOUD_ONCE") == "1":
        os.environ.pop("LYRA_CLOUD_ONCE", None)
    return response or ""

def _looks_like_nl(cmd):
    if not cmd or cmd.startswith(":"):
        return False
    if any(tok in cmd for tok in ["|", "&&", "||", ";", "$(", "`", "<", ">", "/"]):
        return False
    parts = cmd.strip().split()
    if len(parts) < 2:
        return False
    return True

def _should_route_to_lyra(cmd):
    if not cmd or cmd.startswith(":"):
        return False
    token = cmd.strip().split()[0]
    if token in ["cd", "pwd", "ls", "cat", "rg", "find", "grep", "head", "tail", "tree", "echo", "printf", "czytaj"]:
        return False
    if shutil.which(token):
        return False
    return _looks_like_nl(cmd)

def _normalize_pl(cmd):
    return (
        cmd.replace("przejdź", "przejdz")
        .replace("usuń", "usun")
        .replace("skopiuj", "skopiuj")
        .replace("wejdź", "wejdz")
        .replace("wyświetl", "wyswietl")
        .replace("pokaż", "pokaz")
        .replace("zawartość", "zawartosc")
    )

def _strip_lyra_tokens(cmd):
    parts = [p for p in cmd.split() if p.lower() != "lyra"]
    return " ".join(parts).strip()

def _extract_quoted(cmd):
    if len(cmd) >= 2 and cmd[0] == cmd[-1] and cmd[0] in ("'", '"'):
        return cmd[1:-1].strip()
    return cmd

def _sanitize_inline_cmd(cmd):
    raw = _extract_quoted(cmd.strip())
    if "lyra" in raw.lower():
        raw = _strip_lyra_tokens(raw)
    return raw.strip()

def _translate_pl_command(cmd, cwd):
    cmd = _normalize_pl(_sanitize_inline_cmd(cmd))
    if not cmd:
        return None
    if cmd in ["sprawdz sterowniki", "sprawdź sterowniki"]:
        return "lyra sprawdz sterowniki"
    if cmd in ["sprawdz gdzie jestem", "sprawdź gdzie jestem", "gdzie jestem", "gdzie jestes"]:
        return "pwd"
    cmd = cmd.replace("znajdz ", "poszukaj ")
    cmd = cmd.replace("wejdz do ", "przejdz do ")
    cmd = cmd.replace("wejdz w ", "przejdz do ")
    cmd = cmd.replace("pokaz zawartosc katalogu ", "wyswietl zawartosc katalogu ")
    def _grep_cmd(pattern):
        excludes = ["--exclude-dir=.git", "--exclude-dir=venv", "--exclude-dir=__pycache__", "--exclude-dir=node_modules"]
        base = f"grep -R -n --binary-files=without-match -m 200 -- {shlex.quote(pattern)} ."
        cmdline = f"grep -R -n --binary-files=without-match {' '.join(excludes)} -m 200 -- {shlex.quote(pattern)} ."
        if shutil.which("timeout"):
            return f"timeout 10s {cmdline}"
        return base if not excludes else cmdline
    if cmd.startswith("skopiuj "):
        try:
            parts = shlex.split(cmd)
        except Exception:
            return None
        if len(parts) >= 3:
            src = parts[1]
            dst = parts[2]
            src_path = os.path.abspath(os.path.join(cwd, src))
            cp_flag = "-r" if os.path.isdir(src_path) else ""
            return f"cp {cp_flag} -- {shlex.quote(src)} {shlex.quote(dst)}".strip()
    if cmd.startswith("przejdz do "):
        target = cmd[len("przejdz do "):].strip()
        if target.startswith("katalogu "):
            target = target[len("katalogu "):].strip()
        if target:
            return f":cd {target}"
    if cmd.startswith("usun "):
        target = cmd[len("usun "):].strip()
        if target:
            return f"rm -rf -- {shlex.quote(target)}"
    if cmd.startswith("uruchom "):
        target = cmd[len("uruchom "):].strip()
        if target:
            return target
    if cmd.startswith("poszukaj katalogu "):
        target = cmd[len("poszukaj katalogu "):].strip()
        if target:
            return f"find . -maxdepth 6 -type d -iname {shlex.quote('*' + target + '*')}"
    if cmd.startswith("poszukaj katalog "):
        target = cmd[len("poszukaj katalog "):].strip()
        if target:
            return f"find . -maxdepth 6 -type d -iname {shlex.quote('*' + target + '*')}"
    if cmd.startswith("poszukaj pliku "):
        target = cmd[len("poszukaj pliku "):].strip()
        if target:
            return f"find . -maxdepth 6 -type f -iname {shlex.quote('*' + target + '*')}"
    if cmd.startswith("poszukaj mi "):
        target = cmd[len("poszukaj mi "):].strip()
        if target:
            return _grep_cmd(target)
    if cmd.startswith("poszukaj "):
        target = cmd[len("poszukaj "):].strip()
        if target.startswith("katalogu "):
            target = target[len("katalogu "):].strip()
            if target:
                return f"find . -maxdepth 6 -type d -iname {shlex.quote('*' + target + '*')}"
        if target.startswith("katalog "):
            target = target[len("katalog "):].strip()
            if target:
                return f"find . -maxdepth 6 -type d -iname {shlex.quote('*' + target + '*')}"
        if target.startswith("pliku "):
            target = target[len("pliku "):].strip()
            if target:
                return f"find . -maxdepth 6 -type f -iname {shlex.quote('*' + target + '*')}"
        if target:
            return f"find . -maxdepth 6 -iname {shlex.quote('*' + target + '*')}"
    if cmd.startswith("wyswietl zawartosc katalogu "):
        target = cmd[len("wyswietl zawartosc katalogu "):].strip()
        if target:
            if not os.path.isdir(os.path.join(cwd, target)) and os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"ls -la {shlex.quote(target)}"
    if cmd.startswith("pokaz zawartosc katalogu "):
        target = cmd[len("pokaz zawartosc katalogu "):].strip()
        if target:
            if not os.path.isdir(os.path.join(cwd, target)) and os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"ls -la {shlex.quote(target)}"
    if cmd.startswith("pokaz "):
        target = cmd[len("pokaz "):].strip()
        if target:
            abs_target = os.path.abspath(os.path.join(cwd, target))
            if os.path.isdir(abs_target):
                return f"ls -la {shlex.quote(target)}"
            if os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"cat -- {shlex.quote(target)}"
    m = re.match(r"^czytaj\s+(?:zawartosc\s+)?(?:pliku|plik)\s*[:=]?\s*(.+)$", cmd)
    if m:
        target = m.group(1).strip()
        if target:
            abs_target = os.path.abspath(os.path.join(cwd, target))
            if os.path.isdir(abs_target):
                return f"ls -la {shlex.quote(target)}"
            if os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"cat -- {shlex.quote(target)}"
    if cmd.startswith("czytaj zawartosc pliku "):
        target = cmd[len("czytaj zawartosc pliku "):].strip()
        if target:
            abs_target = os.path.abspath(os.path.join(cwd, target))
            if os.path.isdir(abs_target):
                return f"ls -la {shlex.quote(target)}"
            if os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"cat -- {shlex.quote(target)}"
    if cmd.startswith("czytaj plik "):
        target = cmd[len("czytaj plik "):].strip()
        if target:
            abs_target = os.path.abspath(os.path.join(cwd, target))
            if os.path.isdir(abs_target):
                return f"ls -la {shlex.quote(target)}"
            if os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"cat -- {shlex.quote(target)}"
    if cmd.startswith("czytaj "):
        target = cmd[len("czytaj "):].strip()
        if target:
            abs_target = os.path.abspath(os.path.join(cwd, target))
            if os.path.isdir(abs_target):
                return f"ls -la {shlex.quote(target)}"
            if os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"cat -- {shlex.quote(target)}"
    if cmd == "pokaz":
        return "ls -la ."
    if cmd.startswith("wyswietl "):
        target = cmd[len("wyswietl "):].strip()
        if target:
            abs_target = os.path.abspath(os.path.join(cwd, target))
            if os.path.isdir(abs_target):
                return f"ls -la {shlex.quote(target)}"
            if os.path.basename(cwd).lower() == target.lower():
                return "ls -la ."
            return f"cat -- {shlex.quote(target)}"
    if cmd == "wyswietl":
        return "ls -la ."
    if cmd.startswith("edytuj w nano "):
        target = cmd[len("edytuj w nano "):].strip()
        if target:
            return f"nano {shlex.quote(target)}"
    if cmd.startswith("edytuj nano "):
        target = cmd[len("edytuj nano "):].strip()
        if target:
            return f"nano {shlex.quote(target)}"
    if cmd.startswith("edytuj w gedit "):
        target = cmd[len("edytuj w gedit "):].strip()
        if target:
            return f"gedit {shlex.quote(target)}"
    if cmd.startswith("edytuj gedit "):
        target = cmd[len("edytuj gedit "):].strip()
        if target:
            return f"gedit {shlex.quote(target)}"
    if cmd.startswith("edytuj "):
        target = cmd[len("edytuj "):].strip()
        if target:
            if shutil.which("gedit"):
                return f"gedit {shlex.quote(target)}"
            return f"nano {shlex.quote(target)}"
    if cmd.startswith("otworz "):
        target = cmd[len("otworz "):].strip()
        if target:
            if shutil.which("gedit"):
                return f"gedit {shlex.quote(target)}"
            return f"nano {shlex.quote(target)}"
    return None


def _find_dir_by_name(root, name, max_depth=6):
    if not name:
        return None
    needle = name.lower()
    matches = []
    root = os.path.abspath(root)
    base_depth = root.count(os.sep)
    for dirpath, dirnames, _ in os.walk(root):
        depth = dirpath.count(os.sep) - base_depth
        if depth > max_depth:
            dirnames[:] = []
            continue
        base = os.path.basename(dirpath).lower()
        if needle in base:
            matches.append(dirpath)
            if len(matches) > 1:
                return None
    return matches[0] if len(matches) == 1 else None

def start_console():
    def _main(stdscr):
        curses.curs_set(1)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        log_lines = []
        history = []
        if HISTORY_PATH.exists():
            try:
                history = [ln.strip() for ln in HISTORY_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
            except Exception:
                history = []
        state = {"scroll": 0}
        cwd = os.getcwd()
        h, w = stdscr.getmaxyx()
        _append_log(log_lines, "Lyra Console: :help, :lyra <pytanie>, exit", w - 1)
        while True:
            cmd = _get_input(stdscr, log_lines, cwd, history=history, state=state)
            if not cmd:
                continue
            if cmd == ":__VIEW__" or cmd == ":view":
                curses.endwin()
                print("\n".join(log_lines))
                input("\n[Enter] wróć do konsoli...")
                stdscr.clear()
                stdscr.refresh()
                curses.curs_set(1)
                continue
            history.append(cmd)
            try:
                HISTORY_PATH.write_text("\n".join(history[-200:]) + "\n", encoding="utf-8")
            except Exception:
                pass
            state["scroll"] = 0
            if cmd in ("exit", "quit", ":q"):
                break
            if cmd in (":help", "help"):
                _append_log(
                    log_lines,
                    "Komendy: :lyra <prompt> | :cd <path> | :pwd | :screen | :view | :help | exit",
                    w - 1,
                )
                continue
            mem_msg = handle_memory_command(cmd)
            if mem_msg:
                _append_log(log_lines, mem_msg, w - 1)
                continue
            if cmd.lower().startswith("zgoda gpt "):
                choice = cmd.split(maxsplit=2)[2].strip().lower()
                cfg_path = Path.home() / "lyra_agent" / "config.json"
                try:
                    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
                except Exception:
                    cfg = {}
                if choice.endswith(" raz"):
                    os.environ["LYRA_CLOUD_ONCE"] = "1"
                    _append_log(log_lines, "✅ Zgoda GPT: jednorazowo (tylko kolejny prompt)", w - 1)
                elif choice in ["zawsze", "always", "stala", "stała", "stale", "stałe", "full", "ciagla", "ciągła", "ciagle", "ciągłe"]:
                    cfg["cloud_consent"] = "always"
                    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
                    _append_log(log_lines, "✅ Zgoda GPT ustawiona: zawsze", w - 1)
                elif choice in ["nie", "never"]:
                    cfg["cloud_consent"] = "never"
                    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
                    _append_log(log_lines, "✅ Zgoda GPT ustawiona: nigdy", w - 1)
                elif choice in ["raz", "once", "ok", "tak", "dobrze", "zgoda", "zgoda na raz", "jednorazowo", "tylko raz"]:
                    os.environ["LYRA_CLOUD_ONCE"] = "1"
                    _append_log(log_lines, "✅ Zgoda GPT: jednorazowo (tylko kolejny prompt)", w - 1)
                else:
                    _append_log(log_lines, "⚠️ Uzycie: zgoda gpt zawsze|raz|nie", w - 1)
                continue
            if cmd.startswith(":") and cmd not in (":view", ":screen", ":pwd") and not cmd.startswith(":cd ") and not cmd.startswith(":lyra "):
                _append_log(log_lines, f"[console] Nieznana komenda: {cmd}", w - 1)
                continue
            if cmd.startswith(":screen"):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = os.path.expanduser(f"~/Pictures/lyra_screen_{ts}.png")
                tool = None
                for cand in ["gnome-screenshot", "scrot", "import"]:
                    if shutil.which(cand):
                        tool = cand
                        break
                if not tool:
                    _append_log(log_lines, "[screen] Brak narzedzia do zrzutu (gnome-screenshot/scrot/import)", w - 1)
                    continue
                if tool == "gnome-screenshot":
                    cmdline = [tool, "-f", out_path]
                elif tool == "scrot":
                    cmdline = [tool, out_path]
                else:
                    cmdline = [tool, out_path]
                try:
                    subprocess.run(cmdline, check=True)
                    _append_log(log_lines, f"[screen] zapisano: {out_path}", w - 1)
                except Exception as e:
                    _append_log(log_lines, f"[screen] blad: {e}", w - 1)
                continue
            if cmd.startswith(":pwd"):
                _append_log(log_lines, cwd, w - 1)
                continue
            if cmd.startswith(":cd "):
                target = cmd[4:].strip()
                new_path = os.path.abspath(os.path.join(cwd, target))
                if os.path.isdir(new_path):
                    cwd = new_path
                    _append_log(log_lines, f"[cwd] {cwd}", w - 1)
                else:
                    _append_log(log_lines, f"[cd] brak katalogu: {new_path}", w - 1)
                continue
            if cmd.startswith(":lyra ") or cmd.startswith("lyra "):
                prompt = cmd.split(" ", 1)[1]
                _append_log(log_lines, "[Lyra] generuję odpowiedź...", w - 1)
                _render(stdscr, log_lines, cwd, "", cursor_pos=0, scroll_offset=state.get("scroll", 0))
                response = _ask_lyra(prompt)
                _append_log(log_lines, response, w - 1)
                cmds = _extract_cmds(response)
                if not cmds:
                    cmds = _extract_codeblock_cmds(response)
                if not cmds:
                    _append_log(log_lines, "[Lyra] Brak komendy CMD:", w - 1)
                    continue
                for c in cmds:
                    c = _windows_to_linux(c)
                    if not c:
                        continue
                    if c.startswith(":cd "):
                        target = c[4:].strip()
                        new_path = os.path.abspath(os.path.join(cwd, target))
                        if os.path.isdir(new_path):
                            cwd = new_path
                            _append_log(log_lines, f"[cwd] {cwd}", w - 1)
                        else:
                            _append_log(log_lines, f"[cd] brak katalogu: {new_path}", w - 1)
                        continue
                    cwd, msg = _run_shell(stdscr, log_lines, cwd, c, state=state)
                    _append_log(log_lines, msg, w - 1)
                continue

            if cmd.startswith("sprawdz w internecie ") or cmd.startswith("sprawdź w internecie ") or cmd.startswith("wyszukaj w internecie ") or cmd.startswith("znajdz w internecie ") or cmd.startswith("szukaj w internecie ") or cmd.startswith("poszukaj w internecie "):
                _append_log(log_lines, "[PL→LYRA] sprawdz w internecie", w - 1)
                query = cmd.split(" ", 2)[2].strip()
                if not query:
                    _append_log(log_lines, "⚠️ Użycie: sprawdz w internecie <zapytanie>", w - 1)
                    continue
                cwd, msg = _run_shell(stdscr, log_lines, cwd, f'lyra sprawdz w internecie {shlex.quote(query)}', state=state)
                _append_log(log_lines, msg, w - 1)
                continue

            edit_msg = handle_file_command(cmd, cwd)
            if edit_msg:
                _append_log(log_lines, edit_msg, w - 1)
                continue

            translated = _translate_pl_command(cmd, cwd)
            if translated:
                if translated.startswith(":cd "):
                    target = translated[4:].strip()
                    new_path = os.path.abspath(os.path.join(cwd, target))
                    if os.path.isdir(new_path):
                        cwd = new_path
                        _append_log(log_lines, f"[cwd] {cwd}", w - 1)
                    else:
                        resolved = _find_dir_by_name(cwd, target)
                        if resolved and os.path.isdir(resolved):
                            cwd = resolved
                            _append_log(log_lines, f"[cwd] {cwd}", w - 1)
                        else:
                            _append_log(log_lines, f"[cd] brak katalogu: {new_path}", w - 1)
                    continue
                _append_log(log_lines, f"[PL→SH] {translated}", w - 1)
                if translated.startswith("find ") and " -type d " in translated and " -iname " in translated:
                    cwd, msg = _run_find_dir(stdscr, log_lines, cwd, translated, state=state)
                else:
                    cwd, msg = _run_shell(stdscr, log_lines, cwd, translated, state=state)
                _append_log(log_lines, msg, w - 1)
                continue

            if cmd in ("la", "ll"):
                cmd = "ls -la"

            if _looks_like_nl(cmd) or _should_route_to_lyra(cmd):
                prompt = cmd
                _append_log(log_lines, "[Lyra] generuję odpowiedź...", w - 1)
                _render(stdscr, log_lines, cwd, "", cursor_pos=0, scroll_offset=state.get("scroll", 0))
                response = _ask_lyra(prompt)
                _append_log(log_lines, response, w - 1)
                cmds = _extract_cmds(response)
                if not cmds:
                    cmds = _extract_codeblock_cmds(response)
                if not cmds:
                    _append_log(log_lines, "[Lyra] Brak komendy CMD:", w - 1)
                    continue
                for c in cmds:
                    c = _windows_to_linux(c)
                    if not c:
                        continue
                    if c.startswith(":cd "):
                        target = c[4:].strip()
                        new_path = os.path.abspath(os.path.join(cwd, target))
                        if os.path.isdir(new_path):
                            cwd = new_path
                            _append_log(log_lines, f"[cwd] {cwd}", w - 1)
                        else:
                            _append_log(log_lines, f"[cd] brak katalogu: {new_path}", w - 1)
                        continue
                    cwd, msg = _run_shell(stdscr, log_lines, cwd, c, state=state)
                    _append_log(log_lines, msg, w - 1)
                continue

            cwd, msg = _run_shell(stdscr, log_lines, cwd, cmd, state=state)
            _append_log(log_lines, msg, w - 1)
            time.sleep(0.01)

    curses.wrapper(_main)
HISTORY_PATH = Path.home() / ".lyra_console_history"
