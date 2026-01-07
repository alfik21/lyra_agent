import json
import os
from datetime import datetime

class ZarzadcaPamieci:
    """
    ####--- CO: Zarządca Pamięci Wielopoziomowej ---####
    ####--- DLACZEGO: Aby Lyra wiedziała co było rok temu i co Tomek wpisał przed chwilą ---####
    """
    def __init__(self, folder_projektu="."):
        self.sciezki = {
            "dluga": os.path.join(folder_projektu, "Pamiec.json"),
            "krotka": os.path.join(folder_projektu, "Kontekst.json"),
            "biezaca": os.path.join(folder_projektu, "PamiecBiezaca.json"),
            "logowa": os.path.join(folder_projektu, "PamiecLogowa.json")
        }
        self._inicjuj_pliki()

    def _inicjuj_pliki(self):
        """Tworzy pliki JSON, jeśli Tomek jeszcze ich nie ma."""
        for nazwa, sciezka in self.sciezki.items():
            if not os.path.exists(sciezka):
                with open(sciezka, 'w', encoding='utf-8') as f:
                    init_value = {} if nazwa == "dluga" else []
                    json.dump(init_value, f, ensure_ascii=False)

    def zapisz_fakt(self, klucz, wartosc):
        """
        ####--- NA CO: Pamięć Długa ---####
        Służy do zapamiętywania stałych faktów (np. 'IP radia to 192.168.1.50').
        """
        dane = self.odczytaj("dluga")
        dane[klucz] = wartosc
        self._zapisz_na_dysk("dluga", dane)

    def dodaj_do_osi_czasu(self, opis):
        """
        ####--- NA CO: Pamięć Bieżąca ---####
        Zapisuje zdarzenie z automatu z datą i godziną.
        """
        wpis = {
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "zdarzenie": opis
        }
        dane = self.odczytaj("biezaca")
        dane.append(wpis)
        self._zapisz_na_dysk("biezaca", dane[-100:]) # Trzymamy 100 ostatnich zdarzeń

    def loguj_technicznie(self, tytul, tresc):
        """
        ####--- NA CO: Pamięć Logowa ---####
        Zapisuje kody błędów, skrypty i konfiguracje terminala.
        """
        log = {
            "timestamp": datetime.now().isoformat(),
            "modul": tytul,
            "dane": tresc
        }
        dane = self.odczytaj("logowa")
        dane.append(log)
        self._zapisz_na_dysk("logowa", dane[-50:])

    def odczytaj(self, rodzaj):
        """Pobiera dane z konkretnego poziomu pamięci."""
        try:
            with open(self.sciezki[rodzaj], 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return [] if rodzaj != "dluga" else {}

    def _zapisz_na_dysk(self, rodzaj, dane):
        with open(self.sciezki[rodzaj], 'w', encoding='utf-8') as f:
            json.dump(dane, f, indent=2, ensure_ascii=False)
    def zapisz_kontekst(self, tresc):
        """
        ####--- NA CO: Pamięć Krótka ---####
        Historia bieżącej sesji (jak bash_history).
        """
        wpis = {
            "timestamp": datetime.now().isoformat(),
            "tresc": tresc
        }
        dane = self.odczytaj("krotka")
        dane.append(wpis)
        self._zapisz_na_dysk("krotka", dane[-200:])

# Instancja do użycia w agent.py
pamiec = ZarzadcaPamieci()
