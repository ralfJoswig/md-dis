---
type: Source Summary
title: ZDATALAKE_BILLING_DOCUMENT
description: ABAP-Report zur Übertragung von Fakturaköpfen und -positionen (VBRK/VBRP) an den GCP Datalake.
tags: [datalake, abap, report, faktura, billingdocument, vbrk, vbrp, gcp]
timestamp: 2026-07-06T00:00:00Z
---

# ZDATALAKE_BILLING_DOCUMENT

**Paket:** ZDATALAKE_TRANSFER  
**Autor:** Ralf Joswig  
**Erstellt:** 20.03.2025  
**Jira:** OIA-35372  
**SAP-Objekt-URI:** `/sap/bc/adt/programs/programs/zdatalake_billing_document`

## Zweck

Übertragung von Fakturaköpfen (`ZC_Datalake_BillingDocumentHea`) und den zugehörigen Positionen (`ZC_Datalake_BillingDocumentIte`) als verschachtelte JSON-Struktur an den GCP Datalake (Bucket: `BillingDocument`). Die Serialisierung erfolgt über eine dynamisch erzeugte XSLT-Transformation (`zcl_json_to_xslt`).

## Selektionsparameter

| Parameter   | Typ            | Beschreibung                               |
|-------------|----------------|--------------------------------------------|
| `s_saleso`  | SELECT-OPTIONS | Verkaufsorganisation (SalesOrganization)   |
| `s_docume`  | SELECT-OPTIONS | Fakturanummer (BillingDocument)            |
| `s_creatd`  | SELECT-OPTIONS | Erstellungsdatum (CreationDate)            |
| `p_blocks`  | PARAMETER      | Blockgröße (Standard: 250.000 Zeilen)      |
| `p_zip`     | CHECKBOX       | Ausgabedatei als ZIP komprimieren          |
| `p_test`    | CHECKBOX       | Testmodus (Standard: aktiv)                |
| `p_mail`    | CHECKBOX       | Ergebnis per E-Mail versenden              |

## Ausgabe

| Konstante        | Wert                                     |
|------------------|------------------------------------------|
| Dateiname        | `{TIME}_BillingDocument_{NUMBER}.json`   |
| Unterverzeichnis | `billing_document`                       |
| GCP Bucket-Pfad  | `BillingDocument`                        |
| BAL-Unterobjekt  | `BILLING_DOCUMENTS`                      |

## Datenquelle

- Kopf-CDS-View: `ZC_Datalake_BillingDocumentHea` (basierend auf `ZO_BillingDocumentHead`)
- Positions-CDS-View: `ZC_Datalake_BillingDocumentIte` (basierend auf `ZO_BillingDocumentItem`)
- Struktur: Positionen werden pro Fakturakopf als `positions`-Array eingebettet
- Sortierung Köpfe: `billing_Document`
- Verknüpfung Positionen: `FOR ALL ENTRIES` auf `billing_Document`
- XSLT-Transformation wird bei jedem Lauf neu generiert (mit `NUMC_AS_NUMBER = true`)

## Besonderheiten

- `LastChangeDate = '00000000'` wird im CDS-View auf `'19000301'` umgeschrieben (Sentinel-Wert für „kein Änderungsdatum").
- Vor der Datenübertragung wird geprüft, ob die XSLT-Transformation erfolgreich erzeugt werden konnte; bei Fehler wird abgebrochen.

## Feldmapping

→ [Fieldmapping ZDATALAKE_BILLING_DOCUMENT](fieldmapping-ZDATALAKE_BILLING_DOCUMENT.md)
