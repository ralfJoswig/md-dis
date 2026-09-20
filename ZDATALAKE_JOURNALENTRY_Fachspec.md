# Reverse-Engineered Funktionsspezifikation: ZDATALAKE_JOURNALENTRY

**Quelle:** ABAP-Report `ZDATALAKE_JOURNALENTRY` + Klasse `ZCL_DATALAKE_TRANSFER_TOOLS` (gelesen via ADT/MCP am 25.08.2026)
**Methode:** Reverse-Engineering nach dem Sechs-Schritte-Verfahren aus `Reverse-eingineering.txt`
**Autor (lt. Report-Header):** Ralf Joswig, 17.08.2026, OIA-37511

---

## Schritt 1 – Grenze (Boundary)

**Eingaben (Selektionsbild):**
- `s_bukrs` (Company Code), `s_gjahr` (Fiscal Year) – fachliche Selektion
- `p_blocks` (Default 250.000) – Blockgröße fürs Lesen
- Zieldatei: genau eine von vier Radiobutton-Optionen – logischer Dateiname, physischer Pfad (App-Server), Präsentationsserver (lokal), oder Google Cloud Storage
- `p_zip` – Ausgabe als ZIP
- `p_mail` + `s_mailad` – E-Mail-Benachrichtigung bei Fehlern
- `p_test` – **Default `abap_true`** (!)

**Ausgaben:**
- JSONL-Datei (Buchhaltungsbelege), abgelegt je nach gewähltem Ziel, oder Upload in einen Google-Cloud-Storage-Bucket (`JournalEntry`)
- Anwendungslog (BAL) unter Subobjekt `JOURNALENTRY`
- Interface-Monitoring-Eintrag (`ZCL_IFM_MONITORING`)
- Optional: Fehler-Mail

**Kontrakt in einem Satz:** Selektiert Buchhaltungsbelege (Header + Positionen) nach Buchungskreis/Geschäftsjahr, serialisiert sie blockweise als JSONL und überträgt sie an den Datalake (Datei oder Google Cloud Storage), inkl. Monitoring und Logging.

---

## Schritt 2 – Datenquellen

| Business-Objekt | Quelle | Schlüssel |
|---|---|---|
| Belegkopf | CDS View `ZO_Datalake_JournalEntry` (Wrapper auf BKPF) | `company_Code`, `fiscal_Year`, `accounting_Document` |
| Belegposition | CDS View `ZO_Datalake_JournalEntryItem` (Wrapper auf BSEG) | zusätzlich `accounting_Document_Item` |

Lesefolge: erst Header blockweise (`OFFSET`/`UP TO p_blocks ROWS`, sortiert nach Buchungskreis/Jahr/Beleg), dann `FOR ALL ENTRIES` die dazugehörigen Positionen, anschließend Zusammenbau zu einer geschachtelten Struktur (`entry_item` als Subtabelle je Header).

> **Offene Frage (Schritt 6):** Die genauen Felder der beiden CDS-Views wurden nicht einzeln gegen das DDIC verifiziert – nur die in `SELECT *`/`WHERE` sichtbaren Schlüsselfelder sind bestätigt.

---

## Schritt 3 – Verarbeitung

1. Anlage/Prüfung der XSLT-Transformation (`init_xsl_transformation`) – bricht bei Fehler die Übertragung ab, bevor überhaupt Daten gelesen werden.
2. Blockweises Lesen der Header (Speicherschutz).
3. `FOR ALL ENTRIES`-Nachlesen der Positionen.
4. Zuordnung Position → Header über `FILTER` auf sortierter Tabelle (`add_item_to_entry`).
5. Serialisierung zu JSONL – dynamisch verzweigt: existiert eine XSLT-Transformation mit dem Programmnamen (`ZDATALAKE_JOURNALENTRY`), wird diese genutzt, sonst `/UI2/CL_JSON=>SERIALIZE` als Fallback.
6. Übertragung: Datei speichern **oder** Google-Cloud-Upload (exklusiv, je nach Radiobutton).
7. Wiederholung pro Block, Abbruch bei Fehler im Transfer.

---

## Schritt 4 – Business-Regeln vs. Plumbing

