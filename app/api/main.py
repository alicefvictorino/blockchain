"""Aplicacao FastAPI do sistema de votacao em blockchain."""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.network.consumer import consumir_blocos, consumir_transacoes
from app.network.producer import enviar_bloco, enviar_transacao
from app.runtime import RuntimeNo


class PedidoAssinaturaCega(BaseModel):
    """Payload enviado pelo cliente para a Autoridade Registradora."""

    mensagem_ofuscada: str | int


class TransacaoVoto(BaseModel):
    """Contrato padrao da transacao de voto."""

    tx_id: str
    election_id: str
    candidate_id: str
    signature: str
    nullifier: str
    timestamp: int | float


runtime_no = RuntimeNo()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa os workers de um no da rede."""
    parar_evento = threading.Event()
    app.state.runtime_no = runtime_no
    app.state.parar_evento = parar_evento

    workers = [
        threading.Thread(
            target=consumir_transacoes,
            args=(runtime_no, parar_evento),
            name="consumer-transacoes",
            daemon=True,
        ),
        threading.Thread(
            target=consumir_blocos,
            args=(runtime_no, parar_evento),
            name="consumer-blocos",
            daemon=True,
        ),
        threading.Thread(
            target=runtime_no.executar_minerador,
            args=(parar_evento, enviar_bloco),
            name="minerador",
            daemon=True,
        ),
    ]

    for worker in workers:
        worker.start()

    app.state.workers = workers
    yield

    parar_evento.set()
    for worker in workers:
        worker.join(timeout=1.0)


app = FastAPI(lifespan=lifespan)


@app.get("/")
def verificar_api():
    """Endpoint de verificacao da API.

    Returns:
        dict: Mensagem indicando que a API esta em execucao.

    """
    return {"message": "API funcionando"}


@app.get("/autoridade/chave-publica")
def obter_chave_publica():
    """Retorna a chave publica da Autoridade Registradora."""
    return runtime_no.obter_chave_publica()


@app.post("/autoridade/assinar-voto-cego")
def assinar_voto_cego(pedido: PedidoAssinaturaCega):
    """Assina uma mensagem ofuscada sem revelar o voto."""
    try:
        return runtime_no.assinar_voto_cego(pedido.mensagem_ofuscada)
    except Exception as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@app.post("/vote")
def receber_voto(voto: TransacaoVoto) -> dict:
    """Recebe um voto e encaminha a transacao para o Kafka.

    Args:
        `voto (TransacaoVoto):` Transacao de voto com election_id, candidate_id, signature
        e nullifier.

    Returns:
        dict: Mensagem confirmando que o voto foi enviado ao Kafka.

    """
    transacao = voto.model_dump() if hasattr(voto, "model_dump") else voto.dict()
    try:
        enviar_transacao(transacao)
    except Exception as erro:
        raise HTTPException(status_code=503, detail=f"Kafka indisponivel: {erro}") from erro
    return {"status": "enviado para Kafka", "tx_id": voto.tx_id}


@app.get("/chain")
def visualizar_cadeia():
    """Retorna a cadeia principal atual do no."""
    cadeia = runtime_no.cadeia_serializada()
    return {"length": len(cadeia), "chain": cadeia}


@app.get("/forks")
def visualizar_forks():
    """Retorna os forks conhecidos pelo no."""
    forks = runtime_no.forks_serializados()
    return {"count": len(forks), "forks": forks}


@app.get("/mempool")
def visualizar_mempool():
    """Retorna as transacoes pendentes na mempool."""
    transacoes = runtime_no.mempool_serializada()
    return {"count": len(transacoes), "transactions": transacoes}


@app.get("/security-alerts")
def visualizar_alertas_de_seguranca():
    """Retorna os alertas recentes de seguranca observados pelo no."""
    alertas = runtime_no.alertas_seguranca_serializados()
    return {"count": len(alertas), "events": alertas}
