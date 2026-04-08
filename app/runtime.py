"""Runtime de um no da rede de votacao."""

import logging
import threading
import time

from app.config import (
    CHAVE_AR_D,
    CHAVE_AR_E,
    CHAVE_AR_N,
    DIFICULDADE_MINERACAO,
    INTERVALO_MINERADOR,
    MAX_TRANSACOES_POR_BLOCO,
)
from app.blockchain import Blockchain
from app.mempool import Mempool
from app.voting.core import (
    assinar_mensagem,
    criar_texto_voto,
    gerar_chaves_ar,
    verificar_assinatura,
)


logger = logging.getLogger(__name__)


class RuntimeNo:
    """Coordena AR, mempool, blockchain, mineracao e consumers Kafka."""

    def __init__(self, dificuldade=DIFICULDADE_MINERACAO):
        if CHAVE_AR_N and CHAVE_AR_E and CHAVE_AR_D:
            self.chave_n = int(CHAVE_AR_N)
            self.chave_e = int(CHAVE_AR_E)
            self.chave_d = int(CHAVE_AR_D)
        else:
            self.chave_n, self.chave_e, self.chave_d = gerar_chaves_ar()
        self.mempool = Mempool()
        self.blockchain = Blockchain(
            difficulty=dificuldade,
            transaction_validator=self.validar_transacao,
        )
        self._lock = threading.RLock()

    def obter_chave_publica(self):
        return {"n": str(self.chave_n), "e": str(self.chave_e)}

    def assinar_voto_cego(self, mensagem_ofuscada):
        assinatura_cega = assinar_mensagem(int(mensagem_ofuscada), self.chave_d, self.chave_n)
        return {"assinatura_cega": str(assinatura_cega)}

    def validar_transacao(self, transacao):
        campos_obrigatorios = [
            "tx_id",
            "election_id",
            "candidate_id",
            "signature",
            "nullifier",
            "timestamp",
        ]
        for campo in campos_obrigatorios:
            if campo not in transacao or transacao[campo] in ("", None):
                return False, f"Campo obrigatorio ausente: {campo}"

        try:
            assinatura = int(transacao["signature"])
            texto_voto = criar_texto_voto(
                transacao["candidate_id"],
                transacao["nullifier"],
            )
        except (TypeError, ValueError) as erro:
            return False, f"Transacao malformada: {erro}"

        if not verificar_assinatura(texto_voto, assinatura, self.chave_e, self.chave_n):
            return False, "Assinatura invalida"

        return True, "OK"

    def receber_transacao(self, transacao):
        valid, reason = self.validar_transacao(transacao)
        if not valid:
            return {"status": "rejeitada", "motivo": reason}

        with self._lock:
            adicionada, motivo = self.mempool.adicionar(
                transacao,
                nullifiers_confirmados=self.blockchain.get_confirmed_nullifiers(),
                tx_ids_confirmados=self.blockchain.get_confirmed_tx_ids(),
            )

        if not adicionada:
            return {"status": "rejeitada", "motivo": motivo}

        return {"status": "aceita", "tx_id": transacao["tx_id"]}

    def receber_bloco(self, bloco):
        with self._lock:
            for transacao in bloco.get("transactions", []):
                valid, reason = self.validar_transacao(transacao)
                if not valid:
                    return {"status": "rejeitado", "motivo": reason}

            resultado = self.blockchain.receive_block(bloco)
            if resultado in ("added", "duplicate", "chain_replaced"):
                self.mempool.remover(bloco.get("transactions", []))

        return {"status": resultado}

    def minerar_uma_vez(self):
        with self._lock:
            transacoes = self.mempool.selecionar(MAX_TRANSACOES_POR_BLOCO)
            if not transacoes:
                return None

            bloco = self.blockchain.add_block(transacoes)
            self.mempool.remover(transacoes)
            return bloco

    def executar_minerador(self, parar_evento, publicar_bloco):
        while not parar_evento.is_set():
            try:
                bloco = self.minerar_uma_vez()
                if bloco:
                    publicar_bloco(bloco.to_dict())
            except Exception as erro:
                logger.warning("Falha na mineracao: %s", erro)

            parar_evento.wait(INTERVALO_MINERADOR)

    def cadeia_serializada(self):
        with self._lock:
            return self.blockchain.to_dict()

    def forks_serializados(self):
        with self._lock:
            return self.blockchain.get_forks_summary()

    def mempool_serializada(self):
        return self.mempool.listar()
