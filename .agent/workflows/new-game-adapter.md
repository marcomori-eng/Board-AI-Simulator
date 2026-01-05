---
description: Adatta il simulatore a un nuovo gioco partendo dalle regole testuali
---

# Workflow: New Game Adapter

Questo workflow converte le regole di un nuovo gioco inserite in `regole.md` in una simulazione funzionante.

## 1. Traduzione Regole (Text -> YAML)

L'agente deve leggere il file di testo e convertirlo in formato macchina standard.

1.  Leggi il file `regole.md` per comprendere le meccaniche.
2.  Leggi lo schema ` .agent/schema/game-rules-schema.yaml` per la validazione.
3.  Genera/Aggiorna il file `regole.yaml` mappando il testo sullo schema.
    *   Assicurati di definire correttamente `deck`, `points`, `trump_rules` e `victory_conditions`.

## 2. Adattamento Engine (YAML -> Dynamic Runtime)

Una volta generato il YAML, non è necessario scrivere codice Python specifico. Il `DynamicGameEngine` si adatta automaticamente.

1.  Verifica che `regole.yaml` sia valido.
2.  Esegui una simulazione di prova (10 partite) per verificare che le regole siano interpretate correttamente:
    ```bash
    python run_dynamic.py --rules regole.yaml --n 10 --verbose
    ```
3.  Se ci sono errori runtime, correggi `regole.yaml` (spesso errori nei nomi dei semi o valori).

## 3. Esecuzione Simulazione Massiva

Quando il test passa:

1.  Esegui la simulazione completa per raccogliere dati:
    ```bash
    python run_dynamic.py --rules regole.yaml --p1 expert --p2 random --n 1000
    ```

## Esempio di utilizzo:

Se l'utente dice "Ho messo le regole di Tressette in regole.md", l'agente deve:

1.  `view_file rules.md`
2.  Tradurre e scrivere `regole.yaml`
3.  Lanciare `python run_dynamic.py`
