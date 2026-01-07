import subprocess

def run(cmd: str, timeout: int = 30, **kwargs):
    try:
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, text=True, timeout=timeout
        )
        output = result.stdout.strip()
        # Jeśli komenda zadziałała (kod 0), ale nic nie wypisała
        if not output and result.returncode == 0:
            return f"✅ Wykonano pomyślnie: {cmd}"
        return output or "[Brak odpowiedzi systemowej]"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Przekroczono {timeout}s: {cmd}"
    except Exception as e:
        return f"[ERROR] {e}"
