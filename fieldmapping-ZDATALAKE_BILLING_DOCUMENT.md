---
type: Concept
title: Fieldmapping ZDATALAKE_BILLING_DOCUMENT
description: Mapping der SAP-Quelltabellenfelder auf die CDS-Views ZC_Datalake_BillingDocumentHea und ZC_Datalake_BillingDocumentIte (Faktura Kopf/Positionen).
tags: [datalake, fieldmapping, abap, cds, faktura, billingdocument, vbrk, vbrp]
timestamp: 2026-07-06T00:00:00Z
---

# Fieldmapping ZDATALAKE_BILLING_DOCUMENT

Zuordnung der SAP-Quelltabellenfelder auf die CDS-Views `ZC_Datalake_BillingDocumentHea` (Kopf) und `ZC_Datalake_BillingDocumentIte` (Positionen), die vom Report `ZDATALAKE_BILLING_DOCUMENT` als Datenquellen verwendet werden.

## CDS-View-Stack

| CDS-View                         | Typ              | Paket         | Beschreibung              |
|----------------------------------|------------------|---------------|---------------------------|
| `ZC_Datalake_BillingDocumentHea` | Consumption View | ZDATALAKE_CDS | Datalake: Fakturen Kopf   |
| `ZO_BillingDocumentHead`         | Composite View   | ZDATALAKE_CDS | Fakturen Kopf (Basis)     |
| `ZC_Datalake_BillingDocumentIte` | Composite View   | ZDATALAKE_CDS | Datalake: Fakturen Positionen |
| `ZO_BillingDocumentItem`         | Composite View   | ZDATALAKE_CDS | Fakturen Positionen (Basis)   |

## Feldmapping – Fakturakopf (VBRK)

| SAP-Tabelle | SAP-Feld | CDS-View-Feld              | Beschreibung                                                          |
|-------------|----------|----------------------------|-----------------------------------------------------------------------|
| VBRK        | VBELN    | billing_Document           | Fakturabelegnummer (Schlüssel)                                        |
| VBRK        | ERDAT    | creation_Date              | Erfassungsdatum                                                       |
| VBRK        | ERZET    | creation_Time              | Erfassungszeit                                                        |
| VBRK        | FKDAT    | billing_Document_Date      | Fakturadatum                                                          |
| VBRK        | AEDAT    | last_Change_Date           | Letztes Änderungsdatum ('00000000' → '19000301' im CDS-View)          |
| VBRK        | GJAHR    | fiscal_Year                | Geschäftsjahr                                                         |
| VBRK        | VKORG    | sales_Organization         | Verkaufsorganisation                                                  |
| VBRK        | VTWEG    | distribution_Channel       | Vertriebsweg                                                          |
| VBRK        | SPART    | Division                   | Sparte                                                                |
| VBRK        | FKTYP    | billing_Document_Category  | Fakturakategorie                                                      |
| VBRK        | FKART    | billing_Document_Type      | Fakturaart                                                            |
| VBRK        | VBTYP    | sd_Document_Category       | SD-Belegkategorie                                                     |
| VBRK        | NETWR    | total_Net_Amount           | Gesamtnettobeleg in Belegwährung                                      |
| VBRK        | WAERK    | transaction_Currency       | Belegwährungsschlüssel                                                |
| VBRK        | KUNAG    | sold_To_Party              | Auftraggeber                                                          |
| VBRK        | KUNRG    | payer_Party                | Regulierer                                                            |
| VBRK        | STAFO    | statistics_Update_Group    | Fortschreibungsgruppe für Statistik                                   |

## Feldmapping – Fakturapositionen (VBRP)

