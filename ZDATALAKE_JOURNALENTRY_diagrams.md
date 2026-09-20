# ZDATALAKE_JOURNALENTRY – Diagramme

Report: Übertragung der Buchhaltungsbelege (BKPF + BSEG) an den Datalake  
Autor: Ralf Joswig, 17.08.2026

---

## Klassendiagramm

```mermaid
classDiagram
    class main {
        <<FINAL>>
        +run()$
        -init_datalake_transfer()$
        -get_and_transfer_data()$
        -handle_log()$
        -init_xsl_transformation()$
        -add_item_to_entry(entry_items, journal_entry)$
        -datalake_transfer : REF TO zcl_datalake_transfer_tools
    }

    class selection_screen_filename {
        <<FINAL>>
        +fill_filenames()$
        -fill_filename_server()$
        -fill_filename_presentation()$
        -fill_filename_google()$
    }

    class zcl_datalake_transfer_tools {
        +log : REF TO logger
        +start_monitoring()
        +stop_monitoring()
        +transfer_data(data)
        +log_display()
    }

    class zcl_file_selection_screen {
        +modify_selection_screen_datei()$
        +test_input_block_datei()$
        +f4_filename_praesentation()$
    }

    class zcl_json_to_xslt {
        +get_instance()$
        +create_xslt_transform_by_data()
    }

    class ZO_Datalake_JournalEntry {
        <<CDS View>>
        company_Code
        fiscal_Year
        accounting_Document
    }

    class ZO_Datalake_JournalEntryItem {
        <<CDS View>>
        company_Code
        fiscal_Year
        accounting_Document
        accounting_Document_Item
    }

    main --> zcl_datalake_transfer_tools : nutzt
    main --> zcl_json_to_xslt : XSLT-Transformation
    main ..> ZO_Datalake_JournalEntry : SELECT
    main ..> ZO_Datalake_JournalEntryItem : SELECT FOR ALL ENTRIES
    selection_screen_filename --> zcl_datalake_constants : Pfad-Konstanten
    zcl_file_selection_screen --> main : AT SELECTION-SCREEN
```

---

## Ablaufdiagramm

```mermaid
flowchart TD
    A([INITIALIZATION]) --> B[fill_filenames\nDateipfade vorbelegen]
    B --> C([AT SELECTION-SCREEN OUTPUT])
    C --> D[modify_selection_screen_datei\nFelder ein-/ausblenden]
    D --> E([AT SELECTION-SCREEN ON BLOCK file])
    E --> F{Ausführen?}
    F -->|Ja| G[test_input_block_datei\nEingaben prüfen]
    G --> H([START-OF-SELECTION])
    F -->|Nein| H

    H --> I[main::run]
    I --> J[init_datalake_transfer\nObjekt mit allen Parametern anlegen]
    J --> K{Fehler?}
    K -->|Ja| L[Abbruch MESSAGE A]
    K -->|Nein| M[get_and_transfer_data]

    M --> N[start_monitoring]
    N --> O[init_xsl_transformation\nXSLT neu erzeugen]
    O --> P{XSLT-Fehler?}
    P -->|Ja| Q[Fehler im Log]
    Q --> R[stop_monitoring]
    P -->|Nein| S

    S[SELECT aus ZO_Datalake_JournalEntry\nOFFSET + UP TO p_blocks Zeilen] --> T{Keine Daten\nmehr?}
    T -->|Ja – EXIT| R
    T -->|Nein| U[SELECT ZO_Datalake_JournalEntryItem\nFOR ALL ENTRIES]
    U --> V[LOOP: add_item_to_entry\nPositionen dem Beleg zuordnen]
    V --> W[FREE entry_items]
    W --> X[transfer_data\nDaten übertragen]
    X --> Y{Transfer-\nFehler?}
    Y -->|Ja – EXIT| Z[FREE data]
    Z --> R
    Y -->|Nein| AA[FREE data]
    AA -->|nächster Block| S

    R --> AB[handle_log]
    AB --> AC[log_display\nAnwendungslog anzeigen]
    AC --> AD([Ende])
```

---

## Datenfluss: Blockweise Verarbeitung

```mermaid
flowchart LR
    DB1[(ZO_Datalake_JournalEntry\nCDS View)] -->|SELECT OFFSET n UP TO p_blocks| BUF1[data\ninternal table]
    DB2[(ZO_Datalake_JournalEntryItem\nCDS View)] -->|FOR ALL ENTRIES| BUF2[entry_items\nsorted table]
    BUF1 & BUF2 -->|add_item_to_entry| MERGED[data mit\nnested entry_item]
    MERGED -->|transfer_data| OUT{Ausgabe}
    OUT --> F1[Logischer Dateiname]
    OUT --> F2[App-Server-Datei]
    OUT --> F3[Präsentationsserver]
    OUT --> F4[Google Datalake\nBucket: JournalEntry]
```
