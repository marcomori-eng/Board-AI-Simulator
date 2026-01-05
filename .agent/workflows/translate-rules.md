---
description: Traduzione regole gioco da Markdown/testo a formato YAML standard
---

# Workflow: Traduzione Regole Gioco

Questo workflow guida l'agente nella traduzione delle regole di un gioco da tavolo/carte dal formato testuale (Markdown) al formato YAML standardizzato.

## Pre-requisiti

1. Leggere lo schema di riferimento: `.agent/schema/game-rules-schema.yaml`
2. Avere accesso al file sorgente delle regole (es. `regole.md`)

## Passi di Traduzione

### 1. Analisi del Documento Sorgente

- Leggere completamente il file delle regole
- Identificare le sezioni principali:
  - Nome e tipo del gioco
  - Numero di giocatori
  - Componenti (carte, dadi, pedine, ecc.)
  - Preparazione/Setup
  - Fasi di gioco
  - Regole per vincere/perdere
  - Varianti
  - Strategia
  - Glossario/Terminologia

### 2. Mappatura delle Sezioni

Mappare ogni sezione trovata alla struttura YAML standard:

| Contenuto Trovato | Sezione YAML |
|-------------------|--------------|
| Nome gioco, tipo, origine | `game` |
| Numero giocatori, squadre | `players` |
| Durata partita | `duration` |
| Carte, dadi, tabellone, pedine | `components` |
| Preparazione, distribuzione | `setup` |
| Turni, fasi, azioni | `gameplay` |
| Fine partita | `end_game` |
| Come vincere | `victory_conditions` |
| Modalità alternative | `variants` |
| Consigli, tattiche | `strategy` |
| Termini specifici | `glossary` |

### 3. Generazione YAML

Per ogni sezione, seguire lo schema di riferimento:

#### 3.1 Sezione `game`
```yaml
game:
  name: "[Nome esatto del gioco]"
  type: "[card_game|board_game|dice_game|mixed]"
  origin: "[Paese di origine se noto]"
  version: "1.0"
  language: "[codice lingua: it, en, ecc.]"
```

#### 3.2 Sezione `players`
```yaml
players:
  min: [numero minimo]
  max: [numero massimo]
  recommended: [lista numeri consigliati]
  team_play: [true|false]
```

#### 3.3 Sezione `components`
Identificare tutti i componenti fisici e digitalizzarli con:
- Nome
- Quantità
- Proprietà specifiche (punti, valori, ecc.)

#### 3.4 Sezione `setup`
Convertire ogni passo di preparazione in:
```yaml
setup:
  steps:
    - order: [numero progressivo]
      action: "[azione_snake_case]"
      description: "[Descrizione leggibile]"
```

#### 3.5 Sezione `gameplay`
Strutturare le fasi di gioco con:
- ID fase
- Nome fase
- Steps ordinati
- Regole specifiche
- Condizioni

#### 3.6 Sezione `victory_conditions`
Definire chiaramente:
- Tipo di vittoria (punti, obiettivo, eliminazione)
- Soglie numeriche se applicabili
- Gestione pareggi

### 4. Validazione

Dopo la generazione, verificare:

- [ ] Tutti i campi obbligatori sono presenti
- [ ] I valori numerici sono corretti (punti totali, numero carte, ecc.)
- [ ] Le regole sono complete e non ambigue
- [ ] Il glossario copre tutti i termini specifici
- [ ] La struttura YAML è valida (indentazione, sintassi)

### 5. Output

Salvare il file come `[nome-gioco].rules.yaml` nella stessa directory del sorgente.

## Note Importanti

- **Non inventare**: Se un'informazione non è presente nel sorgente, omettere il campo o usare valori null
- **Preservare la semantica**: La traduzione deve mantenere esattamente il significato originale
- **Commenti esplicativi**: Aggiungere commenti YAML (`#`) per sezioni complesse
- **Consistenza**: Usare sempre snake_case per gli ID e le azioni

## Esempio di Invocazione

```
Traduci il file regole.md nel formato YAML standard seguendo il workflow translate-rules
```