| SAP-Tabelle | SAP-Feld | CDS-View-Feld                  | Beschreibung                                      |
|-------------|----------|--------------------------------|---------------------------------------------------|
| VBRP        | VBELN    | billing_Document               | Fakturabelegnummer (Schlüssel)                    |
| VBRP        | POSNR    | billing_Document_Item          | Fakturabelegposition (Schlüssel)                  |
| VBRP        | UEPOS    | higher_Level_Item              | Übergeordnete Position                            |
| VBRP        | NETWR    | net_Amount                     | Nettowert der Auftragsposition in Belegwährung    |
| VBRP        | WAERK    | transaction_Currency           | Belegwährungsschlüssel                            |
| VBRP        | VGBEL    | reference_Sd_Document          | SD-Vorbeleg                                       |
| VBRP        | VGPOS    | reference_Sd_Document_Item     | Position des SD-Vorbelegs                         |
| VBRP        | AUBEL    | sales_Document                 | SD-Auftragsnummer                                 |
| VBRP        | AUPOS    | sales_Document_Item            | Position im SD-Auftrag                            |
| VBRP        | MATNR    | product                        | Materialnummer                                    |
| VBRP        | ARKTX    | billing_Document_Item_Text     | Kurztext der Fakturabelegposition                 |
| VBRP        | MATKL    | product_Group                  | Warengruppe                                       |
| VBRP        | PRODH    | product_Hierarchy_Node         | Produkthierarchie                                 |
| VBRP        | PSTYV    | sales_Document_Item_Category   | SD-Positionstyp                                   |
| VBRP        | POSAR    | sales_Document_Item_Type       | Positionstyp                                      |
| VBRP        | KTGRM    | matl_Account_Assignment_Group  | Kontobestimmungsgruppe Material                   |
| VBRP        | ERDAT    | creation_Date                  | Erfassungsdatum                                   |
| VBRP        | ERZET    | creation_Time                  | Erfassungszeit                                    |
| VBRP        | STAFO    | statistics_Update_Group        | Fortschreibungsgruppe für Statistik               |

## Hinweise

- Die Positionen werden als verschachteltes Array `positions` im JSON des Fakturakopfes übertragen.
- Das Feld `last_Change_Date` enthält eine CASE-Logik: der SAP-Initialwert `'00000000'` wird auf `'19000301'` (Sentinel) umgeschrieben.
- Die XSLT-Transformation für die JSON-Serialisierung wird bei jedem Programmaufruf dynamisch neu generiert (mit `numc_as_number = true`).
- Verknüpfter Report: [ZDATALAKE_BILLING_DOCUMENT](abap-report-ZDATALAKE_BILLING_DOCUMENT.md)


## Mapping zu SAS/DWH und SAP-BW

Direktes Feldmapping der SAP-Quelltabellen zu den Feldern im SAS/DWH-Datenmodell und im SAP-BW. Eine SAP-Tabelle/Feld-Kombination kann auf mehrere BW-Felder abgebildet sein (je eine Zeile pro Zielfeld).

### VBRK

