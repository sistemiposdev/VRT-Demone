import requests
import logging
import uuid
from datetime import datetime
from config import configuration


def invia_dati(negozio, versione_demone, livello_max_fidelity=10):
    endpoint = configuration["out"]["endpoint"]

    # Filtro anomalie fidelity prima dell'invio
    for cassa in negozio.casse:
        anomalie_filtrate = []
        for anomalia in cassa.anomalie:
            if anomalia.tipo_anomalia.value == "Fidelity":
                nr_carta = anomalia.descrizione_anomalia.split(";")[0]
                threshold_anomalia = int(anomalia.descrizione_anomalia.split(";")[1])
                if threshold_anomalia <= livello_max_fidelity:
                    continue
                anomalia.descrizione_anomalia = (
                    f"La card fidelity Nr. {nr_carta} e` stata scansionata in cassa "
                    f"per {threshold_anomalia} volte, eccedendo il limite massimo giornaliero."
                )
            anomalie_filtrate.append(anomalia)
        cassa.anomalie = anomalie_filtrate

    # Costruzione payload JSON
    payload = {
        "id_negozio": negozio.id_negozio,
        "id_cliente": negozio.id_cliente,
        "nome_negozio": negozio.nome_negozio,
        "versione_demone": versione_demone,
        "casse": []
    }

    for cassa in negozio.casse:
        cassa_data = {
            "id_cassa": cassa.id_cassa,
            "numero_scontrini": cassa.numero_scontrini,
            "numero_scontrini_fidelity": cassa.numero_scontrini_fidelity,
            "totale": cassa.totale,
            "reparti": [
                {
                    "id_reparto": reparto.codice,
                    "nome": reparto.nome,
                    "incasso": reparto.incasso,
                    "presenza": reparto.presenza
                }
                for reparto in cassa.incasso_per_reparto
            ],
            "pagamenti": [
                {
                    "tipo_pagamento": pagamento.tipo_pagamento,
                    "incasso": pagamento.incasso
                }
                for pagamento in cassa.incasso_per_tipo_pagamento
            ],
            "anomalie": [
                {
                    "id_anomalia": str(uuid.uuid4()),
                    "tipo_anomalia": anomalia.tipo_anomalia.value,
                    "ora_anomalia": str(anomalia.ora_anomalia) if anomalia.ora_anomalia else None,
                    "operatore": anomalia.operatore,
                    "descrizione_anomalia": anomalia.descrizione_anomalia
                }
                for anomalia in cassa.anomalie
            ]
        }
        payload["casse"].append(cassa_data)

    try:
        response = requests.post(endpoint, json=payload, timeout=60)
        response.raise_for_status()
    except requests.RequestException as ex:
        logging.error("Errore nella chiamata all'endpoint sync: %s", ex)
        return None

    result = response.json()
    if result.get("status") != "ok":
        logging.error("Il server ha restituito un errore: %s", result.get("message", "sconosciuto"))
        return None

    logging.info("Dati inviati con successo al server remoto.")
    return result.get("livello_max_fidelity", livello_max_fidelity)
