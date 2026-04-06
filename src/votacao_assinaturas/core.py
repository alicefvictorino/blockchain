import hashlib
import math
import random
import secrets

from Crypto.PublicKey import RSA
from Crypto.Util.number import bytes_to_long


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

    # donverte a string para um número inteiro gigante para a matemática funcionar

    hash_bytes = hashlib.sha256(voto.encode("utf-8")).digest()

    m_esperado = bytes_to_long(hash_bytes)

    mensagem_verificada = pow(assinatura, e, n)  # retira a criptografiada assinatura

    if mensagem_verificada == m_esperado:
        return True

    else:
        return False


# gera o json 1 ofuscado
def gerar_pacote_voto_cego(candidato, n, e):

    serial = secrets.token_hex(16)

    texto_voto = f"{candidato}|serial:{serial}"

    # converte a string para um número inteiro gigante para a matemática funcionar
    hash_bytes = hashlib.sha256(texto_voto.encode("utf-8")).digest()
    m = bytes_to_long(hash_bytes)

    m_cega, r = ofuscar_mensagem(m, n, e)

    json_1 = {"mensagem_ofuscada": m_cega}

    return json_1, r, texto_voto
