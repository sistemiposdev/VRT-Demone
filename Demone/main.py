
import sys
import os

sys.path.append(os.getcwd())
sys.path.append("C:\SistemiPos\VendutoRealTime\Demone")

import time
import logging
from config import configuration
from Licenza import verifica_licenza
from SyncRemoto import invia_dati
from API.API import API
from API.Model.Negozio import Negozio as ModelNegozio

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

logging.basicConfig(filename=os.path.join(SCRIPT_DIR, 'demone.log'),
                    level=logging.DEBUG, filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S')

versione_demone = "1.1 stabile"
if __name__ == "__main__":
    livello_max_fidelity = 10
    while True:
        logging.info("Chiamata di verifica licenza..")
        id_cliente = verifica_licenza()
        if not id_cliente:
            logging.error("Verifica licenza fallita. Arresto del servizio.")
            sys.exit(-1)
        logging.info("OK.")
            
        # Utilizzo Interfaccia API
        if configuration["applicazione"]["funzionamento"] == "API":
            from generatore_token import genera_token_automatico
            logging.info("Inizio comunicazione con API Uakari..")
            logging.info("Caricamento Api..")
            try:
                api = API(web=True, token_autenticazione=configuration["in"]["API"]
                            ["token_autorizzazione"], url_server=configuration["applicazione"]["server"])
            except Exception as ex:
                logging.exception(ex)
                sys.exit(-1)
            logging.info("Ok.")
            logging.info("Inizio controllo token di autenticazione uakari..")
            if not(api.check_connection()):
                logging.info(
                    "Autenticazione fallita..\n Creazione nuovo token..")
                genera_token_automatico()
                logging.info(
                    "al prossimo riavvio partira` l'esecuzione Normalmente.")
                sys.exit(0)

        # Utilizzo Interfaccia DB
        if configuration["applicazione"]["funzionamento"] == "DB":
            logging.info("Inizio comunicazione con Uakari..")
            try:
                api = API(database_connection_string=(
                    f"driver={{ODBC Driver 17 for SQL Server}};server={configuration['in']['database']['db_address']};uid={configuration['in']['database']['db_username']};pwd={configuration['in']['database']['db_password']};database={configuration['in']['database']['db_name']};"))
            except Exception as ex:
                logging.exception(ex)
                sys.exit(1)
            logging.info("Ok.")
            logging.info("Controllo connessione con database Uakari..")
            if not(api.check_connection()):
                raise Exception("Connessione non disponibile")
            logging.info("Ok.")

        logging.info("Caricamento modello Negozio..")
        try:
            local_negozio = ModelNegozio(id_negozio=configuration["applicazione"]["codice_negozio"],
                                            nome_negozio=configuration["applicazione"]["nome"],
                                            id_cliente=id_cliente
                                            )
        except Exception as ex:
            logging.exception(ex)
            sys.exit(1)
        logging.info("Ok.")

        logging.info("Chiamata a Uakari, ritorno configurazione casse..")
        try:
            local_negozio = api.get_pos(local_negozio)
        except Exception as ex:
            logging.exception(ex)
        logging.info("Ok.")

        logging.info("Chiamata a Uakari, ritorno scontrini per casse..")
        try:
            local_negozio = api.get_valorizzazione_casse(negozio=local_negozio)
        except Exception as ex:
            logging.exception(ex)
        logging.info("Ok.")
        
        logging.info("Invio dati al server remoto..")
        try:
            risultato = invia_dati(local_negozio, versione_demone, livello_max_fidelity)
            if risultato is not None:
                livello_max_fidelity = risultato
            else:
                logging.error("Errore durante l'invio dei dati al server remoto.")
        except Exception as ex:
            logging.exception(ex)
        logging.info("Ok.")

        time.sleep(180)