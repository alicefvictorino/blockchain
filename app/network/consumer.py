"""Consumer Kafka para receber transacoes da blockchain.

Este modulo expoe loops reutilizaveis para consumir transacoes e blocos
do broker Kafka sem executar efeitos colaterais no import.
"""

import json
import logging
from contextlib import suppress

from app.config import KAFKA_BOOTSTRAP_SERVERS, NODE_ID

from .topics import TOPICO_BLOCOS, TOPICO_TRANSACOES, TIPO_NOVA_TRANSACAO, TIPO_NOVO_BLOCO

logger = logging.getLogger(__name__)


def criar_consumidor(topico):
    """Cria um consumer Kafka para o topico informado."""
    from kafka import KafkaConsumer

    return KafkaConsumer(
        topico,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"{NODE_ID}-{topico}",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        consumer_timeout_ms=1000,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )


def extrair_dados_mensagem(valor_mensagem, tipo_esperado):
    """Extrai os dados de um envelope Kafka ou de mensagens antigas sem envelope."""
    if not isinstance(valor_mensagem, dict):
        return None

    if "type" not in valor_mensagem and tipo_esperado == TIPO_NOVA_TRANSACAO:
        return valor_mensagem

    if valor_mensagem.get("type") != tipo_esperado:
        return None

    dados = valor_mensagem.get("data")
    if not isinstance(dados, dict):
        return None
    return dados


def _executar_loop(topico, tipo_esperado, manipulador, parar_evento):
    consumidor = None
    try:
        consumidor = criar_consumidor(topico)
        while not parar_evento.is_set():
            for mensagem in consumidor:
                dados = extrair_dados_mensagem(mensagem.value, tipo_esperado)
                if dados is None:
                    logger.warning("Mensagem ignorada no topico %s: %s", topico, mensagem.value)
                    continue
                manipulador(dados)
                if parar_evento.is_set():
                    break
    except Exception as erro:
        logger.warning("Consumer do topico %s encerrado: %s", topico, erro)
    finally:
        if consumidor:
            with suppress(Exception):
                consumidor.close()


def consumir_transacoes(runtime_no, parar_evento):
    """Consome transacoes Kafka e delega para o runtime do no."""
    _executar_loop(
        TOPICO_TRANSACOES,
        TIPO_NOVA_TRANSACAO,
        runtime_no.receber_transacao,
        parar_evento,
    )


def consumir_blocos(runtime_no, parar_evento):
    """Consome blocos Kafka e delega para o runtime do no."""
    _executar_loop(
        TOPICO_BLOCOS,
        TIPO_NOVO_BLOCO,
        runtime_no.receber_bloco,
        parar_evento,
    )
