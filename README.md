# VendutoRealTime 

Ora siamo alla versione 1.1 STABILE

COMPILARE IL FOGLIO GOOGLE PRIMA DI QUALUNQUE COSA, PERCHE' SI.
https://docs.google.com/spreadsheets/d/1j1DrHwa-U1DZaOuCpIPD5Rmj_Cx0439ynaySWLOOWlU/edit?usp=sharing

---

## Modalita' di funzionamento

Il demone supporta due modalita':

- **Modalita' MySQL diretto** (branch `main`): il demone legge le licenze e scrive i dati 
  direttamente sul database MySQL remoto. Usa `template_config.json` come riferimento.
  
- **Modalita' Endpoint REST** (branch `peppe-dev-v3`): il demone verifica le licenze e invia 
  i dati tramite endpoint REST, senza connessione diretta al DB remoto. 
  Usa `template_api_config.json` come riferimento.

---

## Fase Preliminare: preparare il file di configurazione

### Modalita' MySQL diretto (template_config.json)

1. Aprire PDVVRT
2. Creare una cartella con il nome di riferimento per i negozi oppure usarne una gia' presente
3. Creare un file di configurazione nel formato xxxx_config.json (es. 0001_config.json)
4. Seguire il file `template_config.json` per l'inserimento dei dati:
    - `applicazione.codice_negozio` — Codice del negozio
    - `applicazione.licenza` — UUID della licenza nel DB licenze
    - `applicazione.nome` — Nome del punto vendita
    - `licenze.database` — Credenziali DB licenze MySQL
    - `in.database` — Credenziali DB Uakari locale
    - `out.database` — Credenziali DB MySQL remoto (vrt_stats)

### Modalita' Endpoint REST (template_api_config.json)

1. Aprire PDVVRT
2. Creare una cartella con il nome di riferimento per i negozi oppure usarne una gia' presente
3. Creare un file di configurazione nel formato xxxx_config.json (es. 0001_config.json)
4. Seguire il file `template_api_config.json` per l'inserimento dei dati:
    - `applicazione.codice_negozio` — Codice del negozio (usato per la validazione BUFFER_INFO)
    - `applicazione.codice_negozio_licenza` — Codice negozio della licenza (usato per la ricerca della licenza nell'endpoint)
    - `applicazione.licenza` — UUID della licenza nel DB licenze
    - `applicazione.nome` — Nome del punto vendita
    - `applicazione.id_cliente` — ID cliente associato alla licenza
    - `applicazione.postazione` — Codice postazione (default "999")
    - `applicazione.codice_app` — Fisso "VRT2021"
    - `in.database` — Credenziali DB Uakari locale (se diverse dallo standard)

---

## Installazione sul PDV

### Modalita' MySQL diretto

1. Creare sul pc del punto vendita una cartella al path C:\sistemipos\
2. Trasferire le cartelle bin e PDVVRT in questa cartella
3. Trasferire git-portable.exe sotto C:\
4. Avviare git-portable.exe e modificare il path di installazione in C:\git
5. Aprire un terminale e incollare:
    ```
    cd C:\sistemipos
    C:\git\bin\git clone https://github.com/sistemiposdev/VRT-Demone.git VendutoRealTime
    ```
6. Al termine del clone spostare PDVVRT e BIN nella cartella C:\sistemipos\VendutoRealTime
7. Portarsi sotto C:\sistemipos\VendutoRealTime
8. Lanciare RunMe.bat da GUI
9. Quando compare la selezione del punto vendita seguire i numeri (la numerazione parte da 0)
10. Quando si chiude il batch il servizio e' gia' creato e pronto per essere avviato
11. Cancellare la cartella PDVVRT

### Modalita' Endpoint REST

Stessi passaggi della modalita' MySQL diretto, con una sola differenza al punto 5:
    ```
    cd C:\sistemipos
    C:\git\bin\git clone -b peppe-dev-v3 https://github.com/sistemiposdev/VRT-Demone.git VendutoRealTime
    ```
Il parametro `-b peppe-dev-v3` clona direttamente il branch con la modalita' endpoint.

---

## Log e diagnostica

- Log del demone: `C:\sistemipos\VendutoRealTime\Demone\demone.log`
- Log interno allo script: `C:\sistemipos\VendutoRealTime\bin\demone.log`
- Log del servizio: `C:\sistemipos\VendutoRealTime\Demone\servizio.log` e `servizio_err.log`

## Modifica del config.json

Il file `config.json` in `C:\sistemipos\VendutoRealTime\Demone` e' in versione criptata (base64).
Per modificarlo:

1. **Fermare il servizio** VendutoRealTime
2. Decriptare con il batch in `C:\sistemipos\VendutoRealTime\Demone\Assistenza\decripta_config.bat`
3. Modificare il file
4. Criptare nuovamente con `C:\sistemipos\VendutoRealTime\Demone\Assistenza\cripta_config.bat`
5. Riavviare il servizio