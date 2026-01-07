import sys, psutil, subprocess, os, time
from PyQt5 import QtWidgets, QtGui, QtCore

class LyraTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.setToolTip("Lyra – systemowy asystent Tomka")
        self.menu = QtWidgets.QMenu(parent)

        status_action = self.menu.addAction("📊 Status systemu")
        status_action.triggered.connect(self.show_status)

        restart_action = self.menu.addAction("🔁 Restart Lyry")
        restart_action.triggered.connect(self.restart_lyra)

        log_action = self.menu.addAction("📜 Otwórz logi")
        log_action.triggered.connect(self.open_logs)

        quit_action = self.menu.addAction("❌ Zakończ")
        quit_action.triggered.connect(QtWidgets.qApp.quit)

        self.setContextMenu(self.menu)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.auto_check)
        self.timer.start(60_000)  # co minutę
        self.show()

    def auto_check(self):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        color = "green"
        if cpu > 90 or ram > 85: color = "red"
        elif cpu > 70 or ram > 70: color = "orange"
        self.setIcon(QtGui.QIcon.fromTheme(f"network-{color}"))
        self.setToolTip(f"Lyra – CPU:{cpu}% RAM:{ram}%")

    def show_status(self):
        subprocess.Popen(["lyra", "zdiagnozuj system"])

    def restart_lyra(self):
        subprocess.Popen(["systemctl", "--user", "restart", "lyra.service"])

    def open_logs(self):
        log_path = os.path.expanduser("~/lyra_agent/logs/")
        subprocess.Popen(["xdg-open", log_path])

def main():
    app = QtWidgets.QApplication(sys.argv)
    icon = QtGui.QIcon.fromTheme("face-smile")
    tray = LyraTray(icon)
    tray.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
