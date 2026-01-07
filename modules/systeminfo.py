import psutil, platform, os, subprocess

def tool_SYSINFO(arg, system_tool, log):
    try:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uname = platform.uname()

        info = (
            f"🧠 CPU: {cpu}% użycia\n"
            f"💾 RAM: {ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB\n"
            f"💽 Dysk: {disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB\n"
            f"🖥 System: {uname.system} {uname.release} ({uname.machine})\n"
        )
        return info
    except Exception as e:
        return f"[Błąd SYSINFO] {e}"
