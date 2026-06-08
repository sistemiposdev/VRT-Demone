import requests
import logging
from datetime import datetime, timedelta
from config import configuration

_cache_id_cliente = None
_cache_timestamp = None
INTERVALLO_VERIFICA = timedelta(hours=6)


def verifica_licenza():
    global _cache_id_cliente, _cache_timestamp

    if _cache_timestamp and _cache_id_cliente:
        if datetime.now() - _cache_timestamp < INTERVALLO_VERIFICA:
            logging.info("Verifica licenza: uso cache (ultima verifica: %s)", _cache_timestamp)
            return _cache_id_cliente

    logging.info("Verifica licenza tramite endpoint...")

    endpoint = configuration["licenze"]["endpoint"]
    payload = {
        "codiceApp": configuration["applicazione"]["codice_app"],
        "idCliente": configuration["applicazione"]["id_cliente"],
        "codiceNegozio": configuration["applicazione"]["codice_negozio"],
        "postazione": configuration["applicazione"]["postazione"]
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
    except requests.RequestException as ex:
        logging.error("Errore nella chiamata all'endpoint licenze: %s", ex)
        return None

    licenze = response.json()
    id_licenza_config = configuration["applicazione"]["licenza"]

    licenza = None
    for item in licenze:
        if item.get("ID_LICENZA") == id_licenza_config:
            licenza = item
            break

    if not licenza:
        logging.error("Licenza non trovata (ID_LICENZA: %s)", id_licenza_config)
        return None

    data_fine = datetime.strptime(licenza["DATA_FINE_LICENZA"], "%a, %d %b %Y %H:%M:%S %Z")
    if data_fine < datetime.now():
        logging.error("Licenza presente ma scaduta (scadenza: %s)", data_fine.strftime("%d/%m/%Y"))
        return None

    codice_negozio = configuration["applicazione"]["codice_negozio"]
    negozi_abilitati = [n.strip() for n in licenza.get("BUFFER_INFO", "").split(";") if n.strip()]
    if codice_negozio not in negozi_abilitati:
        logging.error("Il negozio %s non è abilitato per questa licenza (negozi abilitati: %s)", codice_negozio, ", ".join(negozi_abilitati))
        return None

    _cache_id_cliente = licenza["ID_CLIENTE"]
    _cache_timestamp = datetime.now()

    logging.info("Licenza valida - Cliente: %s, Negozio: %s", _cache_id_cliente, codice_negozio)
    return _cache_id_cliente
