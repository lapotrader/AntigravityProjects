# Serviio — Note

## Configurazione di Rete

- **Questo PC**: 192.168.1.x (PC attuale)
- **Altro PC**: DESKTOP-56OHR3O @ 192.168.1.5 (piano sotto)
- **Router**: 192.168.1.1

## Accesso all'altro PC

- `\\192.168.1.5` o `\\DESKTOP-56OHR3O`
- Ha un account **locale** (nessuna password impostata)
- Windows blocca accesso via rete a utenti senza password
- **Soluzione**: andare sul PC remoto e impostare una password per l'utente locale

## Cartelle Condivise

- Questo PC: solo condivisioni admin di default (C$, ADMIN$, IPC$)
- Altro PC: nessuna condivisione visibile senza autenticazione

## Passi per far funzionare Serviio

1. Impostare password sull'account locale del PC remoto
2. Condividere cartelle multimediali sul PC remoto (tasto dx → Proprietà → Condivisione)
3. Configurare Serviio per puntare alle cartelle condivise
4. Verificare che il firewall permetta traffico Serviio (porta 23424/tcp, 1900/udp UPnP)
5. Verificare individuazione rete attiva su entrambi i PC
