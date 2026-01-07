#!/bin/bash

set -euo pipefail

LOG_FILE="$HOME/napraw_radeony.log"
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date '+%F %T')] $*"
}

XORG_LOGS=(
    "/var/log/Xorg.0.log"
    "$HOME/.local/share/xorg/Xorg.0.log"
)

find_xorg_log() {
    for log_path in "${XORG_LOGS[@]}"; do
        if [[ -r "$log_path" ]]; then
            echo "$log_path"
            return 0
        fi
    done
    return 1
}

detect_amdgpu_mismatch() {
    local log_path
    if log_path=$(find_xorg_log); then
        if grep -qi "amdgpu: module ABI major version" "$log_path"; then
            log "🧪 Znalazłem konflikt wersji AMDGPU w $log_path"
            return 0
        fi
    fi
    return 1
}

detect_libllvm_missing() {
    local log_path
    if log_path=$(find_xorg_log); then
        if grep -qi "libLLVM-10" "$log_path"; then
            log "🧪 Brakuje biblioteki libLLVM-10 w $log_path"
            return 0
        fi
    fi
    return 1
}

remove_amdgpu_stack() {
    if command -v amdgpu-install &>/dev/null; then
        log "🚨 Odinstalowuję pakiety AMD GPU (amdgpu-install --uninstall)"
        sudo amdgpu-install --uninstall --rocmrelease=all --usecase=graphics
    elif command -v amdgpu-uninstall &>/dev/null; then
        log "🚨 Odinstalowuję pakiety AMD GPU (amdgpu-uninstall)"
        sudo amdgpu-uninstall --rocmrelease=all
    else
        log "⚠️ Nie znaleziono helpera AMD, usuwam pakiety ręcznie."
        sudo apt-get purge -y 'amdgpu-*' 'rocm-*' >/dev/null
    fi
}

reinstall_mesa_stack() {
    local packages=(
        "xserver-xorg-video-amdgpu"
        "xserver-xorg-core"
        "libdrm-amdgpu1"
        "libgl1-mesa-dri"
        "libglx-mesa0"
        "mesa-vulkan-drivers"
        "libegl-mesa0"
    )

    log "↺ Przywracam domyślne pakiety Mesa i Xorg"
    sudo apt-get update >/dev/null
    sudo apt-get install --reinstall -y "${packages[@]}"
}

log "🚀 Rozpoczynam diagnostykę i naprawę Radeonów dla Lyry..."

# 0. Spójrzmy na log Xorg, może wskazuje na niezgodny sterownik
if detect_amdgpu_mismatch || detect_libllvm_missing; then
    log "🛠️ Znaleziono złe pakiety AMD – usuwam i przywracam sterownik open-source"
    remove_amdgpu_stack
    reinstall_mesa_stack
    log "✅ Zainstalowano domyślny stos Open Source. Zrestartuj system po skończeniu."
fi

# 1. Sprawdzenie grup użytkownika
log "🔍 Sprawdzam uprawnienia..."
for group in video render; do
    if groups "$USER" | grep -q "\\b$group\\b"; then
        log "✅ Użytkownik jest w grupie $group."
    else
        log "❌ Brak grupy $group. Dodaję..."
        sudo usermod -a -G "$group" "$USER"
        log "⚠️ Dodano grupę $group. Zmiany zadziałają po przelogowaniu!"
    fi
done

# 2. Sprawdzenie plików urządzeń
log "🔍 Sprawdzam pliki KFD i DRI..."
if [[ -e /dev/kfd && -e /dev/dri/renderD128 ]]; then
    log "✅ Urządzenia GPU widoczne w systemie."
    sudo chmod 666 /dev/kfd
else
    log "❌ System nie widzi kart Radeon! Sprawdź, czy moduł amdgpu nie został zablokowany."
fi

# 3. Wymuszenie wersji GFX (Ellesmere Fix)
log "🔍 Konfiguruję zmienne środowiskowe..."
export HSA_OVERRIDE_GFX_VERSION=8.0.3
if grep -q "HSA_OVERRIDE_GFX_VERSION" /etc/environment; then
    log "✅ Zmienna HSA_OVERRIDE_GFX_VERSION jest już w /etc/environment."
else
    echo "HSA_OVERRIDE_GFX_VERSION=8.0.3" | sudo tee -a /etc/environment >/dev/null
    log "✅ Dodano zmienną do /etc/environment."
fi

# 4. Restart Ollamy z nowymi parametrami
log "🔄 Restartuję usługę Ollama..."
sudo systemctl stop ollama
sleep 2
# Uruchomienie z jawnym eksportem dla pewności
sudo Environment="HSA_OVERRIDE_GFX_VERSION=8.0.3" systemctl start ollama

log "--------------------------------------------------"
log "✅ Naprawa zakończona!"
log "👉 TERAZ: Wyloguj się i zaloguj ponownie (lub zrestartuj PC)."
log "👉 POTEM: Wpisz 'ollama serve' i sprawdź, czy VRAM > 0B."
log "--------------------------------------------------"