| SAP-Feld | SAS/DWH-Feld | SAS/DWH-Bezeichnung | BW-Feld | BW-Bezeichnung |
|----------|--------------|---------------------|---------|----------------|
| VBELN | FAKTNUM | Vertriebsbelegnummer (Fakturanummer) VBRK-VBELN | 0BILL_NUM | Faktura |
| FKART | FAKTART | Fakturaart VBRK-FKART | 0BILL_TYPE | Fakturaart |
| FKTYP | — | — | 0BILL_CAT | Fakturatyp |
| VBTYP | BEL_CD | Vertriebsbelegtyp==Beleg-Code VBRK-VBTYP | 0BIL_H_CNT | Anzahl der Fakturen |
| VBTYP | BEL_CD | Vertriebsbelegtyp==Beleg-Code VBRK-VBTYP | 0IMODOCCAT | Vertriebsbelegtyp |
| VBTYP | BEL_CD | Vertriebsbelegtyp==Beleg-Code VBRK-VBTYP | 0DEB_CRED | Credit/Debit Buchung (C/D) |
| WAERK | WAERK_FK | Waehrungsschluessel, Belegwaehrung VBRK-WAERK | 0DOC_CURRCY | Belegwährung |
| VKORG | VKORG | Verkaufsorganisation VBRK-VKORG | 0SALESORG | Verkaufsorganisation |
| VTWEG | VTWEG | Vertriebsweg VBRK-VTWEG | 0DISTR_CHAN | Vertriebsweg |
| KALSM | — | — | SD_KALSM | Kalk.Schema |
| KNUMV | — | — | SD_KNUMV | Belegkonditionsnummer |
| VSBED | VSBED_FK | Versandbedingung VBRK-VSBED | 0SHIP_COND | Versandbedingung |
| FKDAT | FAKTDAT | Fakturadatum (JJJJMMTT) VBRK-FKDAT | 0FISCPER | Geschäftsjahr / Periode |
| FKDAT | FAKTDAT | Fakturadatum (JJJJMMTT) VBRK-FKDAT | 0CALDAY | Kalendertag |
| FKDAT | FAKTDAT | Fakturadatum (JJJJMMTT) VBRK-FKDAT | SD_DAY | Kalendertag  (1-31) |
| FKDAT | FAKTDAT | Fakturadatum (JJJJMMTT) VBRK-FKDAT | SD_MONDAY | Kalendermonat / Tag |
| FKDAT | FAKTDAT | Fakturadatum (JJJJMMTT) VBRK-FKDAT | 0BILL_DATE | Datum für Faktura-/Rechnungsindex und Druck |
| KONDA | — | — | 0PRICE_GRP | Preisgruppe des Kunden |
| KDGRP | KDGRP_FK | Kundengruppe VBRK-KDGRP | 0CUST_GROUP | Kundengruppe |
| BZIRK | — | — | 0SALES_DIST | Kundenbezirk |
| PLTYP | — | — | 0PRICE_LIST | Preislistentyp |
| INCO1 | — | — | 0INCOTERMS | Incoterms Teil 1 |
| INCO2 | — | — | 0IMOINCOTM2 | Incoterms Teil 2 |
| RFBSK | — | — | SD_RFBSK | Status für die Überleitung an die Buchhaltung |
| MRNKZ | — | — | SD_MRNKZ | Rechnungsnachbearbeitung |
| KURRF | — | — | 0EXRATE_ACC | Währungskurs für FI-Buchungen |
| VALTG | — | — | SD_VALTG | zus. Valutatage |
| VALDT | — | — | SDRVALDT | Valutafixdatum |
| ZTERM | ZTERM_FK | Zahlungsbedingungsschluessel VBRK-ZTERM | 0PMNTTRMS | Zahlungsbedingungsschlüssel |
| KTGRD | — | — | 0ACCNT_ASGN | Kontierungsgruppe Debitor |
| LAND1 | — | — | 0COUNTRY | Länderschlüssel |
| REGIO | — | — | 0REGION | Region (Bundesstaat, Bundesland, Provinz, Grafschaft) |
| BUKRS | — | — | 0COMP_CODE | Buchungskreis |
| TAXK1 | — | — | SD_TAXK1 | Steuerkla-Kd |
| NETWR | NETWR_FK | Fakturakopfwert, vor Steuern, in Haus-Waehrung VBRK-NETWR Druckaufbereiteter | 0NET_VALUE | Nettowert der Auftragsposition in Belegwährung |
| ZUKRI | — | — | SD_ZUKRI | Zus.Kriterien |
| ERZET | — | — | 0CREA_TIME | Erfassungszeit |
| ERDAT | ERDAT_FK | Belegdatum (JJJJMMTT) Datum, an dem der Satz hinzugefuegt wurde VBRK-ERDAT | 0CREATEDON | Datum, an dem der Satz hinzugefügt wurde |
| STAFO | — | — | SD_STAFO | Fortschreibungsgruppe Statistik |
| KUNRG | KUNDNRG | Kundennr==Regulierer VBRK-KUNRG | 0PAYER | Regulierer |
| KUNAG | — | — | 0SOLD_TO | Auftraggeber |
| MABER | — | — | 0DUNN_AREA | Mahnbereich |
| STWAE | — | — | 0STAT_CURR | Statistikwährung |
| STCEG | — | — | 0VAT_REG_NO | Umsatzsteueridentifikationsnummer |
| AEDAT | AENDATFK | Datum der letzten Aenderung==Aenderungsdatum (JJJJMMTT) VBRK-AEDAT | — | — |
| SFAKN | — | — | SDRSFAKN | Nummer der stornierten Faktura |
| FKART_RL | — | — | SD_FKARTL | RechListArt |
| FKDAT_RL | — | — | SDRFKDTRL | Agenturgeschäft: Buchungsdatum für Vergütungsliste |
| KURST | — | — | 0RATE_TYPE | Kurstyp |
| MANSP | — | — | 0DUNN_BLOCK | Mahnsperre |
| SPART | SPARTE | Sparte VBRK-SPART | 0DIVISION | Sparte |
| KKBER | — | — | 0C_CTR_AREA | Kreditkontrollbereich |
| KNKLI | — | — | SDRKNKLI | Kontonummer des Debitoren mit der Kreditlimit-Vorgabe |
| BSTNK_VF | — | — | SD_BSTKD | Bestellnummer |
| VBUND | — | — | 0COMPANY | Gesellschaft |
| LANDTX | — | — | SDRLANDTX | Steuerliches Abgangsland |
| STCEG_H | — | — | SD_STCEGH | HerkunftUstNr |
| STCEG_L | — | — | SDRSTCEGL | LandUstNummer |
| XBLNR | — | — | 0REF_DOC_NO | Referenz-Belegnummer |
| ZUONR | — | — | 0ALLOC_NMBR | Zuordnungsnummer |
| MWSBK | — | — | 0TAX_VALUE | Steuerbetrag in Vertriebsbelegwährung |
| FKSTO | — | — | SD_FKSTO | Storniert |
| XEGDR | — | — | 0TRIANGULAR | Kennzeichen Dreiecksgeschäfte innerhalb der EU |
| RPLNR | — | — | 0FCIPL_NUMB | Ratenplan Nummer |
| EXPKZ | — | — | SD_EXPKZ | Exportkennzeichen Lieferung |
| EXNUM | — | — | SD_EXNUM | AH-Nummer |
| GBSTK | — | — | SDRGBSTK | Gesamtbearbeitungsstatus des Vertriebsbeleges |
| RELIK | — | — | SDRRELIK | ReliStatus |
| KUNWE | KUNDNWE | Kundennr==Warenempfaenger VBRK-KUNWE | — | — |
| ZZWMINR | WMINR_FK | Werbemittelnummer, Katalognummer, Preisliste VBRK-ZZWMINR | — | — |
| BSARK | BSARK_FK | Bestellart des Kunden VBRK-BSARK | SD_BSARK | Bestellart des Kunden |
| VKBUR | VKBUR_FK | Verkaufsbuero VBRK-VKBUR | 0SALES_OFF | Verkaufsbüro |
| VKGRP | VKGRP_FK | Verkaeufergruppe VBRK-VKGRP | 0SALES_GRP | Verkäufergruppe |
| BNAME | — | — | SD_BNAME | Name |
| SUBMI | — | — | SD_SUBMI | Submission |
| BSTZD | — | — | SD_BSTZD | Zusatz |
| ZZKATR5 | — | — | SD_KATR5 | Kundenklassifizierung |
| ZZKATR9 | — | — | SD_KATR9 | AD-Gebiet 2.0 |

