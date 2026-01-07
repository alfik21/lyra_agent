#!/bin/bash

SESSION="lyra_session"

# Sprawdź czy sesja już istnieje, jeśli tak - zamknij ją
tmux kill-session -t $SESSION 2>/dev/null

# Stwórz nową sesję i okno dla Lyry
tmux new-session -d -s $SESSION -n "Lyra_Core"

# Podziel okno na panele
# Lewy panel: Serwer LLM (Vulkan/llama-server)
tmux send-keys -t $SESSION:0.0 "cd ~/lyra_agent/llama.cpp/build && ./bin/llama-server -m ../../models/mistral --port 11434 --n-gpu-layers 99 --vulkan" C-m

# Prawy górny panel: Monitor GPU (Radeony)
tmux split-window -h -t $SESSION:0.0
tmux send-keys -t $SESSION:0.1 "watch -n 1 'cat /sys/class/drm/card*/device/mem_info_vram_used'" C-m

# Prawy dolny panel: Interfejs Lyry
tmux split-window -v -t $SESSION:0.1
tmux send-keys -t $SESSION:0.2 "cd ~/lyra_agent && python3 agent.py" C-m

# Ustaw fokus na panelu z Lyrą
tmux select-pane -t $SESSION:0.2

# Podłącz się do sesji
tmux attach-session -t $SESSION
