from datetime import datetime
from Model.Negozio import Negozio
from Model.Cassa import Cassa
from Model.Reparto import Reparto
from Model.Pagamento import Pagamento
from Model.Anomalia import Anomalia, CodiceAnomalia, TipoAnomalia
import requests
import hashlib
import logging
import pyodbc
import pandas as pd

class API:

    def __init__(self, web:bool = False, **kwargs):
        """
        Costruttore API

        Parameters
        ----------

        web (bool)
            Definisce la modalita di interfacciamento con i dati uakari:
                True: Interfacciamento via API Uakari
                False: Interfacciamento via Database Uakari
        
        kwargs:
            web == False -> len(kwargs) == 1
                Dati di accesso presi dal file di configurazione
                
                `database_connection_string`
                    Connection string per database uakari.
                    
            web == True -> len(kwargs) == 2
                'token_autenticazione'
                    Token di autenticazione per servizi web di uakari, 

                'url_server'
                    Url delle Api Uakari
        """
        logging.info("Controllo dati..")
        logging.info(f"Interfacciamento attraverso {'Database' if not web else 'Web API'}")
        self.web = web
        if self.web:
            self.cookies = {
                'UakariWebSolution': kwargs['token_autenticazione']
            }
            
        self.server = kwargs['url_server'] if self.web else kwargs['database_connection_string']                     
        self.request_time = str(datetime(year=datetime.now().year,month=datetime.now().month,day=datetime.now().day))
        
    def check_connection(self) -> bool:
        """
        Controlla la connessione con l' API

        Returns
        -------
        True la connessione funziona, False altrimenti
        """
        return self._check_connection_WEB() if self.web else self._check_connection_DB()

    def get_pos(self, negozio: Negozio) -> Negozio:
        """
        Richiede la configurazione delle casse associate al punto vendita

        Parameters
        ----------
        negozio
            Negozio della quale si vuole la configurazione delle casse

        Returns
        -------
        Ritorna il negozio passato in input con le casse inizializzate
        """
        return self._get_pos_WEB(negozio) if self.web else self._get_pos_DB(negozio)
    
    
    def get_valorizzazione_casse(self, negozio: Negozio) -> Negozio:
        return self._get_valorizzazione_casse_DB(negozio)
    
    ############################################################################
    # Metodi nascosti per interfacciamento con Database Uakari
    def _check_connection_DB(self) -> bool:
        """
        Controlla la connessione con il DB

        Returns
        -------
        True la connessione funziona, False altrimenti
        """
        try:
            test = pyodbc.connect(self.server)
        except Exception as ex:
            return False
        test.close()
        return True
    
    def _get_pos_DB(self, negozio: Negozio) -> Negozio:
        """
        Richiede la configurazione delle casse associate al punto vendita

        Parameters
        ----------
        negozio
            Negozio della quale si vuole la configurazione delle casse

        Returns
        -------
        Ritorna il negozio con le casse inizializzate
        """
        conn = pyodbc.connect(self.server)
        cursor = conn.cursor()
        cursor.execute(f"SELECT ven_npo as id_cassa FROM vendite_stor where ven_dsc = 'TOTALE' and ven_dat = {{ts '{self.request_time}'}} GROUP BY ven_npo")
        negozio.casse = [Cassa(id_cassa=row[0]) for row in cursor]
        cursor.close()
        conn.close
        return negozio
    
    def _get_valorizzazione_casse_DB(self, negozio: Negozio) -> Negozio:
        """
        Funzione che valorizza tutte le informazioni per le casse di un punto vendita

        Parameters
        ----------

        negozio
            Negozio della quale si vuole valorizzare le informazioni delle casse.

        data
            Datetime del giorno della quale ricevere le informazioni.

            _Example: '2021-06-09'_

        Returns
        -------
            Ritorna il negozio che ho passato come parametro con i valori delle casse valorizzato
        """
        for cassa in negozio.casse:
            # Calcoli scontrini
            results = self._execute_query_DB(f"SELECT count(*) as scontrini FROM vendite_stor where ven_dsc = 'TOTALE' and ven_npo='{cassa.id_cassa}'  and ven_dat = {{ts '{self.request_time} '}}")
            cassa.numero_scontrini = results[0][0]
            
            results = self._execute_query_DB(f"SELECT count(*) as scontrini FROM vendite_stor where ven_dsc = 'TOTALE' and ven_npo='{cassa.id_cassa}'  and ven_dat = {{ts '{self.request_time} '}} and LEN(ven_card) > 1 ")
            cassa.numero_scontrini_fidelity = results[0][0]
            
            # Calcoli per reparto
            results = self._execute_query_DB("select rep_cod, rep_dsa  from reparti")
            reparti = {row[0]:row[1] for row in results}
            cassa.incasso_per_reparto = []
            cassa.anomalie = []
            for cod, desc in reparti.items():
                
                result = self._execute_query_DB(f"select SUM(ven_tot), COUNT(DISTINCT ven_nsc) from vendite_stor where ven_sgn= '-' and ven_npo='{cassa.id_cassa}' and ven_sta in('V','R','S') and ven_dat = {{ts '{self.request_time} '}} and ven_rep = '{cod.strip()}' ")
                reparto_neg, presenze_neg = result[0][0], result[0][1]

                result = self._execute_query_DB(f"select SUM(ven_tot), COUNT(DISTINCT ven_nsc) from vendite_stor where ven_sgn= '+' and ven_npo='{cassa.id_cassa}' and ven_sta in('V','R','S') and ven_dat = {{ts '{self.request_time} '}} and ven_rep = '{cod.strip()}' ")
                reparto_pos, presenze_pos = result[0][0], result[0][1]
                
                if presenze_pos == 0: continue
                try:
                    cassa.incasso_per_reparto.append(
                                                    Reparto(nome=desc.strip(),
                                                         codice=cod.strip(),
                                                         incasso=float(reparto_pos)-float(reparto_neg if reparto_neg is not None else 0),
                                                         presenza=int(presenze_pos)-int(presenze_neg if presenze_neg is not None else 0)
                                                        )
                                                )
                except Exception as ex:
                    continue

            # Calcoli per tender pagamento
            results = self._execute_query_DB("select par_cod, par_des from parametri where par_cod LIKE '%TEN%'")
            tender = {row[0]:row[1] for row in results}
            cassa.incasso_per_tipo_pagamento = []
            for cod, desc in tender.items():
                try:
                    results = self._execute_query_DB(f"select SUM(ven_tot), count(*) from vendite_stor where ven_sgn= '+' and ven_npo='{cassa.id_cassa}'  and ven_dat = {{ts '{self.request_time} '}} and ven_cda = '{cod.strip()}'")
                    tender_pos_incasso, tender_pos_presenze = results[0][0],results[0][1]
                    
                    results = self._execute_query_DB(f"select SUM(ven_tot), count(*) from vendite_stor where ven_sgn= '-' and ven_npo='{cassa.id_cassa}'  and ven_dat = {{ts '{self.request_time} '}} and ven_cda = '{cod.strip()}'")
                    tender_neg_incasso, tender_neg_presenze = results[0][0] if results[0][0] is not None else 0,results[0][1]
                    
                    if tender_pos_presenze == 0: continue
                    
                    cassa.incasso_per_tipo_pagamento.append(Pagamento(tipo_pagamento=desc.strip(),
                                                            incasso=float(tender_pos_incasso) - float(tender_neg_incasso)))
                except Exception as ex:
                    continue
                
            # Calcoli anomalie 
            
            # Fidelity
            anomalie_fidelity = []
            results = self._execute_query_DB(f"SELECT count (*) as cnt , LTRIM(RTRIM(VEN_CARD)) AS FID FROM vendite_stor where ven_dat = {{ts '{self.request_time} '}} and ven_dsc = 'TOTALE' and LTRIM(RTRIM(VEN_CARD)) <> '' GROUP BY ven_card HAVING count(*) > 1 ")
            fidelity = {row[1]:row[0] for row in results}
            try:
                for fidelity, nr_volte_in_cassa in fidelity.items():
                    anomalie_fidelity.append(
                        Anomalia(
                            tipo_anomalia=CodiceAnomalia.Fidelity,
                            ora_anomalia=None, 
                            operatore="",
                            descrizione_anomalia = TipoAnomalia.FidelityLimite(fidelity,nr_volte_in_cassa)
                        )
                    )
            except:
                print("Errore durante analisi fidelity")
            
            # Abort
            anomalie_abort = []
            results = self._execute_query_DB(f"""
                                                Select SUM(ven_tot) As TOT, LTRIM(RTRIM(ope_des)) As OPERATORE,VEN_TIM As ORA,VEN_NPO As CASSA,VEN_NSC As SCONTRINO 
                                                FROM vendite_stor inner join operatori on (ven_ope = operatori.ope_cpd)
                                                where ven_sta In ('Z') and ven_sgn = '-' and ven_dat =  {{ts '{self.request_time}'}} and ven_npo='{cassa.id_cassa}' 
                                                GROUP BY LTRIM(RTRIM(ope_des)),VEN_NPO,VEN_NSC,VEN_TIM
                                            """)
            try:
                for row in results:
                    anomalie_abort.append(
                        Anomalia(
                            tipo_anomalia=CodiceAnomalia.Abort,
                            ora_anomalia=row[2], 
                            operatore=row[1],
                            descrizione_anomalia = TipoAnomalia.Abort(ora_anomalia=row[2],operatore=row[1],nr_scontrino=row[4],totale=row[0])
                        )
                    )
            except:
                print("Errore durante analisi abort")
            # Storno
            anomalie_storno = []
            results = self._execute_query_DB(f"""
                                                SELECT
                                                    RTRIM(LTRIM(VEN_DSC)) AS DESCRIZIONE,
                                                    RTRIM(LTRIM(ope_des)) AS operatore,
                                                    VEN_tim AS ora,
                                                    RTRIM(LTRIM(VEN_EAN)) AS EAN,
                                                    VEN_TOT AS TOT
                                                FROM
                                                    vendite_stor inner join operatori on (ven_ope = ope_cpd)
                                                where
                                                    ven_sta IN ('A')
                                                    and ven_sgn = '-'
                                                    and ven_dat = {{ts '{self.request_time}'}}
                                                    and ven_npo='{cassa.id_cassa}' 
                                                GROUP BY
                                                    ope_des,
                                                    VEN_npo,
                                                    VEN_tim,
                                                    ven_TOT,
                                                    VEN_EAN,
                                                    VEN_DSC
                                            """)
            try:
                for row in results:
                    anomalie_storno.append(
                        Anomalia(
                            tipo_anomalia=CodiceAnomalia.Storno,
                            ora_anomalia=row[2], 
                            operatore=row[1],
                            descrizione_anomalia = TipoAnomalia.Storno(ora_anomalia=row[2],operatore=row[1],descrizione=row[0],ean=row[3], valore=row[4])
                        )
                    )
            except:
                print("Errore durante analisi storni")
            
            # Reso
            anomalie_reso = []
            results = self._execute_query_DB(f"""
                                                SELECT
                                                    VEN_NSC As SCONTRINO,
                                                    RTRIM(LTRIM(VEN_DSC)) AS DESCRIZIONE,
                                                    RTRIM(LTRIM(ope_des)) AS operatore,
                                                    VEN_tim AS ora,
                                                    RTRIM(LTRIM(VEN_EAN)) AS EAN,
                                                    VEN_TOT AS TOT
                                                FROM
                                                    vendite_stor inner join operatori on (ven_ope = ope_cpd)
                                                where
                                                    vendite_stor.ven_sta = 'V' 
                                                    and vendite_stor.ven_cau = 2
                                                    and ven_sgn = '-'
                                                    and ven_dat = {{ts '{self.request_time}'}}
                                                    and ven_npo='{cassa.id_cassa}' 
                                                GROUP BY
                                                    ope_des,
                                                    VEN_npo,
                                                    Ven_nsc,
                                                    VEN_tim,
                                                    ven_TOT,
                                                    VEN_EAN,
                                                    VEN_DSC
                                            """)
            try:
                for row in results:
                    anomalie_reso.append(
                        Anomalia(
                            tipo_anomalia=CodiceAnomalia.Reso,
                            ora_anomalia=row[3], 
                            operatore=row[2],
                            descrizione_anomalia = TipoAnomalia.ResoScontrino(scontrino=row[0],ora_anomalia=row[3],operatore=row[2],descrizione=row[1],ean=row[4], valore=row[5])
                        )
                    )
            except:
                print("Errore durante analisi reso")
            
            # Reso da scontrino
            anomalie_reso_scontrino = []
            results = self._execute_query_DB(f"""
                                                SELECT
                                                    VEN_NSC As SCONTRINO,
                                                    RTRIM(LTRIM(VEN_DSC)) AS DESCRIZIONE,
                                                    RTRIM(LTRIM(ope_des)) AS operatore,
                                                    VEN_tim AS ora,
                                                    RTRIM(LTRIM(VEN_EAN)) AS EAN,
                                                    VEN_TOT AS TOT
                                                FROM
                                                    vendite_stor inner join operatori on (ven_ope = ope_cpd)
                                                where
                                                    vendite_stor.ven_sta = 'V' 
                                                    and vendite_stor.ven_cau = 20
                                                    and ven_sgn = '-'
                                                    and ven_dat = {{ts '{self.request_time}'}}
                                                    and ven_npo='{cassa.id_cassa}' 
                                                GROUP BY
                                                    ope_des,
                                                    VEN_npo,
                                                    Ven_nsc,
                                                    VEN_tim,
                                                    ven_TOT,
                                                    VEN_EAN,
                                                    VEN_DSC
                                            """)
            try:
                for row in results:
                    anomalie_reso_scontrino.append(
                        Anomalia(
                            tipo_anomalia=CodiceAnomalia.ResoScontrino,
                            ora_anomalia=row[3], 
                            operatore=row[2],
                            descrizione_anomalia = TipoAnomalia.ResoScontrino(scontrino=row[0],ora_anomalia=row[3],operatore=row[2],descrizione=row[1],ean=row[4], valore=row[5])
                        )
                    )
            except:
                print("Errore durante analisi resi da scontrino")
            cassa.anomalie = anomalie_abort + anomalie_storno + anomalie_reso + anomalie_reso_scontrino
            cassa.totale = sum(reparto.incasso for reparto in cassa.incasso_per_reparto)
            
        # Dato che le anomalie sono cassa invariante, mi prendo il generato dall'ultima iterazione
        negozio.casse[-1].anomalie += anomalie_fidelity 
        return negozio
        

    def _execute_query_DB(self,  query: str):
        """ Esegue una query sul database indicato in fase di costruzione dell'api

        Args:
            query (str): 
                Query da effettuare verso il database

        Returns:
            _type_: 
                Risultato della query
        """
        connection = pyodbc.connect(self.server)
        cursor = connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        return results
    
    
    ############################################################################
    # Metodi nascosti per interfacciamento con API WEB v.1.1.7.3
    def _check_connection_WEB(self) -> bool:
        """
        Controlla la connessione con l' API Web

        Returns
        -------
        True la connessione funziona, False altrimenti
        """
        response = requests.post("http://localhost:50550/API/Sold/GetReceipts",
                                    cookies= self.cookies,
                                    data= {
                                        'CodeShop': '0001',
                                        'PosCode': '00001',
                                        'Date': datetime.now().strftime("%Y-%m-%d")
                                    }
                                 )
        if response.status_code == 200:
            return True
        return False


    def _get_pos_WEB(self, negozio: Negozio) -> Negozio:
        """
        Richiede la configurazione delle casse associate al punto vendita

        Parameters
        ----------
        negozio
            Negozio della quale si vuole la configurazione delle casse

        Returns
        -------
        Ritorna il negozio con le casse inizializzate
        """
        # data = requests.get(
        #     url=f'http://25.80.54.156:50550/API/Shops/GetPosConfiguration',
        #     cookies=self.cookies,
        #     timeout=30
        #
        # dati_negozio = list(filter(lambda _negozio: _negozio['ShopCode'] == negozio.id_negozio, data.json()['Data']))
        # negozio.casse = [Cassa(id_cassa=cassa['Code']) for cassa in dati_negozio[0]['Pos']]
        negozio.casse = [Cassa(id_cassa=codice_cassa) for codice_cassa in ['00001','00002']]
        return negozio

    def _get_valorizzazione_casse_WEB(self, negozio: Negozio, data: datetime) -> Negozio:
        """
        Funzione che valorizza tutte le informazioni per le casse di un punto vendita

        Parameters
        ----------

        negozio
            Negozio della quale si vuole valorizzare le informazioni delle casse.

        data
            Datetime del giorno della quale ricevere le informazioni.

            _Example: '2021-06-09'_

        Returns
        -------
            Ritorna il negozio che ho passato come parametro con i valori delle casse valorizzato
        """
        for cassa in negozio.casse:
            response_data = requests.post(
                url='http://localhost:50550/API/Sold/GetReceipts',
                cookies=self.cookies,
                data={
                    'CodeShop': negozio.id_negozio,
                    'PosCode': cassa.id_cassa,
                    'Date': data
                }
            )
            scontrini_fidelity = 0
            scontrini = 0
            totale_cassa = 0
            incasso_per_tipo_pagamento = {}
            incasso_per_reparti = {}
            for scontrino in response_data.json()['Data']:
                scontrini_fidelity += 1 if len(scontrino['FidelityCard']) > 0 else 0
                scontrini += 1
                totale_cassa += scontrino['Total']
                # Se contanti e` presente nel tender devo fare un elaborazione diversa perche` le api non tengono conto del resto
                for tipo_pagamento in scontrino['TendersDetails']:
                    if "CONTANTI" in tipo_pagamento['Description']:
                        totale_tender_senza_contante = sum(
                            _tender['Total'] for _tender in \
                            
                            list(
                                filter(
                                    lambda __tender: 'CONTANTI' not in __tender['Description'], scontrino['TendersDetails']
                                )
                            )
                        )
                        if totale_tender_senza_contante != 0:
                            print("ok")
                        try:
                            incasso_per_tipo_pagamento[tipo_pagamento['Description']] += scontrino[
                                                                                             'Total'] - totale_tender_senza_contante
                        except KeyError as ex:
                            incasso_per_tipo_pagamento[tipo_pagamento['Description']] = 0
                            incasso_per_tipo_pagamento[tipo_pagamento['Description']] +=  scontrino[
                                                                                             'Total'] - totale_tender_senza_contante
                    else:
                        try:
                            incasso_per_tipo_pagamento[tipo_pagamento['Description']] += tipo_pagamento['Total']
                        except KeyError as ex:
                            incasso_per_tipo_pagamento[tipo_pagamento['Description']] = 0
                            incasso_per_tipo_pagamento[tipo_pagamento['Description']] += tipo_pagamento['Total']

                for riga_scontrino in scontrino['ReceiptRows']:
                    try:
                        incasso_per_reparti[riga_scontrino['DepartmentCode']]['Incasso'] = incasso_per_reparti[
                                                                                    riga_scontrino['DepartmentCode']]['Incasso'] + \
                                                                                (riga_scontrino['Total'] if
                                                                                 riga_scontrino['Sign'] == '+' else -
                                                                                riga_scontrino['Total'])
                        incasso_per_reparti[riga_scontrino['DepartmentCode']]['Presenza'] += 1
                    except KeyError as ex:
                        incasso_per_reparti[riga_scontrino['DepartmentCode']] = {}
                        incasso_per_reparti[riga_scontrino['DepartmentCode']]['Incasso'] = 0
                        incasso_per_reparti[riga_scontrino['DepartmentCode']]['Incasso'] = incasso_per_reparti[
                                                                                    riga_scontrino['DepartmentCode']]['Incasso'] + \
                                                                                (riga_scontrino['Total'] if
                                                                                 riga_scontrino['Sign'] == '+' else -
                                                                                riga_scontrino['Total'])
                        incasso_per_reparti[riga_scontrino['DepartmentCode']]['Presenza'] = 1
            cassa.incasso_per_reparto = list(
                map(lambda incasso_reparto: Reparto(nome='Dummy', codice=incasso_reparto[0],
                                                    incasso=round(float(incasso_reparto[1]['Incasso']), 2),presenza=incasso_reparto[1]['Presenza']),
                    incasso_per_reparti.items()))
            cassa.incasso_per_tipo_pagamento = list(
                map(lambda incasso_pagamento: Pagamento(tipo_pagamento=incasso_pagamento[0],
                                                        incasso=round(float(incasso_pagamento[1]), 2)),
                    incasso_per_tipo_pagamento.items()))
            cassa.numero_scontrini = scontrini
            cassa.numero_scontrini_fidelity = scontrini_fidelity
            cassa.totale = sum(reparto.incasso for reparto in cassa.incasso_per_reparto)
        return negozio
    
    