### VBRP

| SAP-Feld | SAS/DWH-Feld | SAS/DWH-Bezeichnung | BW-Feld | BW-Bezeichnung |
|----------|--------------|---------------------|---------|----------------|
| VBELN | FAKTNUM | Vertriebsbelegnummer (Fakturanummer) VBRK-VBELN | 0BILL_NUM | Faktura |
| POSNR | FAKTPOS | Positionsnummer des Vertriebsbeleges VBRP-POSNR | 0BILL_ITEM | Fakturaposition |
| UEPOS | FAKTPOSH | uebergeordnete Fakturaposition bei Stuecklistenstrukturen VBRP-UEPOS | 0ROOTORDITM | Positionsnummer von Wurzelposition |
| FKIMG | MENGE | Fakturamenge VBRP-FKIMG | 0INV_QTY | Fakturamenge in Verkaufsmengeneinheiten |
| VRKME | — | — | 0SALES_UNIT | Verkaufsmengeneinheit |
| UMVKZ | — | — | 0NUMERATOR | Zaehler(Faktor) fuer Umrechnung Verkaufsmenge in LME |
| UMVKN | — | — | 0DENOMINTR | Nenner(Divisor) fuer Umrechnung Verkaufsmenge in LME |
| MEINS | — | — | 0QUANT_B | Menge in Basismengeneinheiten |
| MEINS | — | — | 0BASE_UOM | Basismengeneinheit |
| FKLMG | — | — | 0BILL_QTY | Fakturamenge in Basismengeneinheiten |
| FKLMG | — | — | 0QUANT_B | Menge in Basismengeneinheiten |
| LMENG | — | — | 0REQ_QTY | Bedarfsmenge für die Materialwirtschaft in LME |
| NTGEW | — | — | 0NET_WGT_DL | Nettogewicht |
| NTGEW | — | — | 0NT_WT_KG | Nettogewicht in Kilogramm |
| BRGEW | BRGEW | Bruttogewicht der Faktura-Position VBRP-BRGEW | 0GRS_WGT_DL | Bruttogewicht der Lieferposition |
| BRGEW | BRGEW | Bruttogewicht der Faktura-Position VBRP-BRGEW | 0GR_WT_KG | Bruttogewicht in Kilogramm |
| GEWEI | — | — | 0NT_WT_KG | Nettogewicht in Kilogramm |
| GEWEI | — | — | 0GR_WT_KG | Bruttogewicht in Kilogramm |
| GEWEI | — | — | 0UNIT_OF_WT | Gewichtseinheit |
| VOLUM | VOLUM | Volumen der Faktura-Position VBRP-VOLUM | 0VOLUME_DL | Liefervolumen |
| VOLUM | VOLUM | Volumen der Faktura-Position VBRP-VOLUM | 0VOLUME_CDM | Volumen in Kubikdezimeter |
| VOLEH | — | — | 0VOLUME_CDM | Volumen in Kubikdezimeter |
| VOLEH | — | — | 0VOLUMEUNIT | Volumeneinheit |
| GSBER | — | — | 0BUS_AREA | Geschäftsbereich |
| PRSDT | — | — | 0PRICE_DATE | Datum für Preisfindung und Währungskurs |
| FBUDA | — | — | 0SERV_DATE | Datum der Leistungserstellung |
| KURSK | — | — | 0EXCHG_RATE | Kurs für Preisfindung und Statistiken |
| NETWR | NETWR_FP | Nettopreis nach Konditionen, vor Steuer VBRP-NETWR | 0NETVAL_INV | Nettowert der Fakturaposition in Belegwährung |
| VBELV | — | — | 0VBELV | Originalbeleg |
| POSNV | — | — | 0POSNV | Ursprungsposition |
| VGBEL | VGBLNUM | Belegnummer des Vorgaengerbeleges (Lieferscheinnr od. Fakturanr) VBRP-VGBEL | 0REFER_DOC | Belegnummer des Vorlagebeleges |
| VGPOS | VGBLPOS | Positionsnummer der Vorgaengerposition (Auftragsposition) VBRP-VGPOS | 0REFER_ITM | Positionsnummer der Vorlage-Geschäftsposition |
| VGTYP | — | — | 0IMODOCCATP | Vorgängerbelegtyp |
| AUBEL | AUFTNUM | Verkaufsbeleg (Auftragsnummer) VBRP-AUBEL | 0DOC_NUMBER | Verkaufsbeleg |
| AUPOS | AUFTPOS | Verkaufsbelegposition (Auftragsposition) VBRP-AUPOS | 0S_ORD_ITEM | Verkaufsbelegposition |
| MATNR | ARTINUM | Materialnummer (Artikelnummer) VBRP-MATNR | 0MATERIAL | Material |
| ARKTX | ARTITXT | Kurztext der Kundenfakturaposition VBRP-ARKTX | SD_ARKTX | Kurztext Artikel |
| MATKL | WAGRU_FP | Warengruppe VBRP-MATKL | 0MATL_GROUP | Warengruppe |
| PSTYV | — | — | 0ITEM_CATEG | Positionstyp Vertriebsbeleg |
| POSAR | — | — | 0ITM_TYPE | Positionsart |
| PRODH | PRODH_FP | Produkthierarchie VBRP-PRODH | 0PROD_HIER | Produkthierarchie Beleg |
| VSTEL | VSTEL_FP | Versandstelle/Warenannahmestelle VBRP-VSTEL | 0SHIP_POINT | Versandstelle |
| SPART | SPARTE | Sparte VBRP-SPART | 0DIVISION | Sparte |
| WERKS | WERK_FP | Werk VBRP-WERKS | 0PLANT | Werk |
| ALAND | — | — | SDRALAND | Land |
| TAXM1 | — | — | SD_TAXM1 | Steuerklassifikation Material |
| KOWRR | — | — | SD_KOWRR | Werte statistisch |
| SKTOF | — | — | SD_SKTOF | Skontofähig |
| SKFBP | — | — | 0CSHDSC_BAS | Skontofähiger Betrag in Belegwährung |
| KONDM | — | — | SD_KONDM | Konditionsgruppe Material |
| KTGRM | — | — | SD_KTGRM | KontierGrp.Mat. |
| BONUS | — | — | 0REBATE_GRP | Bonusgruppe |
| PROVG | — | — | 0PROV_GROUP | Provisionsgruppe |
| VKGRP | VKGRP_FP | Verkaeufergruppe VBRP-VKGRP | 0SALES_GRP | Verkäufergruppe |
| VKBUR | VKBUR_FP | Verkaufsbuero VBRP-VKBUR | 0SALES_OFF | Verkaufsbüro |
| SPARA | — | — | 0DIV_HEAD | Sparte Auftragskopf |
| SHKZG | — | — | 0DB_CRD_IND | Retourenposition |
| ERDAT | — | — | 0CREATEDON | Datum, an dem der Satz hinzugefügt wurde |
| ERZET | — | — | 0TIME | Uhrzeit |
| LGORT | — | — | 0STOR_LOC | Lagerort |
| STAFO | — | — | SD_STAFO | Fortschreibungsgruppe Statistik |
| KZWI1 | — | — | 0SUBTOTAL_1 | Konditionszwischensumme 1 aus Kalkulationsschema |
| KZWI2 | — | — | 0SUBTOTAL_2 | Konditionszwischensumme 2 aus Kalkulationsschema |
| KZWI3 | — | — | 0SUBTOTAL_3 | Konditionszwischensumme 3 aus Kalkulationsschema |
| KZWI4 | — | — | 0SUBTOTAL_4 | Konditionszwischensumme 4 aus Kalkulationsschema |
| KZWI5 | — | — | 0SUBTOTAL_5 | Konditionszwischensumme 5 aus Kalkulationsschema |
| KZWI6 | — | — | 0SUBTOTAL_6 | Konditionszwischensumme 6 aus Kalkulationsschema |
| STCUR | — | — | 0EXCHG_STAT | Umrechnungskurs für Statistiken |
| EAN11 | — | — | 0EANUPC | Europäische Artikelnummer/Universal Product Code |
| KVGR1 | — | — | 0CUST_GRP1 | Kundengruppe 1 |
| KVGR2 | — | — | 0CUST_GRP2 | Kundengruppe 2 |
| KVGR3 | — | — | 0CUST_GRP3 | Kundengruppe 3 |
| KVGR4 | — | — | 0CUST_GRP4 | Kundengruppe 4 |
| KVGR5 | — | — | 0CUST_GRP5 | Kundengruppe 5 |
| MVGR1 | — | — | 0MATL_GRP_1 | Materialgruppe 1 |
| MVGR2 | — | — | 0MATL_GRP_2 | Materialgruppe 2 |
| MVGR3 | — | — | 0MATL_GRP_3 | Materialgruppe 3 |
| MVGR4 | — | — | 0MATL_GRP_4 | Materialgruppe 4 |
| MVGR5 | — | — | 0MATL_GRP_5 | Materialgruppe 5 |
| MATWA | — | — | 0MAT_ENTRD | Eingegebenes Material |
| KOKRS | — | — | 0CO_AREA | Kostenrechnungskreis |
| PAOBJNR | — | — | 0PROFTB_SEG | Nummer für Ergebnisobjekte (CO-PA) |
| CMPRE | — | — | SD_CMPRE | Kreditpreis |
| CMPNT | — | — | SD_CMPNT | aktive Forderung |
| ABRVW | RTGRU_FP | Retourengrund-Posi VBRP-ABRVW | SD_ABRVW | Verwendung |
| KDGRP_AUFT | — | — | SDRKDGRAU | KundenGrpAuft |
| LLAND_AUFT | — | — | SDRLLNDAU | EmpfLandAuft |
| PLTYP_AUFT | — | — | 0PRICE_LIST | Preislistentyp |
| REGIO_AUFT | — | — | SDRREGIOZ | Region Zielgebiet |
| VKORG_AUFT | — | — | SDRVKORAU | Verkaufsorganisation Kundenauftrag |
| VTWEG_AUFT | — | — | SDRVTWGAU | Vertriebsweg des Kundenauftrages |
| MWSBP | — | — | 0TAX_AMOUNT | Steuerbetrag in Belegwährung |
| AUGRU_AUFT | — | — | 0ORD_REASON | Auftragsgrund (Grund des Vorgangs) |
| FAREG | — | — | 0VOLUME_CDM | Volumen in Kubikdezimeter |
| FAREG | — | — | 0NT_WT_KG | Nettogewicht in Kilogramm |
| FAREG | — | — | 0GR_WT_KG | Bruttogewicht in Kilogramm |
| FAREG | — | — | 0QUANT_B | Menge in Basismengeneinheiten |
| FAREG | — | — | 0BIL_I_CNT | Anzahl der Fakturapositionen |
| BRTWR | — | — | 0GROSS_VAL | Bruttowert in Vertriebsbelegwährung |
| KURSK_DAT | — | — | 0TRANS_DATE | Umrechungsdatum |
| KDKG1 | — | — | SD_KDKG1 | KonditionsGrp 1 |
| VKAUS | VKAUS_FP | Verwendungskennzeichen VBRP-VKAUS | 0USAGE_IND | Verwendungskennzeichen des Materials |
| MWSKZ | — | — | 0IS_TXCOD | Umsatzsteuerkennzeichen |
| WMINR | WMINR_FP | Werbemittelnummer, Katalognummer, Preisliste VBRP-WMINR | SD_PRLI | Preislistenkennung |
| WAERK | — | — | 0DOC_CURRCY | Belegwährung |
| KDMAT | — | — | SD_KDMAT | Materialnummer des Kunden |

