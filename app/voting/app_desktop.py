"""Interface desktop da urna de votacao."""

import json
import os
import time
import uuid

import requests

URL_API = os.getenv("URL_API_VOTACAO", "http://127.0.0.1:8000")
ELECTION_ID = os.getenv("ELECTION_ID", "eleicao-demo")
TIMEOUT_API = 10
AUTO_REFRESH_MS = int(os.getenv("AUTO_REFRESH_MS", "2000"))
MAX_BLOCOS_MONITOR = int(os.getenv("MAX_BLOCOS_MONITOR", "8"))


def requisitar_api(metodo, rota, **kwargs):
    """Executa uma requisicao HTTP para a API da demo."""
    resposta = requests.request(
        metodo,
        f"{URL_API}{rota}",
        timeout=TIMEOUT_API,
        **kwargs,
    )
    resposta.raise_for_status()
    return resposta.json()


def buscar_chave_publica():
    """Busca a chave publica da Autoridade Registradora."""
    dados = requisitar_api("GET", "/autoridade/chave-publica")
    return int(dados["n"]), int(dados["e"])


def solicitar_assinatura_cega(mensagem_ofuscada):
    """Solicita a assinatura cega do voto para a API."""
    resposta = requisitar_api(
        "POST",
        "/autoridade/assinar-voto-cego",
        json={"mensagem_ofuscada": str(mensagem_ofuscada)},
    )
    return int(resposta["assinatura_cega"])


def enviar_transacao_voto(transacao):
    """Envia a transacao final do voto para a API."""
    return requisitar_api("POST", "/vote", json=transacao)


def consultar_status_api():
    """Consulta o endpoint de status da API."""
    return requisitar_api("GET", "/")


def consultar_blockchain():
    """Consulta a blockchain atual do no."""
    return requisitar_api("GET", "/chain")


def consultar_mempool():
    """Consulta a mempool atual do no."""
    return requisitar_api("GET", "/mempool")


def consultar_forks():
    """Consulta os forks conhecidos pelo no."""
    return requisitar_api("GET", "/forks")

def simular_fork_api():
    """Solicita ao no a simulacao controlada de um fork."""
    return requisitar_api("POST", "/debug/simular-fork")

def consultar_alertas_seguranca():
    """Consulta os alertas de seguranca produzidos pelo no."""
    return requisitar_api("GET", "/security-alerts")

