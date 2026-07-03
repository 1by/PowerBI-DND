# DND Monitor — bpost kantoor Aalst

Power BI-monitoringoplossing voor de Dense/Non-Dense (DND) piloot die start
op **21/09/2026**: 61 dense diensten (JL/JM, vaste dag-om-dag ronden) en 19
non-dense diensten (JT/JU, dynamisch grondgebied).

## Mapstructuur

```
PowerBI-DND/
├── bron/                              Ruwe bronbestanden (Excel), niet bewerken
│   ├── diensten_met_detail_ronden_en_extra_info.xlsx
│   ├── diensten_met_uitreikingsgebied_en_LS_dagen.xlsx
│   ├── pakken_en_bussen_samengevat.xlsx
│   ├── vergelijking_oude_en_nieuwe_ronden_procentueel.xlsx
│   └── sorteerlijst.xlsx
├── reference_pdf/                     Plannetjes (zone-kaarten) — enkel visuele context, geen databron
├── data/                              Output van prep_data.py — wordt door Power Query ingelezen
│   ├── DimDienst.csv
│   ├── FactBaseline.csv
│   ├── BridgeOudNieuw.csv
│   ├── DimStraat.csv
│   └── DimDate.csv
├── realisatie/                        Wekelijkse realisatie-exports (zie hieronder)
│   ├── pod/                           PoD-scans, 1 CSV per week
│   ├── klara/                         KLARA-klachten, 1 CSV per week
│   └── historisch/                    Eenmalige historische baseline (vóór de piloot, oude rondestructuur)
├── prep_data.py                       Data-preparatie (pandas + openpyxl, geen internet)
├── DND_Monitor.pbip                   PBIP-projectbestand — dit open je in Power BI Desktop
├── DND_Monitor.SemanticModel/         TMDL semantic model (star schema + DAX measures)
└── DND_Monitor.Report/                Lege PBIR-shell + pagina_spec.md (zie "Rapportpagina's")
```

## 1. `prep_data.py` draaien

Vereisten: Python 3 met enkel `pandas` en `openpyxl` (geen andere packages,
geen internetcalls).

```bash
python3 prep_data.py
```

Leest alles uit `./bron/` en schrijft de 5 CSV's naar `./data/`. Bij elke
mislukte validatie stopt het script met een duidelijke `AssertionError` —
er wordt nooit stilzwijgend gecorrigeerd. Waarschuwingen (bv. ontbrekende
brondata voor een specifieke dienst) worden gelogd, niet "gefixt".

Bekende afwijkingen in de huidige brondata (geen bug, gewoon een gat in de
bron dat niet verzonnen mag worden):
- **JL049 / JM049** hebben geen rij in `pakken_en_bussen_samengevat.xlsx`
  → geen `FactBaseline`-rij voor deze dienst.
- **JL018 / JM018** hebben geen rij in
  `vergelijking_oude_en_nieuwe_ronden_procentueel.xlsx` → geen
  Bridge-mapping voor deze dienst (geen herwogen pre/post-vergelijking
  mogelijk voor ronde 18).

## 2. PBIP openen in Power BI Desktop

1. Zorg dat **Power BI Desktop developer mode** aanstaat: `Bestand →
   Opties en instellingen → Opties → Preview-functies → "Power BI Project
   (.pbip) opslagformaat"` aanvinken, Desktop herstarten.
2. Dubbelklik `DND_Monitor.pbip` (of `Bestand → Openen` en kies het
   bestand).
