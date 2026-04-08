"""Producer Kafka para transacoes e blocos da blockchain.

Este modulo envia mensagens para os topicos Kafka, sem aplicar regras de negocio.
"""

import json
from functools import lru_cache

from app.config import KAFKA_BOOTSTRAP_SERVERS

from .topics import TOPICO_BLOCOS, TOPICO_TRANSACOES, TIPO_NOVA_TRANSACAO, TIPO_NOVO_BLOCO


@lru_cache(maxsize=1)
def obter_produtor():
    """Cria o producer Kafka sob demanda."""
    from kafka import KafkaProducer

    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def _enviar(topico, tipo, dados, produtor=None):
    cliente = produtor or obter_produtor()
    mensagem = {"type": tipo, "data": dados}
    cliente.send(topico, mensagem)
    cliente.flush()


def enviar_transacao(transacao: dict, produtor=None):
    """Envia uma transacao para o topico Kafka de transacoes."""
    _enviar(TOPICO_TRANSACOES, TIPO_NOVA_TRANSACAO, transacao, produtor=produtor)


def enviar_bloco(bloco: dict, produtor=None):
    """Envia um bloco minerado para o topico Kafka de blocos."""
    _enviar(TOPICO_BLOCOS, TIPO_NOVO_BLOCO, bloco, produtor=produtor)
