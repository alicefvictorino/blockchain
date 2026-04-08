"""Comandos auxiliares da demo de votacao em blockchain."""

import argparse
import random


def buscar_chave_publica(url_api):
    """Busca a chave publica da Autoridade Registradora."""
    import requests

    resposta = requests.get(f"{url_api}/autoridade/chave-publica", timeout=10)
    resposta.raise_for_status()
    dados = resposta.json()
    return int(dados["n"]), int(dados["e"])


def assinar_voto_cego(url_api, mensagem_ofuscada):
    """Solicita a assinatura cega de uma mensagem ofuscada."""
    import requests

    resposta = requests.post(
        f"{url_api}/autoridade/assinar-voto-cego",
        json={"mensagem_ofuscada": str(mensagem_ofuscada)},
        timeout=10,
    )
    resposta.raise_for_status()
    return int(resposta.json()["assinatura_cega"])


def enviar_voto(url_api, transacao):
    """Envia a transacao final de voto para a API."""
    import requests

    resposta = requests.post(f"{url_api}/vote", json=transacao, timeout=10)
    resposta.raise_for_status()
    return resposta.json()


def comando_gerar_chaves_ar(_args):
    """Gera um par de chaves RSA para compartilhar entre os nos da demo."""
    from app.voting.core import gerar_chaves_ar

    n, e, d = gerar_chaves_ar()
    print(f"CHAVE_AR_N={n}")
    print(f"CHAVE_AR_E={e}")
    print(f"CHAVE_AR_D={d}")


def comando_gerar_transacoes(args):
    """Gera transacoes reproduziveis e envia para a API."""
    from app.voting.core import finalizar_assinatura, gerar_voto_cego

    random.seed(args.seed)
    candidatos = ["Candidato A", "Candidato B", "Voto Nulo", "Voto Branco"]
    n, e = buscar_chave_publica(args.url_api)

    for indice in range(args.quantidade):
        candidato = random.choice(candidatos)
        nullifier = f"seed-{args.seed}-voto-{indice}"
        pacote = gerar_voto_cego(candidato, n, e, nullifier=nullifier)
        assinatura_cega = assinar_voto_cego(args.url_api, pacote["mensagem_ofuscada"])
        assinatura = finalizar_assinatura(assinatura_cega, pacote["r"], n)
        transacao = {
            "tx_id": f"tx-{args.seed}-{indice}",
            "election_id": args.election_id,
            "candidate_id": candidato,
            "signature": str(assinatura),
            "nullifier": pacote["nullifier"],
            "timestamp": indice,
        }
        resposta = enviar_voto(args.url_api, transacao)
        print(f"{transacao['tx_id']}: {resposta}")


def criar_parser():
    """Cria o parser dos comandos auxiliares."""
    parser = argparse.ArgumentParser(
        description="Comandos auxiliares da demo de votacao em blockchain."
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    parser_chaves = subparsers.add_parser(
        "gerar-chaves-ar",
        help="gera chaves RSA para a Autoridade Registradora",
    )
    parser_chaves.set_defaults(func=comando_gerar_chaves_ar)

    parser_transacoes = subparsers.add_parser(
        "gerar-transacoes",
        help="gera votos reproduziveis e envia para a API",
    )
    parser_transacoes.add_argument("--url-api", default="http://127.0.0.1:8000")
    parser_transacoes.add_argument("--quantidade", type=int, default=5)
    parser_transacoes.add_argument("--seed", type=int, default=42)
    parser_transacoes.add_argument("--election-id", default="eleicao-demo")
    parser_transacoes.set_defaults(func=comando_gerar_transacoes)

    return parser


def main(argv=None):
    """Executa o comando solicitado."""
    parser = criar_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
