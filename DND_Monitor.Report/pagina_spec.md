# Pagina-specificatie — DND Monitor rapport

> Waarom een spec in plaats van kant-en-klare PBIR-bestanden? Het Power BI
> report-format (PBIR/`definition/pages/...`) bestaat uit veel onderling
> verwijzende JSON-bestanden (visual-id's, z-order, conditionele opmaak,
> drillthrough-koppelingen) die alleen betrouwbaar te valideren zijn door ze
> in Power BI Desktop te openen. Zonder die validatiestap zou ik met
> handgeschreven JSON een gerede kans lopen op een rapport dat niet opent.
> Deze spec is exact genoeg om de 3 pagina's snel na te bouwen in Power BI
> Desktop (of te laten bouwen door Copilot/een collega) tegen het semantic
> model in `DND_Monitor.SemanticModel`. Alle meetwaarden bestaan al als
> measures in `_Measures` — je hoeft enkel visuals te slepen.

Canvas: 1280 x 720, thema "neutraal" (max. 4 kleuren: grijs/neutraal
achtergrond, 1 accentkleur voor "goed", 1 voor "aandacht", 1 voor "afwijking").
Gebruik conditionele kleuren enkel om afwijkingen te highlighten — geen
kleur op cellen die binnen de norm zitten.

---

## Pagina 1 — "Piloot Overzicht"

**Layout (boven naar onder):**