**Business-Regeln (gehören in den Fachspec):**
- Selektion nur nach Buchungskreis + Geschäftsjahr (keine weiteren fachlichen Filter wie Belegart, Konto etc.)
- Header-Position-Zuordnung 1:n über den Belegschlüssel
- Genau ein Zielsystem pro Lauf (Datei *oder* Google), keine Mehrfachverteilung
- Dateinamensschema `{TIME}_JournalEntry_{NUMBER}.json` inkl. Paketnummerierung bei mehreren Blöcken – relevant für die Datalake-seitige Ingestion
- **`p_test` ist standardmäßig aktiv** → ohne aktives Abwählen läuft der Report im Testmodus: Es wird geloggt, aber nichts tatsächlich gespeichert/übertragen (`IF is_test = abap_false` umschließt jeden echten Schreibzugriff)

**Plumbing (gehört NICHT in den Fachspec):**
- Blockgröße/Offset-Schleife (Speicherschutz)
- `FREE` statt `CLEAR` für Zwischentabellen
- Wahl XSLT-Transformation vs. `/UI2/CL_JSON` (rein technisches Serialisierungsdetail)
- ZIP-Komprimierung als Technikoption

---

## Schritt 5 – Nebeneffekte

- Schreibt eine Datei (Filesystem/Application Server/Präsentationsserver) **oder** lädt in einen Google-Cloud-Storage-Bucket hoch
- Schreibt Einträge in den Anwendungslog (BAL, Objekt `ZDATALAKE`/Subobjekt `JOURNALENTRY`)
- Schreibt einen Interface-Monitoring-Satz (Start/Stop, inkl. Fehlerstatus) – produktionsrelevant für Monitoring-Dashboards
- Versendet bei Fehler + `p_mail` eine E-Mail an `s_mailad`
- **Keine** Änderung an BKPF/BSEG selbst – reiner Leseprozess, keine Buchungsänderung
- Kein `AUTHORITY-CHECK` im Report sichtbar – auditrelevante Beobachtung

---

## Schritt 6 – Validierung / offene Punkte für den SME

1. Ist der Default `p_test = 'X'` eine bewusste Sicherheitsmaßnahme (Schutz vor versehentlichem Produktivlauf), oder ein Rest aus der Entwicklung? Für den produktiven Batch-Job müsste der Variantenwert explizit auf `false` stehen – wurde das geprüft?
2. Ist die Option „Präsentationsserver" für einen automatisierten Datalake-Feed überhaupt sinnvoll (setzt eine GUI-Session voraus) oder nur für manuelle Ad-hoc-Tests gedacht?
3. Welche Variante(n)/Jobs laufen produktiv, und welches Zielsystem (Datei vs. Google) ist dort aktiv?
4. Existiert die XSLT-Transformation `ZDATALAKE_JOURNALENTRY` im System? Das entscheidet, welcher der beiden Serialisierungspfade tatsächlich greift.

---

## Gefundene Fallen (Traps)

- **Silent no-op durch Default:** `p_test` default `true` – ein Lauf ohne explizite Parameteränderung sieht im Log erfolgreich aus, überträgt aber nichts.
- **Copy-Paste-Variante wahrscheinlich:** Der Code kommentiert explizit, dass `data_type`/`data_tt` "generisch" gehalten sind, "damit sie für verschiedene Entitäten wiederverwendet werden können" – deutet auf mehrere `ZDATALAKE_*`-Reports mit fast identischer Struktur hin (vgl. bestehende Design-Entscheidung zu `ZDATALAKE_FIELDS *`). Der Unterschied steckt vermutlich nur in Konstanten (`bal_sub_document`, `bucket_path`) und den zwei CDS-View-Namen.
- **Dynamisches Verhalten außerhalb des Programms:** Die JSON-Serialisierung hängt von einer zur Laufzeit gesuchten XSLT-Transformation ab (`cl_o2_api_xsltdesc=>load` mit `sy-cprog`) – Verhalten ändert sich, ohne dass es im Reportcode sichtbar ist.

---

## Fazit zum Test der Methode

Die Methode hat sich bewährt: Der Boundary-first-Ansatz (Schritt 1) lieferte den Kontrakt in kurzer Zeit, bevor die Detaillogik gelesen wurde. Die Trennung Business-Regel/Plumbing (Schritt 4) funktionierte sauber – einziger Grenzfall war der `p_test`-Default, der auf den ersten Blick wie Plumbing aussieht, aber fachlich hoch relevant ist (Produktivlauf vs. Trockenlauf). Die "Traps"-Liste traf direkt einen echten Kandidaten (Copy-Paste-Familie `ZDATALAKE_*`), was ohne die Methode vermutlich übersehen worden wäre.
