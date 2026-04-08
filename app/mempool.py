"""Mempool em memoria para transacoes pendentes."""

from collections import OrderedDict
from threading import RLock


class Mempool:
    """Armazena transacoes pendentes em ordem de chegada."""

    def __init__(self):
        self._transacoes = OrderedDict()
        self._nullifiers = {}
        self._lock = RLock()

    def adicionar(self, transacao, nullifiers_confirmados=None, tx_ids_confirmados=None):
        nullifiers_confirmados = nullifiers_confirmados or set()
        tx_ids_confirmados = tx_ids_confirmados or set()
        tx_id = transacao.get("tx_id")
        nullifier = transacao.get("nullifier")

        with self._lock:
            if tx_id in self._transacoes or tx_id in tx_ids_confirmados:
                return False, "tx_id duplicado"
            if nullifier in self._nullifiers or nullifier in nullifiers_confirmados:
                return False, "nullifier duplicado"

            self._transacoes[tx_id] = transacao
            self._nullifiers[nullifier] = tx_id
            return True, "OK"

    def selecionar(self, limite):
        with self._lock:
            return list(self._transacoes.values())[:limite]

    def remover(self, transacoes):
        with self._lock:
            for transacao in transacoes:
                tx_id = transacao.get("tx_id")
                removida = self._transacoes.pop(tx_id, None)
                if removida:
                    self._nullifiers.pop(removida.get("nullifier"), None)

    def listar(self):
        with self._lock:
            return list(self._transacoes.values())
