"""Runtime de um no da rede de votacao."""

import logging
import threading
import time
from collections import deque

from app.config import (
    CHAVE_AR_D,
    CHAVE_AR_E,
    CHAVE_AR_N,
    DIFICULDADE_MINERACAO,
    INTERVALO_MINERADOR,
    MAX_TRANSACOES_POR_BLOCO,
)
from app.blockchain import Block, Blockchain
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
        self.chave_n, self.chave_e, self.chave_d = self._carregar_chaves_ar()
        self.mempool = Mempool()
        self.blockchain = Blockchain(
            difficulty=dificuldade,
            transaction_validator=self.validar_transacao,
        )
        self._lock = threading.RLock()
        self._alertas_seguranca = deque(maxlen=20)
        self._sequencia_alertas = 0

    def _carregar_chaves_ar(self):
        """Carrega as chaves da AR do ambiente ou gera um par novo para demo local."""
        chaves = (
            ("CHAVE_AR_N", CHAVE_AR_N),
            ("CHAVE_AR_E", CHAVE_AR_E),
            ("CHAVE_AR_D", CHAVE_AR_D),
        )

        if all(valor in (None, "") for _, valor in chaves):
            return gerar_chaves_ar()

        faltando = [nome for nome, valor in chaves if valor in (None, "")]
        if faltando:
            raise RuntimeError(
                "Configuracao incompleta da Autoridade Registradora. "
                f"Variaveis ausentes: {', '.join(faltando)}."
            )

        try:
            chave_n = int(CHAVE_AR_N or "")
            chave_e = int(CHAVE_AR_E or "")
            chave_d = int(CHAVE_AR_D or "")
            return chave_n, chave_e, chave_d
        except ValueError as erro:
            raise RuntimeError(
                "Configuracao invalida da Autoridade Registradora: "
                "CHAVE_AR_N, CHAVE_AR_E e CHAVE_AR_D devem ser inteiros."
            ) from erro

    def obter_chave_publica(self):
        return {"n": str(self.chave_n), "e": str(self.chave_e)}

    def assinar_voto_cego(self, mensagem_ofuscada):
        assinatura_cega = assinar_mensagem(
            int(mensagem_ofuscada), self.chave_d, self.chave_n
        )
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
            logger.warning(
                "Transacao rejeitada antes da mempool: tx_id=%s motivo=%s",
                transacao.get("tx_id"),
                reason,
            )
            return {"status": "rejeitada", "motivo": reason}

        with self._lock:
            adicionada, motivo = self.mempool.adicionar(
                transacao,
                nullifiers_confirmados=self.blockchain.get_confirmed_nullifiers(),
                tx_ids_confirmados=self.blockchain.get_confirmed_tx_ids(),
            )

        if not adicionada:
            logger.warning(
                "Mempool recusou transacao: tx_id=%s nullifier=%s motivo=%s",
                transacao.get("tx_id"),
                transacao.get("nullifier"),
                motivo,
            )
            self._registrar_alerta_transacao(transacao, motivo, origem="mempool")
            return {"status": "rejeitada", "motivo": motivo}

        logger.info(
            "Transacao aceita na mempool: tx_id=%s nullifier=%s",
            transacao["tx_id"],
            transacao["nullifier"],
        )
        return {"status": "aceita", "tx_id": transacao["tx_id"]}

    def receber_bloco(self, bloco):
        with self._lock:
            for transacao in bloco.get("transactions", []):
                valid, reason = self.validar_transacao(transacao)
                if not valid:
                    logger.warning(
                        "Bloco rejeitado na validacao de transacoes: motivo=%s",
                        reason,
                    )
                    return {"status": "rejeitado", "motivo": reason}

            resultado = self.blockchain.receive_block(bloco)
            if resultado in ("added", "duplicate", "chain_replaced"):
                self.mempool.remover(bloco.get("transactions", []))
            logger.info("Resultado do bloco recebido: %s", resultado)

        return {"status": resultado}

    def simular_fork(self):
        """
        Gera um fork local de demonstracao e tenta forcar reorganizacao.

        O metodo cria:
        1) Um bloco alternativo no penultimo bloco da cadeia.
        2) Blocos extras no ramo alternativo ate vencer por trabalho acumulado.
        """
        with self._lock:
            if len(self.blockchain.chain) < 2:
                bloco_base = self.blockchain.add_block(
                    [{"type": "genesis", "data": "bloco-base-fork-demo"}]
                )
                logger.info(
                    "Bloco base criado para permitir fork: index=%s hash=%s",
                    bloco_base.index,
                    bloco_base.hash[:16],
                )

            cadeia_atual = self.blockchain.chain
            indice_pai = max(0, len(cadeia_atual) - 2)
            bloco_pai = cadeia_atual[indice_pai]
            dificuldade = self.blockchain.difficulty
            resultados = []

            bloco_fork = Block(
                index=bloco_pai.index + 1,
                transactions=[
                    {
                        "type": "genesis",
                        "data": f"fork-demo-1-no-pai-{bloco_pai.index}",
                    }
                ],
                previous_hash=bloco_pai.hash,
                difficulty=dificuldade,
            )
            status = self.blockchain.receive_block(bloco_fork.to_dict())
            resultados.append(
                {
                    "etapa": "bloco_fork_1",
                    "status": status,
                    "hash": bloco_fork.hash,
                    "previous_hash": bloco_fork.previous_hash,
                }
            )

            ponta_ramo = bloco_fork
            for etapa in range(2, 8):
                if status == "chain_replaced":
                    break

                bloco_extra = Block(
                    index=ponta_ramo.index + 1,
                    transactions=[
                        {
                            "type": "genesis",
                            "data": f"fork-demo-extra-{etapa}",
                        }
                    ],
                    previous_hash=ponta_ramo.hash,
                    difficulty=dificuldade,
                )
                status = self.blockchain.receive_block(bloco_extra.to_dict())
                resultados.append(
                    {
                        "etapa": f"bloco_fork_{etapa}",
                        "status": status,
                        "hash": bloco_extra.hash,
                        "previous_hash": bloco_extra.previous_hash,
                    }
                )
                ponta_ramo = bloco_extra

            return {
                "status_final": status,
                "cadeia_length": len(self.blockchain.chain),
                "forks_count": len(self.blockchain.get_forks_summary()),
                "resultados": resultados,
            }

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

    def alertas_seguranca_serializados(self):
        with self._lock:
            return list(self._alertas_seguranca)

    def _registrar_alerta_transacao(self, transacao, motivo, origem):
        if motivo != "nullifier duplicado":
            return None

        with self._lock:
            self._sequencia_alertas += 1
            alerta = {
                "event_id": self._sequencia_alertas,
                "type": "gasto_duplo_detectado",
                "severity": "alta",
                "origin": origem,
                "reason": motivo,
                "message": "Tentativa de reutilizar um nullifier ja utilizado.",
                "tx_id": transacao.get("tx_id"),
                "nullifier": transacao.get("nullifier"),
                "candidate_id": transacao.get("candidate_id"),
                "detected_at": time.time(),
            }
            self._alertas_seguranca.append(alerta)
            return alerta
