"""Configuracoes compartilhadas da aplicacao."""

import os


def _obter_int(nome, padrao):
    return int(os.getenv(nome, str(padrao)))


def _obter_float(nome, padrao):
    return float(os.getenv(nome, str(padrao)))


KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DIFICULDADE_MINERACAO = _obter_int("DIFICULDADE_MINERACAO", 2)
INTERVALO_MINERADOR = _obter_float("INTERVALO_MINERADOR", 1.0)
MAX_TRANSACOES_POR_BLOCO = _obter_int("MAX_TRANSACOES_POR_BLOCO", 5)
NODE_ID = os.getenv("NODE_ID", "no-1")
ELECTION_ID_PADRAO = os.getenv("ELECTION_ID", "eleicao-demo")
CHAVE_AR_N = os.getenv("CHAVE_AR_N")
CHAVE_AR_E = os.getenv("CHAVE_AR_E")
CHAVE_AR_D = os.getenv("CHAVE_AR_D")