3. **Power Query-parameters instellen** (eenmalig, want de CSV's worden
   via een parameter-pad ingelezen zodat het project overal lokaal werkt
   zonder hardcoded paden):
   - `Transformeren van gegevens → Parameters beheren`
   - `DataFolder` → volledig pad naar de `data`-map, bv.
     `C:\...\PowerBI-DND\data\` (met backslash op het einde)
   - `RealisatieFolder` → volledig pad naar de `realisatie`-map, bv.
     `C:\...\PowerBI-DND\realisatie\` (met backslash op het einde)
   - Sluiten → Toepassen, dan **Vernieuwen** (Refresh).
4. Als de parameters om een of andere reden niet meekomen (TMDL-import
   kan hier gevoelig zijn): maak ze gewoon manueel aan via `Nieuwe
   Parameter` met dezelfde naam/type Tekst, en plak de M-code uit de
   `partition ... = m` sectie van het betreffende `.tmdl`-bestand in
   `DND_Monitor.SemanticModel/definition/tables/` in de Advanced Editor
   van de gelijknamige query.
5. Het rapport-canvas opent leeg (1 placeholder-pagina "Piloot
   Overzicht"). Bouw de 3 pagina's uit volgens
   `DND_Monitor.Report/pagina_spec.md` — alle measures bestaan al in
   `_Measures`, je hoeft enkel visuals te slepen en in te stellen (zie
   die spec voor het "waarom" van deze aanpak).

## 3. Wekelijkse realisatie-exports toevoegen

`FactRealisatie`, `KLARA` en `PodVolumeHistorisch` laden **alle CSV's**
uit hun respectievelijke map in `./realisatie/` en combineren ze (`Folder.
Files` + `Table.Combine`). Elke map bevat al een `_template.csv` (header,
0 rijen) zodat het model direct kan verversen zonder fout, ook vóór er
echte data is.

Zet elke week een nieuw bestand in de juiste map — bestandsnaam maakt niet
uit, zolang het `.csv` is en exact de kolomkoppen hieronder gebruikt.
**UTF-8, ISO-datums (`YYYY-MM-DD`), tijden als `HH:MM`.**

### `./realisatie/pod/*.csv` — PoD-scans (1 rij per dienst-dag)

| Kolom | Type | Omschrijving |
|---|---|---|
| `Datum` | datum | Kalenderdag van de ronde |
| `RondeKey` | tekst | JLxxx/JMxxx/JTxxx/JUxxx — moet matchen met `DimDienst[RondeKey]` |
| `LaatsteScanTijd` | tijd (`HH:MM`) | Tijdstip laatste PoD-scan van de ronde |
| `WerkelijkEindUur` | tijd (`HH:MM`) | Werkelijk einduur van de dienst |
| `GerealiseerdPakketten` | geheel getal | Aantal effectief uitgereikte pakketten |
| `GerealiseerdBussen` | geheel getal | Aantal effectief uitgereikte bussen |
| `UitgesteldeStukken` | geheel getal | Aantal niet-uitgereikte/uitgestelde stukken |

### `./realisatie/klara/*.csv` — KLARA-klachten (1 rij per dag/ronde/klachttype)

| Kolom | Type | Omschrijving |
|---|---|---|
| `Datum` | datum | Datum van de klacht |
| `RondeNr` | tekst | Ronde-nummer zoals gekend in KLARA op dat moment — **vóór 21/09/2026 zijn dit OUDE ronde-nummers** (bv. `Res-036`), **vanaf 21/09/2026 de NIEUWE** (bv. `Res-001`). Dit is bewust: het Bridge-patroon (zie semantic model) herweegt de oude klachten automatisch naar de nieuwe structuur. |
| `Klachttype` | tekst | Vrije tekst-categorie |
| `AantalKlachten` | geheel getal | Aantal klachten in deze rij |

### `./realisatie/historisch/*.csv` — historische PoD-volumes vóór de piloot (eenmalig, niet wekelijks)

| Kolom | Type | Omschrijving |
|---|---|---|
| `Datum` | datum | Historische datum (vóór 21/09/2026) |
| `RondeNr` | tekst | OUDE ronde-nummer |
| `AantalStukken` | geheel getal | Historisch PoD-volume voor die oude ronde |

Dit is de baseline die via `BridgeOudNieuw` herwogen wordt naar de nieuwe
structuur (measure `PoD Baseline Herwogen`), voor de Pre/Post-vergelijking
op pagina 3.

## Semantic model — ontwerp

Star schema, alle relaties enkelrichting (dim → fact):

- `DimDienst (1) → FactBaseline (*)` op `RondeKey`
- `DimDate (1) → FactRealisatie (*)` op `Date`/`Datum`
- `DimDienst (1) → FactRealisatie (*)` op `RondeKey`
- `DimDate (1) → KLARA (*)` op `Date`/`Datum`
- `DimDate (1) → PodVolumeHistorisch (*)` op `Date`/`Datum`
- `BridgeOudNieuw`, `KLARA`, `PodVolumeHistorisch`: **geen fysieke relatie
  naar `DimDienst`/`FactBaseline`** — hun `RondeNr` kan zowel oud als
  nieuw zijn (bij KLARA/PodVolumeHistorisch) of is per definitie de
  brug tussen beide (bij BridgeOudNieuw). Ze worden uitsluitend via
  `TREATAS` in measures gekoppeld (zie `_Measures`).
- `DimStraat`: bewust **geen relatie** toegevoegd — dit stond niet in de
  opgegeven relatielijst. `DimStraat[RondeNr]` matcht wel met
  `FactBaseline[RondeNr]` (te zien in de data), dus als je automatische
  filtering wil op de stratenlijst-pagina, voeg je zelf de relatie
  `FactBaseline (RondeNr) → DimStraat (RondeNr)` toe in de modelweergave.
- `_Measures`: lege measure-tabel (calculated table `{BLANK()}`), bevat
  alle DAX-measures, georganiseerd in displayfolders `Basis`,
  `Realisatie`, `Bridge`, `Leercurve`.

### Waarom `KLARA` en `PodVolumeHistorisch` als aparte tabellen?

De opdracht geeft het Bridge-patroon met een tabel `KLARA[RondeNr]` als
voorbeeld, en vraagt "zelfde patroon als template voor PoD-volumes". Geen
van de 5 opgegeven bronbestanden bevat historische PoD- of
klachtenvolumes op de oude rondestructuur — dat moet vanuit een apart
(toekomstig) exportbestand komen. Ik heb daarom het schema hierboven
(`./realisatie/klara/` en `./realisatie/historisch/`) zelf gedefinieerd,
zoals gevraagd, in plaats van dit te verzinnen als data.

## Data-brondetails (voor wie de mapping wil nakijken)

- **`diensten_met_detail_ronden_en_extra_info.xlsx`** (Blad1) bevat 2
  aparte tabellen in 1 blad: rijen 2–123 = dense (61 diensten × 2 dagen),
  rijen 126–144 = non-dense (19 diensten). `prep_data.py` detecteert deze
  blokken dynamisch via de herhaalde headerrij, niet via hardcoded
  rijnummers.
- **Non-dense Zone/Gemeente/Opmerking** komen niet uit bovenstaand
  bestand (daar staat enkel een generieke, identieke placeholder-tekst),
  maar uit `diensten_met_uitreikingsgebied_en_LS_dagen.xlsx`, dat wél de
  volledige, dienst-specifieke tekst bevat (incl. de effectieve vrije dag
  — vandaar de bonuskolom `VrijeDag` in `DimDienst`, niet expliciet
  gevraagd maar rechtstreeks uit de bron beschikbaar).
- **`HeeftDepRit`** = opmerking begint met "Dep" (case-insensitive).
  **`HeeftExtraTaak`** = opmerking is niet leeg, begint niet met "Dep" en
  is niet de non-dense boilerplate-tekst ("PakSat aanvang...").
- **`pakken_en_bussen_samengevat.xlsx`** (sheet "ronde totaal") bevat 2
  herhaalde headerrijen door plakwerk uit meerdere exports — deze worden
  genegeerd, niet meegeteld als data.
- **`vergelijking_oude_en_nieuwe_ronden_procentueel.xlsx`**: kolommen
  Dienst/DienstNr/RondeNr zijn forward-filled (merged-cell-stijl).
  `PctNieuw` = kolom "% Nieuwe Ronde" (het aandeel van de oude ronde in
  het volume van de nieuwe ronde — dit is de kolom die per NieuwRondeNr
  optelt tot ~100%, geverifieerd in `prep_data.py`).
- **`sorteerlijst.xlsx`**, sheet "per dienst en ronde": de laatste 3–4
  rijen zijn een legende (lege `Dienst`-kolom) en worden gedropt.

## Validatie-output (laatste run)

Zie de terminaloutput van `python3 prep_data.py` voor de actuele cijfers;
kernresultaten bij oplevering:

- `DimDienst`: 141 rijen (122 dense + 19 non-dense), 61 unieke dense
  DienstNr.
- `FactBaseline`: 130 rondes, som Bussen = **77.105** (exacte match),
  som Pakken ≈ 8.803,8.
- `BridgeOudNieuw`: 285 rijen, 118/118 NieuwRondeNr binnen 100 % ± 5.
- `DimStraat`: 1.758 straten, 119 unieke RondeNr.
- `DimDate`: 1.095 dagen (2025–2027), week 0 = 21–27/09/2026.
