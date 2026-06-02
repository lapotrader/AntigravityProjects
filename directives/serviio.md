# Serviio / Rete — Note

## Dispositivi in rete

| Dispositivo | IP | Nome PC |
|---|---|---|
| Questo PC | 192.168.1.10 | DESKTOP-TL38OLL |
| PC piano sotto | 192.168.1.5 | DESKTOP-56OHR3O |
| Notebook (Windows 11) | 192.168.1.15 | LAPTOP-TS6RMJGF |
| Router | 192.168.1.1 | — |

## Accesso Notebook (LAPTOP-TS6RMJGF)

- Utente: `tradin python` (password vuota)
- Per abilitare accesso senza password: `Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "LimitBlankPasswordUse" -Value 0`
- Condivisioni: `C:` (disco intero), `cherie` (cartella), stampante HP

## Accesso PC piano sotto (DESKTOP-56OHR3O)

- Utente locale, password non impostata
- Condivisioni: `Disco giu`, `Users` (solo Public accessibile)
- **Problema**: Windows blocca accesso rete con password vuota. Necessario:
  - `secpol.msc` → Account: Limita uso account locali con password vuota... → Disabilitato
  - Oppure impostare password sull'account

## Comandi utili

```powershell
# Condividere un disco
New-SmbShare -Name "C" -Path "C:\" -ChangeAccess Everyone

# Abilitare firewall per condivisione
Set-NetFirewallRule -DisplayGroup "Condivisione file e stampanti" -Enabled True -Profile Private

# Abilitare accesso senza password in rete
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "LimitBlankPasswordUse" -Value 0

# Verificare connessione
net view \\192.168.1.15
```
