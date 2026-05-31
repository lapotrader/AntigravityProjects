# OpenCode Portable su USB

Creata chiavetta USB portatile con OpenCode v1.15.11 su `E:\OPENCODE\`.

## Struttura

```
E:\OPENCODE\
├── opencode.bat                    ← Lancia il CLI (doppio click)
├── opencode.ps1                    ← Lancia il CLI (PowerShell)
├── opencode-desktop-win-x64.exe    ← App desktop standalone
├── README.txt                      ← Istruzioni
├── bin\
│   └── opencode.exe                ← Binary CLI v1.15.11
├── config\
│   ├── opencode.jsonc              ← Config (identica a ~/.config/opencode/opencode.jsonc)
│   ├── skills\
│   │   ├── graphify\               ← Skill graphify (da ~/.claude/skills/graphify/)
│   │   └── microsoft-foundry\      ← Skill Microsoft Foundry (da ~/.agents/skills/microsoft-foundry/)
│   ├── agents\                     ← Agenti personalizzati (vuoto, pronto all'uso)
│   ├── commands\                   ← Comandi personalizzati (vuoto)
│   ├── plugins\                    ← Plugin (vuoto)
│   ├── themes\                     ← Temi (vuoto)
│   └── tools\                      ← Strumenti (vuoto)
└── data\
    └── opencode.db                 ← DB auth + sessioni (da ~/.local/share/opencode/opencode.db)
```

## Come funziona

- `opencode.bat` imposta `OPENCODE_CONFIG_DIR` e `OPENCODE_CONFIG` per puntare a `E:\OPENCODE\config\`
- Il binary è standalone (scarica l'exe da GitHub Releases), senza bisogno di npm/choco/install
- Skills e agenti nella cartella `config/` vengono riconosciuti automaticamente da opencode

## Come aggiornare il binary

Scaricare l'ultima release da https://github.com/anomalyco/opencode/releases/latest e sostituire:
- `bin\opencode.exe` (CLI)
- `opencode-desktop-win-x64.exe` (Desktop)

## Note

- Il DB `opencode.db` contiene auth tokens e cronologia sessioni di questo PC (~385 MB)
- Su un altro PC, se il DB non viene riconosciuto, fare `/connect` per le API keys
- In alternativa, cancellare `data\opencode.db` e riconnettere le API keys su ogni PC