def encurtar_texto(valor, tamanho=14):
    """Encurta hashes e ids longos para facilitar a leitura."""
    texto = str(valor)
    if len(texto) <= tamanho:
        return texto
    metade = max(4, tamanho // 2)
    return f"{texto[:metade]}...{texto[-metade:]}"


def contar_zeros_iniciais(hash_bloco):
    """Conta quantos zeros existem no inicio do hash."""
    contador = 0
    for caractere in str(hash_bloco):
        if caractere != "0":
            break
        contador += 1
    return contador


def resumir_transacao(transacao):
    """Resume uma transacao para exibicao na interface."""
    if transacao.get("type") == "genesis":
        return "genesis | Início da votação"

    candidato = transacao.get("candidate_id") or transacao.get("candidate") or "?"
    tx_id = encurtar_texto(transacao.get("tx_id", "sem-tx"))
    nullifier = encurtar_texto(transacao.get("nullifier", "sem-nullifier"))
    return f"{candidato} | tx {tx_id} | serial {nullifier}"


def formatar_horario_evento(timestamp_evento):
    """Formata o horario de um evento do backend."""
    if timestamp_evento in (None, ""):
        return "--:--:--"
    return time.strftime("%H:%M:%S", time.localtime(timestamp_evento))


def resumir_alerta(alerta):
    """Resume um alerta de seguranca para exibicao no monitor."""
    tipo = alerta.get("type")
    horario = formatar_horario_evento(alerta.get("detected_at"))
    if tipo == "gasto_duplo_detectado":
        return (
            f"Gasto duplo detectado | {horario} | "
            f"serial {encurtar_texto(alerta.get('nullifier', 'sem-nullifier'))} | "
            f"tx {encurtar_texto(alerta.get('tx_id', 'sem-tx'))}"
        )
    return (
        f"Alerta de seguranca | {horario} | "
        f"{alerta.get('reason', 'sem motivo informado')}"
    )


def filtrar_alertas_gasto_duplo(alertas):
    """Retorna apenas os alertas relacionados a gasto duplo."""
    return [
        alerta
        for alerta in alertas.get("events", [])
        if alerta.get("type") == "gasto_duplo_detectado"
    ]


def montar_relacao_blocos(cadeia):
    """Monta uma linha simples mostrando o encadeamento da blockchain."""
    if not cadeia:
        return "sem blocos"

    blocos_visiveis = cadeia[-MAX_BLOCOS_MONITOR:]
    etiquetas = []
    for bloco in blocos_visiveis:
        if bloco["index"] == 0:
            etiquetas.append("GEN")
        else:
            etiquetas.append(f"B{bloco['index']:02d}")
    relacao = " -> ".join(etiquetas)
    ocultos = len(cadeia) - len(blocos_visiveis)
    if ocultos > 0:
        relacao = f"... ({ocultos} bloco(s) anteriores) -> {relacao}"
    return relacao


def montar_texto_monitor(status_api, cadeia, mempool, forks, alertas):
    """Monta o texto exibido no monitor da rede."""
    horario = time.strftime("%H:%M:%S")
    blocos = cadeia.get("chain", [])
    transacoes_pendentes = mempool.get("transactions", [])
    forks_resumo = forks.get("forks", [])
    alertas_recentes = alertas.get("events", [])
    alertas_gasto_duplo = filtrar_alertas_gasto_duplo(alertas)
    ultimo_alerta_gasto_duplo = alertas_gasto_duplo[-1] if alertas_gasto_duplo else None

    linhas = [
        "MONITOR DA REDE",
        "================",
        f"Atualizado em: {horario}",
        f"Status da API: {status_api.get('message', 'desconhecido')}",
        (
            f"Blocos: {cadeia.get('length', 0)} | "
            f"Mempool: {mempool.get('count', 0)} | "
            f"Forks: {forks.get('count', 0)} | "
            f"Alertas: {alertas.get('count', 0)}"
        ),
        "",
        "STATUS DE SEGURANCA",
        "-------------------",
    ]

    if ultimo_alerta_gasto_duplo is None:
        linhas.extend(
            [
                "Nenhum ataque de gasto duplo detectado.",
                "",
            ]
        )
    else:
        linhas.extend(
            [
                "ATAQUE DE GASTO DUPLO DETECTADO",
                (
                    "Ultimo evento: "
                    f"{formatar_horario_evento(ultimo_alerta_gasto_duplo.get('detected_at'))}"
                ),
                (
                    "Serial reutilizado: "
                    f"{encurtar_texto(ultimo_alerta_gasto_duplo.get('nullifier', 'sem-nullifier'))}"
                ),
                (
                    "Transacao rejeitada: "
                    f"{encurtar_texto(ultimo_alerta_gasto_duplo.get('tx_id', 'sem-tx'))}"
                ),
                "",
            ]
        )

    linhas.extend(
        [
            "RELACAO ENTRE BLOCOS",
            "--------------------",
            montar_relacao_blocos(blocos),
            "",
            "CADEIA PRINCIPAL",
            "---------------",
        ]
    )

    if not blocos:
        linhas.append("Nenhum bloco encontrado.")
    else:
        blocos_visiveis = blocos[-MAX_BLOCOS_MONITOR:]
        for bloco in blocos_visiveis:
            linhas.append(
                f"[B{bloco['index']:02d}] "
                f"hash={encurtar_texto(bloco['hash'])} "
                f"prev={encurtar_texto(bloco['previous_hash'])}"
            )
            linhas.append(
                f"      nonce={bloco['nonce']} | diff={bloco['difficulty']} | "
                f"pow_zeros={contar_zeros_iniciais(bloco['hash'])} | "
                f"txs={len(bloco['transactions'])}"
            )
            for transacao in bloco["transactions"][:3]:
                linhas.append(f"      - {resumir_transacao(transacao)}")
            extras = len(bloco["transactions"]) - 3
            if extras > 0:
                linhas.append(f"      - ... e mais {extras} transacao(oes)")
            linhas.append("")

    linhas.extend(
        [
            "MEMPOOL",
            "-------",
        ]
    )
    if not transacoes_pendentes:
        linhas.append("Nenhuma transacao pendente.")
    else:
        for transacao in transacoes_pendentes[:6]:
            linhas.append(f"- {resumir_transacao(transacao)}")
        extras = len(transacoes_pendentes) - 6
        if extras > 0:
            linhas.append(f"- ... e mais {extras} transacao(oes)")

    linhas.extend(
        [
            "",
            "FORKS",
            "-----",
        ]
    )
    if not forks_resumo:
        linhas.append("Nenhum fork registrado.")
    else:
        for fork in forks_resumo:
            linhas.append(
                f"- fork apos o bloco {fork['divergence_index'] - 1} | "
                f"ramo alternativo com {fork['branch_length']} bloco(s) | "
                f"trabalho {fork['branch_work']} | "
                f"hash pai {encurtar_texto(fork['fork_point_hash'])}"
            )

    linhas.extend(
        [
            "",
            "ALERTAS DE SEGURANCA",
            "--------------------",
        ]
    )
    if not alertas_recentes:
        linhas.append("Nenhum alerta recente.")
    else:
        for alerta in alertas_recentes[-6:]:
            linhas.append(f"- {resumir_alerta(alerta)}")

    return "\n".join(linhas) + "\n"


def main():
    """Cria e executa a interface grafica da demo."""
    import customtkinter as ctk

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    janela = ctk.CTk()
    janela.geometry("1280x860")
    janela.minsize(1160, 760)
    janela.title("Painel de Votação e Blockchain")

    memoria_cliente = {
        "r_guardado": None,
        "texto_voto_guardado": None,
        "nullifier_guardado": None,
        "ultima_transacao": {},
    }
    estado_monitor = {
        "auto_refresh": True,
        "ultimo_topo": None,
        "ultimo_tamanho_cadeia": None,
        "ultimo_mempool": None,
        "ultimo_forks": None,
        "ultimo_alerta_id": 0,
    }

    status_api_var = ctk.StringVar(value="API: não verificada")
    status_acao_var = ctk.StringVar(value="Última ação: aguardando interação")
    status_voto_var = ctk.StringVar(value="Último voto: nenhum")
    metric_blocos_var = ctk.StringVar(value="Blocos: --")
    metric_mempool_var = ctk.StringVar(value="Mempool: --")
    metric_forks_var = ctk.StringVar(value="Forks: --")
    metric_alertas_var = ctk.StringVar(value="Alertas: --")
    metric_ataque_var = ctk.StringVar(value="Ataque: nenhum")
    metric_atualizacao_var = ctk.StringVar(value="Última leitura: --:--:--")
    monitor_auto_var = ctk.StringVar(value="Monitor: automático")

    def definir_texto(widget, texto):
        posicao_atual = widget.yview()[0]
        widget.configure(state="normal")
        widget.delete("0.0", "end")
        widget.insert("0.0", texto)
        widget.configure(state="disabled")
        widget.yview_moveto(posicao_atual)

    def anexar_texto(widget, texto):
        widget.configure(state="normal")
        widget.insert("end", texto)
        widget.configure(state="disabled")
        widget.see("end")
        janela.update()

    def registrar_log(texto, limpar=False):
        if limpar:
            definir_texto(caixa_terminal, texto)
            caixa_terminal.see("end")
            janela.update()
            return
        anexar_texto(caixa_terminal, texto)

    def limpar_terminal():
        registrar_log(
            (
                "Terminal limpo.\n"
                "Use CONFIRMAR VOTO para acompanhar o fluxo da urna.\n"
                "Use os botões do painel para consultar JSONs detalhados.\n"
            ),
            limpar=True,
        )
        status_acao_var.set("Última ação: terminal limpo")

    def registrar_erro(contexto, erro):
        registrar_log(f"[ERRO] {contexto}\n{erro}\n\n")
        status_api_var.set("API: indisponível")
        status_acao_var.set(f"Última ação: falha em {contexto.lower()}")

    def registrar_sucesso(descricao):
        status_api_var.set("API: conectada")
        status_acao_var.set(f"Última ação: {descricao}")

    def exibir_json_no_terminal(titulo, dados):
        registrar_log(
            (
                f"{titulo}\n"
                f"{'-' * len(titulo)}\n"
                f"{json.dumps(dados, indent=2, ensure_ascii=False)}\n\n"
            ),
            limpar=True,
        )

    def obter_estado_rede():
        status = consultar_status_api()
        cadeia = consultar_blockchain()
        mempool = consultar_mempool()
        forks = consultar_forks()
        alertas = consultar_alertas_seguranca()
        return status, cadeia, mempool, forks, alertas

    def registrar_eventos_da_rede(cadeia, mempool, forks, alertas):
        tamanho_cadeia = cadeia.get("length", 0)
        hash_topo = None
        if cadeia.get("chain"):
            hash_topo = cadeia["chain"][-1]["hash"]

        mempool_count = mempool.get("count", 0)
        forks_count = forks.get("count", 0)
        alertas_recentes = alertas.get("events", [])
        ultimo_alerta_id = max(
            (alerta.get("event_id", 0) for alerta in alertas_recentes),
            default=0,
        )

        if estado_monitor["ultimo_tamanho_cadeia"] is None:
            estado_monitor["ultimo_tamanho_cadeia"] = tamanho_cadeia
            estado_monitor["ultimo_topo"] = hash_topo
            estado_monitor["ultimo_mempool"] = mempool_count
            estado_monitor["ultimo_forks"] = forks_count
            estado_monitor["ultimo_alerta_id"] = ultimo_alerta_id
            return

        if tamanho_cadeia > estado_monitor["ultimo_tamanho_cadeia"]:
            registrar_log(
                "[REDE] Blockchain cresceu para "
                f"{tamanho_cadeia} bloco(s). Topo: {encurtar_texto(hash_topo)}\n"
            )
        elif hash_topo != estado_monitor["ultimo_topo"] and hash_topo is not None:
            registrar_log(
                f"[REDE] O topo da cadeia mudou para {encurtar_texto(hash_topo)}.\n"
            )

        if mempool_count != estado_monitor["ultimo_mempool"]:
            registrar_log(
                f"[REDE] Mempool atualizada: {mempool_count} transacao(oes) pendente(s).\n"
            )

        if forks_count > (estado_monitor["ultimo_forks"] or 0):
            registrar_log(
                f"[REDE] Novo fork detectado. Total de forks: {forks_count}.\n"
            )

        novos_alertas = [
            alerta
            for alerta in alertas_recentes
            if alerta.get("event_id", 0) > estado_monitor["ultimo_alerta_id"]
        ]
        for alerta in novos_alertas:
            if alerta.get("type") == "gasto_duplo_detectado":
                registrar_log(
                    "[ALERTA] Ataque de gasto duplo detectado. "
                    f"Serial {encurtar_texto(alerta.get('nullifier', 'sem-nullifier'))} | "
                    f"tx {encurtar_texto(alerta.get('tx_id', 'sem-tx'))}.\n"
                )
            else:
                registrar_log(f"[ALERTA] {resumir_alerta(alerta)}.\n")

        estado_monitor["ultimo_tamanho_cadeia"] = tamanho_cadeia
        estado_monitor["ultimo_topo"] = hash_topo
        estado_monitor["ultimo_mempool"] = mempool_count
        estado_monitor["ultimo_forks"] = forks_count
        estado_monitor["ultimo_alerta_id"] = ultimo_alerta_id

    def atualizar_monitor(logar_eventos=True):
        try:
            status, cadeia, mempool, forks, alertas = obter_estado_rede()
        except requests.RequestException as erro:
            definir_texto(
                caixa_monitor,
                f"MONITOR DA REDE\n================\nAPI indisponível.\nErro: {erro}\n",
            )
            status_api_var.set("API: indisponível")
            metric_blocos_var.set("Blocos: --")
            metric_mempool_var.set("Mempool: --")
            metric_forks_var.set("Forks: --")
            metric_alertas_var.set("Alertas: --")
            metric_ataque_var.set("Ataque: --")
            metric_atualizacao_var.set("Última leitura: falhou")
            return

        texto_monitor = montar_texto_monitor(status, cadeia, mempool, forks, alertas)
        definir_texto(caixa_monitor, texto_monitor)
        alertas_gasto_duplo = filtrar_alertas_gasto_duplo(alertas)

        status_api_var.set("API: conectada")
        metric_blocos_var.set(f"Blocos: {cadeia.get('length', 0)}")
        metric_mempool_var.set(f"Mempool: {mempool.get('count', 0)}")
        metric_forks_var.set(f"Forks: {forks.get('count', 0)}")
        metric_alertas_var.set(f"Alertas: {alertas.get('count', 0)}")
        if alertas_gasto_duplo:
            metric_ataque_var.set("Ataque: gasto duplo detectado")
        else:
            metric_ataque_var.set("Ataque: nenhum")
        metric_atualizacao_var.set(f"Última leitura: {time.strftime('%H:%M:%S')}")

        if logar_eventos:
            registrar_eventos_da_rede(cadeia, mempool, forks, alertas)

    def ciclo_monitor():
        if estado_monitor["auto_refresh"]:
            atualizar_monitor(logar_eventos=True)
        janela.after(AUTO_REFRESH_MS, ciclo_monitor)

    def alternar_monitor():
        estado_monitor["auto_refresh"] = not estado_monitor["auto_refresh"]
        if estado_monitor["auto_refresh"]:
            monitor_auto_var.set("Monitor: automático")
            registrar_log("[PAINEL] Autoatualização reativada.\n")
            atualizar_monitor(logar_eventos=False)
        else:
            monitor_auto_var.set("Monitor: pausado")
            registrar_log("[PAINEL] Autoatualização pausada.\n")
        status_acao_var.set("Última ação: alternou monitor automático")

    def atualizar_agora():
        atualizar_monitor(logar_eventos=True)
        status_acao_var.set("Última ação: monitor atualizado manualmente")

    def consultar_json(nome, consulta, rota):
        try:
            dados = consulta()
        except requests.RequestException as erro:
            registrar_erro(f"Falha ao consultar {rota}", erro)
            return

        registrar_sucesso(f"consulta de {nome.lower()}")
        exibir_json_no_terminal(f"{nome} ({rota})", dados)

    def ao_clicar_status_api():
        consultar_json("Status da API", consultar_status_api, "/")

    def ao_clicar_blockchain():
        consultar_json("Blockchain", consultar_blockchain, "/chain")

    def ao_clicar_mempool():
        consultar_json("Mempool", consultar_mempool, "/mempool")

    def ao_clicar_forks():
        consultar_json("Forks", consultar_forks, "/forks")

    def ao_clicar_alertas():
        consultar_json(
            "Alertas de segurança", consultar_alertas_seguranca, "/security-alerts"
        )

    def ao_clicar_votar():
        from app.voting.core import finalizar_assinatura, gerar_voto_cego

        candidato_escolhido = menu_candidatos.get()
        registrar_log(
            f"[URNA] Iniciando fluxo de voto para {candidato_escolhido}\n\n",
            limpar=True,
        )

        try:
            registrar_log("[*] Buscando chave pública da Autoridade Registradora\n")
            n, e = buscar_chave_publica()
            registrar_sucesso("busca da chave pública")
            time.sleep(0.3)

            registrar_log("[*] Inicializando módulo de segurança\n")
            pacote_voto = gerar_voto_cego(candidato_escolhido, n, e)

            memoria_cliente["r_guardado"] = pacote_voto["r"]
            memoria_cliente["texto_voto_guardado"] = pacote_voto["texto_voto"]
            memoria_cliente["nullifier_guardado"] = pacote_voto["nullifier"]

            registrar_log("[!] Ofuscação RSA concluída.\n")
            registrar_log(
                json.dumps(
                    {"mensagem_ofuscada": str(pacote_voto["mensagem_ofuscada"])},
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            time.sleep(0.3)

            registrar_log("[*] Solicitando assinatura cega à API\n")
            assinatura_cega = solicitar_assinatura_cega(
                pacote_voto["mensagem_ofuscada"]
            )
            assinatura_real = finalizar_assinatura(assinatura_cega, pacote_voto["r"], n)
            registrar_log("[!] Assinatura cega recebida e desofuscada.\n")

            transacao = {
                "tx_id": uuid.uuid4().hex,
                "election_id": ELECTION_ID,
                "candidate_id": candidato_escolhido,
                "signature": str(assinatura_real),
                "nullifier": pacote_voto["nullifier"],
                "timestamp": time.time(),
            }

            registrar_log("[*] Enviando transação final para a API\n")
            resposta_api = enviar_transacao_voto(transacao)
            registrar_log(
                "[!] Resposta da API:\n"
                f"{json.dumps(resposta_api, indent=2, ensure_ascii=False)}\n\n"
            )

            memoria_cliente["ultima_transacao"] = dict(transacao)
            status_voto_var.set(
                "Último voto: "
                f"{candidato_escolhido} | tx {transacao['tx_id'][:8]}... | "
                f"serial {pacote_voto['nullifier'][:8]}..."
            )
            status_acao_var.set("Última ação: voto enviado para a API")
            registrar_log(
                "[DICA] Use o monitor ao lado para acompanhar a mempool e o "
                "crescimento da blockchain em tempo real.\n"
            )
            atualizar_monitor(logar_eventos=True)
        except requests.RequestException as erro:
            registrar_erro("Falha de comunicação com a API", erro)
        except Exception as erro:
            registrar_log(f"[ERRO] Falha ao preparar o voto\n{erro}\n")
            status_acao_var.set("Última ação: falha ao preparar voto")

    def ao_clicar_gasto_duplo():
        ultima_transacao = memoria_cliente.get("ultima_transacao")
        if not ultima_transacao:
            registrar_log(
                "[ATAQUE] Ainda não existe um voto válido para reutilizar.\n",
                limpar=True,
            )
            status_acao_var.set("Última ação: tentativa de gasto duplo sem voto base")
            return

        transacao_ataque = dict(ultima_transacao)

        registrar_log(
            "[ATAQUE] Reenviando exatamente o mesmo JSON do ultimo voto.\n\n",
            limpar=True,
        )
        registrar_log(
            json.dumps(transacao_ataque, indent=2, ensure_ascii=False) + "\n\n"
        )

        try:
            resposta_api = enviar_transacao_voto(transacao_ataque)
        except requests.RequestException as erro:
            registrar_erro("Falha ao enviar tentativa de gasto duplo", erro)
            return

        registrar_log(
            "[ATAQUE] Resposta imediata da API:\n"
            f"{json.dumps(resposta_api, indent=2, ensure_ascii=False)}\n\n"
        )
        registrar_log(
            "[ATAQUE] Agora observe a seção ALERTAS DE SEGURANCA no monitor "
            "para ver a detecção do nullifier duplicado.\n"
        )
        status_acao_var.set("Última ação: tentativa de gasto duplo enviada")
        atualizar_monitor(logar_eventos=True)

    def ao_clicar_simular_fork():
        registrar_log(
            "[FORK] Solicitando simulacao de fork ao no da blockchain...\n\n",
            limpar=True,
        )
        try:
            resposta = simular_fork_api()
        except requests.RequestException as erro:
            registrar_erro("Falha ao simular fork", erro)
            return

        registrar_log(
            "[FORK] Resultado da simulacao:\n"
            f"{json.dumps(resposta, indent=2, ensure_ascii=False)}\n\n"
        )
        registrar_log(
            "[FORK] Veja no monitor se houve aumento em forks e mudanca no topo da cadeia.\n"
        )
        status_acao_var.set("Última ação: simulacao de fork executada")
        atualizar_monitor(logar_eventos=True)

    topo_frame = ctk.CTkFrame(janela, fg_color="transparent")
    topo_frame.pack(fill="x", padx=20, pady=(20, 12))

    cabecalho = ctk.CTkFrame(topo_frame, corner_radius=18, width=430)
    cabecalho.pack(side="left", fill="both", padx=(0, 8))

    titulo = ctk.CTkLabel(
        cabecalho,
        text="PAINEL DE VOTAÇÃO E BLOCKCHAIN",
        font=("Consolas", 28, "bold"),
    )
    titulo.pack(anchor="w", padx=18, pady=(16, 4))

    subtitulo = ctk.CTkLabel(
        cabecalho,
        text=(
            "Urna, monitor da rede, mempool, forks e crescimento da cadeia "
            "em uma única interface."
        ),
        font=("Consolas", 14),
    )
    subtitulo.pack(anchor="w", padx=18, pady=(0, 14))

    status_frame = ctk.CTkFrame(topo_frame, corner_radius=18)
    status_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))

    linha_1 = ctk.CTkFrame(status_frame, fg_color="transparent")
    linha_1.pack(fill="x", padx=18, pady=(14, 6))

    linha_2 = ctk.CTkFrame(status_frame, fg_color="transparent")
    linha_2.pack(fill="x", padx=18, pady=(0, 14))

    for texto, coluna in (
        (f"API alvo: {URL_API}", 0),
        (f"Eleição: {ELECTION_ID}", 1),
        (metric_blocos_var, 2),
        (metric_mempool_var, 3),
    ):
        if isinstance(texto, str):
            label = ctk.CTkLabel(
                linha_1,
                text=texto,
                font=("Consolas", 14, "bold"),
            )
        else:
            label = ctk.CTkLabel(
                linha_1,
                text="",
                textvariable=texto,
                font=("Consolas", 14, "bold"),
            )
        label.grid(row=0, column=coluna, padx=12, pady=4, sticky="w")

    for texto, coluna in (
        (status_api_var, 0),
        (metric_forks_var, 1),
        (metric_alertas_var, 2),
        (metric_ataque_var, 3),
        (metric_atualizacao_var, 4),
        (monitor_auto_var, 5),
    ):
        label = ctk.CTkLabel(
            linha_2,
            textvariable=texto,
            font=("Consolas", 14),
        )
        label.grid(row=0, column=coluna, padx=12, pady=4, sticky="w")

    label_status_acao = ctk.CTkLabel(
        status_frame,
        textvariable=status_acao_var,
        font=("Consolas", 14),
    )
    label_status_acao.pack(anchor="w", padx=30, pady=(0, 4))

    label_status_voto = ctk.CTkLabel(
        status_frame,
        textvariable=status_voto_var,
        font=("Consolas", 14),
    )
    label_status_voto.pack(anchor="w", padx=30, pady=(0, 14))

    controles = ctk.CTkFrame(janela, corner_radius=18)
    controles.pack(fill="x", padx=20, pady=(0, 10))

    voto_frame = ctk.CTkFrame(controles, corner_radius=14)
    voto_frame.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=16)

    consulta_frame = ctk.CTkFrame(controles, corner_radius=14)
    consulta_frame.pack(side="left", fill="both", expand=True, padx=(8, 16), pady=16)

    titulo_voto = ctk.CTkLabel(
        voto_frame,
        text="Urna do eleitor",
        font=("Consolas", 20, "bold"),
    )
    titulo_voto.pack(anchor="w", padx=16, pady=(16, 8))

    subtitulo_voto = ctk.CTkLabel(
        voto_frame,
        text="Envie um voto legítimo ou simule um gasto duplo usando o último voto.",
        font=("Consolas", 13),
    )
    subtitulo_voto.pack(anchor="w", padx=16, pady=(0, 12))

    menu_candidatos = ctk.CTkOptionMenu(
        voto_frame,
        values=["Candidato A", "Candidato B", "Voto Nulo", "Voto Branco"],
        width=280,
        font=("Consolas", 16),
        dropdown_font=("Consolas", 14),
    )
    menu_candidatos.pack(anchor="w", padx=16, pady=(0, 14))

    botao_votar = ctk.CTkButton(
        voto_frame,
        text="CONFIRMAR VOTO",
        font=("Consolas", 18, "bold"),
        fg_color="green",
        hover_color="darkgreen",
        height=48,
        command=ao_clicar_votar,
    )
    botao_votar.pack(fill="x", padx=16, pady=(0, 10))

    botao_gasto_duplo = ctk.CTkButton(
        voto_frame,
        text="SIMULAR GASTO DUPLO",
        font=("Consolas", 16, "bold"),
        fg_color="#b85c00",
        hover_color="#8f4700",
        height=44,
        command=ao_clicar_gasto_duplo,
    )
    botao_gasto_duplo.pack(fill="x", padx=16, pady=(0, 16))

    titulo_consulta = ctk.CTkLabel(
        consulta_frame,
        text="Painel do nó",
        font=("Consolas", 20, "bold"),
    )
    titulo_consulta.pack(anchor="w", padx=16, pady=(16, 8))

    subtitulo_consulta = ctk.CTkLabel(
        consulta_frame,
        text="Atualize o monitor e abra os JSONs detalhados quando precisar provar algo.",
        font=("Consolas", 13),
    )
    subtitulo_consulta.pack(anchor="w", padx=16, pady=(0, 12))

    grade_botoes = ctk.CTkFrame(consulta_frame, fg_color="transparent")
    grade_botoes.pack(fill="x", padx=16, pady=(0, 16))

    botoes_consulta = (
        ("ATUALIZAR MONITOR", atualizar_agora),
        ("PAUSAR / RETOMAR MONITOR", alternar_monitor),
        ("VER STATUS JSON", ao_clicar_status_api),
        ("VER BLOCKCHAIN JSON", ao_clicar_blockchain),
        ("VER MEMPOOL JSON", ao_clicar_mempool),
        ("VER FORKS JSON", ao_clicar_forks),
        ("SIMULAR FORK", ao_clicar_simular_fork),
        ("VER ALERTAS JSON", ao_clicar_alertas),
        ("LIMPAR TERMINAL", limpar_terminal),
    )

    for indice, (texto, comando) in enumerate(botoes_consulta):
        linha = indice // 2
        coluna = indice % 2
        botao = ctk.CTkButton(
            grade_botoes,
            text=texto,
            font=("Consolas", 15, "bold"),
            height=40,
            command=comando,
        )
        botao.grid(row=linha, column=coluna, padx=6, pady=6, sticky="ew")

    grade_botoes.grid_columnconfigure(0, weight=1)
    grade_botoes.grid_columnconfigure(1, weight=1)

    area_inferior = ctk.CTkFrame(janela, corner_radius=18)
    area_inferior.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    terminal_frame = ctk.CTkFrame(area_inferior, corner_radius=14)
    terminal_frame.pack(side="left", fill="both", expand=True, padx=(18, 9), pady=18)

    monitor_frame = ctk.CTkFrame(area_inferior, corner_radius=14)
    monitor_frame.pack(side="left", fill="both", expand=True, padx=(9, 18), pady=18)

    label_terminal = ctk.CTkLabel(
        terminal_frame,
        text="Terminal da urna",
        font=("Consolas", 18, "bold"),
    )
    label_terminal.pack(anchor="w", padx=18, pady=(16, 8))

    caixa_terminal = ctk.CTkTextbox(
        terminal_frame,
        font=("Consolas", 14),
        text_color="#00FF88",
        fg_color="#101820",
        activate_scrollbars=True,
    )
    caixa_terminal.pack(fill="both", expand=True, padx=18, pady=(0, 18))
    caixa_terminal.configure(state="disabled")

    label_monitor = ctk.CTkLabel(
        monitor_frame,
        text="Monitor da blockchain",
        font=("Consolas", 18, "bold"),
    )
    label_monitor.pack(anchor="w", padx=18, pady=(16, 8))

    caixa_monitor = ctk.CTkTextbox(
        monitor_frame,
        font=("Consolas", 13),
        text_color="#C7F9CC",
        fg_color="#14213D",
        activate_scrollbars=True,
    )
    caixa_monitor.pack(fill="both", expand=True, padx=18, pady=(0, 18))
    caixa_monitor.configure(state="disabled")

    limpar_terminal()
    atualizar_monitor(logar_eventos=False)
    janela.after(AUTO_REFRESH_MS, ciclo_monitor)
    janela.mainloop()


if __name__ == "__main__":
    main()