1. **KPI-rij** (4 cards, gelijke breedte, bovenaan, hoogte ~120px)
   - Card 1: `% Ronden Binnen Eindtijd` — format 0.0%
   - Card 2: `Niet-Uitgereikt Non-Dense` — format #,0
   - Card 3: `Aantal Klachten` naast `Klachten Baseline Herwogen`
     (gebruik een "Card met vergelijking" of 2 kleine cards naast elkaar:
     "Klachten (werkelijk)" en "Klachten (herwogen baseline)")
   - Card 4: `Overuren Minuten` — format #,0

   Elke card: BLANK()-waarden tonen als "—" (Card-opmaak: "Toon niets bij
   leeg" desactiveren, of gebruik een Tekstvak met een IF-measure die "Nog
   geen realisatiedata" toont zolang `FactRealisatie` leeg is).

2. **Weektrend** (lijngrafiek, volle breedte, hoogte ~220px)
   - As X: `DimDate[Date]` (of `DimDate[WekenSindsStart]` als alternatieve
     as-optie)
   - Lijnen: `% Ronden Binnen Eindtijd`, `Overuren Minuten` (secundaire as,
     want andere schaal), optioneel `Aantal Klachten`
   - **Verticale referentielijn** op 21/09/2026 (piloot-start): Analytics-paneel
     → "Constante lijn" op de X-as op datum 2026-09-21, label "Start piloot",
     stippellijn, neutrale kleur.

3. **Dienst-matrix** (matrix-visual, volle breedte, hoogte ~300px)
   - Rijen: `DimDienst[DienstNr]` (evt. gegroepeerd onder `DimDienst[Type]`)
   - Kolommen (measures): `% Ronden Binnen Eindtijd`, `Overuren Minuten`,
     `Delta vs Norm %`, `Bussen Norm`, `Pakken Norm`
   - **Conditionele opmaak** op `Delta vs Norm %`: kleurschaal met 3 punten
     (bv. -10% = rood/oranje, 0% = neutraal grijs, +10% = blauw/oranje) —
     gebruik exact dezelfde 2 "afwijkings"-kleuren als de rest van het
     rapport, geen 5e kleur toevoegen.
   - Sortering: aflopend op `ABS(Delta vs Norm %)` zodat grootste afwijkingen
     bovenaan staan (vereist een verborgen sorteer-measure `ABS([Delta vs
     Norm %])` indien matrix-sortering op absolute waarde gewenst is).

**Pagina-filter:** slicer op `DimDienst[Type]` (dense/non-dense) bovenaan,
niet in de KPI-rij maar als aparte smalle balk erboven.

---

## Pagina 2 — "Dienst Detail" (drillthrough op `DimDienst[DienstNr]`)

**Drillthrough-instelling:** drillthroughfilter op `DimDienst[DienstNr]`
(rechtsklik op een rij in de matrix van pagina 1 → "Drill through" →
"Dienst Detail").

**Layout:**

1. **Header**: kaarten met `DimDienst[Voertuig]`, `DimDienst[Zone]`,
   `DimDienst[Gemeente]` voor de geselecteerde dienst (First-visible-value
   of gewoon tekstvak gebonden aan de kolom).

2. **Dag 1 vs Dag 2 vergelijking** (geclusterde kolomgrafiek of 2 cards
   naast elkaar)
   - Filter op `DimDienst[DagType] = "dag 1"` resp. `"dag 2"`
   - Toon: `BeginUur`, `EindUur`, `Bussen Norm`, `Pakken Norm` per dag
   - Voor non-dense diensten (DagType = "elke dag") toont dit blok gewoon 1
     kolom i.p.v. 2 — geen aparte visual-variant nodig, de filter lost dit
     vanzelf op.

3. **Stratenlijst** (tabel, volle breedte)
   - Bron: `DimStraat` gefilterd op `RondeNr` — **let op**: er is bewust
     géén fysieke relatie tussen `DimStraat` en `DimDienst` gebouwd (zie
     README, sectie "Ontwerpkeuzes"), omdat `DimStraat[RondeNr]` en
     `FactBaseline[RondeNr]` wel matchen maar dat een fact-tabel als
     "1-kant" van een relatie zou maken. Voor een werkende drillthrough-
     koppeling: voeg zelf een relatie `FactBaseline (RondeNr) → DimStraat
     (RondeNr)` toe in Power BI Desktop (Modelweergave → relatie slepen),
     enkelrichting, dim-achtig gedrag blijft behouden omdat `DimStraat` de
     "veel-kant" wordt. Kolommen: `Postcode`, `Deelgemeente`, `Straat`,
     `Nummerbereik`.

4. **Norm vs realisatie trend** (lijngrafiek)
   - As X: `DimDate[Date]`
   - Lijnen: `Pakken Norm` (constante referentielijn, want RondeNiveau-norm
     zonder datum) vs `SUM(FactRealisatie[GerealiseerdPakketten])`
   - Filter geërfd van drillthrough (`DienstNr`)

5. **Opmerkingen** (tekstvak of card, gebonden aan `DimDienst[Opmerking]`,
   `HeeftDepRit`, `HeeftExtraTaak`, en voor non-dense `VrijeDag`)

---

## Pagina 3 — "Pre/Post Vergelijking"

**Layout:**

1. **Filters**: slicer op Zone (`DimDienst[Zone]`) en op "pizza"/RondeType
   (`FactBaseline[RondeType]`)

2. **Herwogen baseline naast realisatie** (geclusterde kolomgrafiek,
   gegroepeerd per Zone)
   - Reeks 1: `Klachten Baseline Herwogen` (herwogen, vóór piloot)
   - Reeks 2: `Aantal Klachten` (werkelijk, na piloot-start — filter
     `DimDate[Date] >= 21/09/2026` via een visual-filter of via een
     aparte measure `Aantal Klachten Na Start`)
   - Reeks 3 & 4: idem met `PoD Baseline Herwogen` / `PoD Volume` op een
     tweede grafiek ernaast (zelfde layout, andere measures)

3. **Tabel per Zone/RondeType**: `Zone`, `RondeType`, `Klachten Baseline
   Herwogen`, `Aantal Klachten`, `Delta` (= verschil), `PoD Baseline
   Herwogen`, `PoD Volume`

---

## Algemene rapport-instellingen

- Thema: 1 neutrale achtergrondkleur, 1 tekstkleur, max. 2 accentkleuren
  voor afwijkingen (bv. amber = aandacht, rood = kritiek). Geen 5+ kleuren
  kleurenpaletten op grafieken — gebruik dezelfde 2 accentkleuren overal.
- Alle measures tonen BLANK() als "—" zolang `FactRealisatie`/`KLARA` leeg
  zijn (zie README voor hoe je de eerste wekelijkse export toevoegt).
- Voeg een vast tekstvak "Piloot gestart: 21/09/2026 — Dag {DATEDIFF(...,
  TODAY(), DAY)} van de piloot" toe in de paginakop van pagina 1.
