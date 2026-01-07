import shutil
from textwrap import indent

def tool_DISK_DIAG(arg, system_tool, log):
    """
    Diagnostyka dysków, partycji i systemu plików.
    """
    rep = []
    rep.append("=== DISK_DIAG – diagnostyka dysków ===\n")

    cmds = {
        "lsblk": "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,LABEL",
        "df -h": "df -h",
        "fstab": "cat /etc/fstab",
        "SMART": "sudo smartctl -a /dev/sda || echo 'SMART niedostępny'"
    }

    for title, command in cmds.items():
        rep.append(f"## {title}")
        out = system_tool(command)
        rep.append(f"$ {command}")
        rep.append(indent(out or "(brak danych)", "    "))
        rep.append("")
        if log:
            log(f"[DISK_DIAG {command}] {out[:2000]}", "disk_diag.log")

    rep.append("=== KONIEC DISK_DIAG ===")
    return "\n".join(rep)

