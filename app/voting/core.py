import hashlib
import math
import random
import secrets

from Crypto.PublicKey import RSA
from Crypto.Util.number import bytes_to_long


def _hash_texto_para_inteiro(texto):
    hash_bytes = hashlib.sha256(texto.encode("utf-8")).digest()
    return bytes_to_long(hash_bytes)


# gera o par de chaves RSA para realizar o processo de criptografia
def gerar_chaves_ar(tamanho=2048):

    chave_ar = RSA.generate(tamanho)

    n = chave_ar.n
    e = chave_ar.e
    d = chave_ar.d  # mantido em segredo pela AR

    return n, e, d


# gera um fator de ofuscação e o cliente ofusca a mensagem antes de enviar para o AR
def ofuscar_mensagem(m, n, e):

    r = random.randint(2, n - 1)
    while math.gcd(r, n) != 1:
        r = random.randint(2, n - 1)

    r_elevado_e = pow(r, e, n)

    m_cega = (m * r_elevado_e) % n

    return m_cega, r


# assina a mensagem cega sem saber o que tem dentro
def assinar_mensagem(m_cega, d, n):

    s_cega = pow(m_cega, d, n)

    return s_cega


# o cliente remove a ofuscacao e revela a assinatura real
def desofuscar_assinatura(s_cega, r, n):

    inverso_r = pow(r, -1, n)

    assinatura_real = (s_cega * inverso_r) % n

    return assinatura_real


# a blockchain verifica a veracidade da assinatura
def verificar_assinatura(voto, assinatura, e, n):

    # converte a string para um número inteiro gigante para a matemática funcionar

    m_esperado = _hash_texto_para_inteiro(voto)

    mensagem_verificada = pow(assinatura, e, n)  # retira a criptografiada assinatura

    if mensagem_verificada == m_esperado:
        return True

    else:
        return False


def criar_texto_voto(candidate_id, nullifier):
    """Cria a mensagem deterministica assinada pela Autoridade Registradora."""
    return f"{candidate_id}|serial:{nullifier}"


def gerar_voto_cego(candidate_id, n, e, nullifier=None):
    """
    Gera a mensagem ofuscada do voto e guarda os dados necessarios
    para o cliente concluir a assinatura depois.
    """
    nullifier = nullifier or secrets.token_hex(16)
    texto_voto = criar_texto_voto(candidate_id, nullifier)
    m = _hash_texto_para_inteiro(texto_voto)
    mensagem_ofuscada, r = ofuscar_mensagem(m, n, e)

    return {
        "mensagem_ofuscada": mensagem_ofuscada,
        "r": r,
        "texto_voto": texto_voto,
        "nullifier": nullifier,
    }


def finalizar_assinatura(s_cega, r, n):
    """Remove a ofuscacao da assinatura retornada pela AR."""
    return desofuscar_assinatura(s_cega, r, n)


# gera o json 1 ofuscado, mantido por compatibilidade com a interface antiga
def gerar_pacote_voto_cego(candidato, n, e):

    serial = secrets.token_hex(16)

    texto_voto = criar_texto_voto(candidato, serial)
    m = _hash_texto_para_inteiro(texto_voto)
    m_cega, r = ofuscar_mensagem(m, n, e)

    json_1 = {"mensagem_ofuscada": m_cega}

    return json_1, r, texto_voto
