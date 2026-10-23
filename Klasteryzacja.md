# Klasteryzacja w projekcie

Projekt analizuje decyzje moderacyjne zgłaszane do DSA Transparency Database:
porównuje sankcje stosowane przez YouTube, Instagram i TikTok wobec tych samych
kategorii naruszeń oraz udział decyzji podejmowanych w pełni automatycznie.


## Jednostka i metoda grupowania

Grupujemy **profile platforma × kategoria naruszenia**, opisane ważonymi przez
`count` udziałami każdej sankcji oraz pełnej automatyzacji. Platforma i
kategoria są etykietami interpretacyjnymi, a nie cechami klasteryzacji.
Sankcje są osobnymi, współwystępującymi wskaźnikami; nie są zamieniane w jedną
klasę decyzji.

W profilu udział TRUE ma mianownik równy ważonej sumie znanych wyników
`TRUE + FALSE`. Wartość `UNKNOWN` jest raportowana osobno: liczebnością ważoną,
udziałem w całkowitym `count` profilu oraz przez jawny mianownik znanych
wyników. Nieznane dane nie są zamieniane na brak sankcji. Porównania platform
wykonuje się w obrębie tej samej kategorii. Raport zawiera opisowe przedziały
Wilson 95% tylko dla całkowitych mianowników; zakładają one niezależność
reprezentowanych decyzji, więc nie zastępują testu hipotez.

Klasteryzacja hierarchiczna średniego wiązania i odległości euklidesowej jest
wyłącznie eksploracyjna. Powstają dwa warianty: same udziały sankcji oraz
udziały sankcji wraz z pełną automatyzacją. Próg odcięcia trzeba jawnie podać
po obejrzeniu danych; nie ma domyślnej, arbitralnie wybranej liczby klastrów.
Liczba platform jest ograniczona do trzech i wynik nie jest typologią samych
platform. Projekt nie dodaje predykcji.

## Dane

Źródłowy Parquet nie jest śledzony w repozytorium. Skrypt
`scripts/prepare_dataset.py` czyta go z `data/aggregated-complete.parquet/` i
zapisuje próbę jako `data/dataset_3_platforms_sep_01_29.parquet`. Sprawdzony
lokalny plik ma daty od 1 do 29 września 2026 r., 1 341 968 wierszy i trzy
platformy. Rzeczywiste nazwy kolumn to `platform_name`, `category` i `count`.
`category` zawiera 14 kodów `STATEMENT_CATEGORY_*`; właściwe wartości są
zachowane w danych oraz w `analysis_summary.json`. Pola
`STATEMENT_CATEGORY_*` są osobnymi flagami, a nie kolumną do grupowania.

`count` ma typ `Int64`, nie zawiera braków, a jego suma w przygotowanej próbie
wynosi 63 590 477 (min. 1, max. 448 905) jest to liczba decyzji reprezentowana przez każdy
zagregowany wiersz. W analizie profile, liczniki i mianowniki ważone są tym
polem.

## Uruchomienie

Zależności projektu (m.in. pandas i polars) muszą być już dostępne w wybranym
środowisku.

[Poradnik Windows]
Z katalogu głównego repozytorium, w PowerShell. Krok `prepare_dataset.py`
można pominąć, jeśli plik próbki został już przygotowany:

```text
.\.venv\Scripts\python.exe -X utf8 scripts\prepare_dataset.py
.\.venv\Scripts\python.exe -X utf8 scripts\pipeline.py --platform-column platform_name --category-column category --count-column count --cluster-distance-threshold 0.1
```

Pipeline uruchamia ładowanie, czyszczenie, gold standard, inżynierię
cech, walidację i klasteryzację w tej kolejności. Próg `0.1` powyżej jest
wartością testową, którą sprawdziłem na obecnych danych.
Bez opcjonalnych argumentów pipeline pomija klasteryzację.

Pipeline używa
`scripts/gold_standard.py` oraz istniejącego pliku
`scripts/feature_enginnering.py`.
Jeśli inżynieria cech już się wykonała klasteryzację można
uruchomić niezależnie:

```text
.\.venv\Scripts\python.exe -X utf8 scripts\clustering.py --platform-column platform_name --category-column category --count-column count --distance-threshold 0.1
```

Wyniki trafiają do `reports/clustering/`:

- `weighted_profiles.csv` — ważone profile, liczniki TRUE/FALSE/UNKNOWN,
  znane mianowniki i udziały;
- `platform_comparisons.csv` — porównania udziałów platform w obrębie
  kategorii wraz z mianownikami, UNKNOWN i opisowymi przedziałami;
- `raw_code_counts.csv` — zachowane surowe kody decyzji i ich ważone
  liczebności;
- `hierarchical_merges.csv` — pełne hierarchie połączeń dla obu wariantów;
- `cluster_assignments.csv` — przypisania do klastrów poniżej podanego progu
  (profile bez obliczalnych udziałów pozostają jawnie nieprzypisane);
- `analysis_summary.json` — ustawienia, kategorie, platformy, ograniczenia i
  opis mianowników.

Walidacja codebooka zapisuje raporty w `reports/instrument_validation/`.
