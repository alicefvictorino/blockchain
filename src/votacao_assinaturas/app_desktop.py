import json
import time

import customtkinter as ctk

# importa as funçoes do arquivo core
from votacao_assinaturas.core import gerar_chaves_ar, gerar_pacote_voto_cego

# simulação das Chaves da AR para a interface funcionar, mas esse papel será da rede
# quando fizermos a integração
CHAVE_N, CHAVE_E, CHAVE_D = gerar_chaves_ar()

# interface grafica
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

janela = ctk.CTk()
janela.geometry("550x700")
janela.title("Urna Eletrônica")

memoria_cliente = {"r_guardado": None, "texto_voto_guardado": None}


def ao_clicar_votar():
    candidato_escolhido = menu_candidatos.get()

    caixa_texto.configure(state="normal")
    caixa_texto.delete("0.0", "end")

    caixa_texto.insert("end", "[*] Inicializando módulo de segurança\n")
    janela.update()
    time.sleep(1.5)

    # executa a funcao para gerar o voto cego
    json_1_funcao, r, texto_voto = gerar_pacote_voto_cego(
        candidato_escolhido, CHAVE_N, CHAVE_E
    )

    # salva na memória
    memoria_cliente["r_guardado"] = r
    memoria_cliente["texto_voto_guardado"] = texto_voto

    # resultado
    json_1_texto = json.dumps(json_1_funcao, indent=2)
    caixa_texto.insert("end", "[!] Ofuscação RSA concluída.\n")
    janela.update()
    time.sleep(1)

    caixa_texto.insert("end", f" JSON 1 finalizado:\n{json_1_texto}\n\n")
    janela.update()
    time.sleep(1)

    # futura implementaçao da rede
    caixa_texto.insert("end", "[*] Aguardando conexão com a API da Rede\n")

    # rola a tela para o final para mostrar sempre a última linha
    caixa_texto.see("end")

    # tranca a caixa
    caixa_texto.configure(state="disabled")


# elementos da janela

titulo = ctk.CTkLabel(janela, text="SISTEMA DE VOTAÇÃO", font=("Consolas", 30, "bold"))
titulo.pack(pady=20)

instrucao = ctk.CTkLabel(
    janela, text="Selecione o seu candidato:", font=("Consolas", 18)
)
instrucao.pack(pady=5)

menu_candidatos = ctk.CTkOptionMenu(
    janela, values=["Candidato A", "Candidato B", "Voto Nulo", "Voto Branco"], width=200
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
    janela, text="Terminal de Vizualização:", font=("Consolas", 16)
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
