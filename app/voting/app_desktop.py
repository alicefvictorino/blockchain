"""Interface desktop da urna de votacao."""

import json
import os
import time
import uuid

import requests

URL_API = os.getenv("URL_API_VOTACAO", "http://127.0.0.1:8000")
ELECTION_ID = os.getenv("ELECTION_ID", "eleicao-demo")


def buscar_chave_publica():
    """Busca a chave publica da Autoridade Registradora."""
    resposta = requests.get(f"{URL_API}/autoridade/chave-publica", timeout=10)
    resposta.raise_for_status()
    dados = resposta.json()
    return int(dados["n"]), int(dados["e"])


def solicitar_assinatura_cega(mensagem_ofuscada):
    """Solicita a assinatura cega do voto para a API."""
    resposta = requests.post(
        f"{URL_API}/autoridade/assinar-voto-cego",
        json={"mensagem_ofuscada": str(mensagem_ofuscada)},
        timeout=10,
    )
    resposta.raise_for_status()
    return int(resposta.json()["assinatura_cega"])


def enviar_transacao_voto(transacao):
    """Envia a transacao final do voto para a API."""
    resposta = requests.post(f"{URL_API}/vote", json=transacao, timeout=10)
    resposta.raise_for_status()
    return resposta.json()


def main():
    """Cria e executa a interface grafica da urna."""
    import customtkinter as ctk

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    janela = ctk.CTk()
    janela.geometry("550x700")
    janela.title("Urna Eletrônica")

    memoria_cliente = {
        "r_guardado": None,
        "texto_voto_guardado": None,
        "nullifier_guardado": None,
    }

    def registrar_log(texto):
        caixa_texto.insert("end", texto)
        caixa_texto.see("end")
        janela.update()

    def ao_clicar_votar():
        from app.voting.core import finalizar_assinatura, gerar_voto_cego

        candidato_escolhido = menu_candidatos.get()

        caixa_texto.configure(state="normal")
        caixa_texto.delete("0.0", "end")

        try:
            registrar_log("[*] Buscando chave pública da Autoridade Registradora\n")
            n, e = buscar_chave_publica()
            time.sleep(0.5)

            registrar_log("[*] Inicializando módulo de segurança\n")
            pacote_voto = gerar_voto_cego(candidato_escolhido, n, e)

            memoria_cliente["r_guardado"] = pacote_voto["r"]
            memoria_cliente["texto_voto_guardado"] = pacote_voto["texto_voto"]
            memoria_cliente["nullifier_guardado"] = pacote_voto["nullifier"]

            json_1_texto = json.dumps(
                {"mensagem_ofuscada": str(pacote_voto["mensagem_ofuscada"])},
                indent=2,
            )
            registrar_log("[!] Ofuscação RSA concluída.\n")
            registrar_log(f" JSON 1 finalizado:\n{json_1_texto}\n\n")
            time.sleep(0.5)

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
                f"[!] Resposta da API:\n{json.dumps(resposta_api, indent=2)}\n"
            )
        except requests.RequestException as erro:
            registrar_log(f"[ERRO] Falha de comunicação com a API: {erro}\n")
        except Exception as erro:
            registrar_log(f"[ERRO] Falha ao preparar o voto: {erro}\n")

        caixa_texto.configure(state="disabled")

    titulo = ctk.CTkLabel(
        janela,
        text="SISTEMA DE VOTAÇÃO",
        font=("Consolas", 30, "bold"),
    )
    titulo.pack(pady=20)

    instrucao = ctk.CTkLabel(
        janela,
        text="Selecione o seu candidato:",
        font=("Consolas", 18),
    )
    instrucao.pack(pady=5)

    menu_candidatos = ctk.CTkOptionMenu(
        janela,
        values=["Candidato A", "Candidato B", "Voto Nulo", "Voto Branco"],
        width=200,
    )
    menu_candidatos.pack(pady=10)

    botao_votar = ctk.CTkButton(
        janela,
        text="CONFIRMAR VOTO",
        font=("Consolas", 20, "bold"),
        fg_color="green",
        hover_color="darkgreen",
        height=50,
        command=ao_clicar_votar,
    )
    botao_votar.pack(pady=20)

    label_log = ctk.CTkLabel(
        janela,
        text="Terminal de Vizualização:",
        font=("Consolas", 16),
    )
    label_log.pack(pady=(10, 0))

    caixa_texto = ctk.CTkTextbox(
        janela,
        width=450,
        height=300,
        font=("Consolas", 15),
        text_color="#00FF00",
        fg_color="#1E1E1E",
    )
    caixa_texto.insert("0.0", "Aguardando ação do eleitor...")
    caixa_texto.configure(state="disabled")
    caixa_texto.pack(pady=10)

    janela.mainloop()


if __name__ == "__main__":
    main()
