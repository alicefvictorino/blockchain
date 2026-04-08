# Blockchain para votação eletrônica com assinaturas cegas (blind signatures)


## 🐍 Como configurar o ambiente do projeto

O projeto utiliza Poetry para gerenciamento de dependências, devido à sua facilidade de uso e isolamento de ambientes. Siga os passos abaixo para configurar o ambiente corretamente.

---

## 1. Clonar o repositório e entrar na pasta do projeto

No terminal:

```bash
git clone <url-do-repositorio>
cd <nome-da-pasta-do-projeto>
```

---

## 2. Instalar o Poetry

[Link para o guia de instalação](https://python-poetry.org/docs/)

---

## 3. Instalar as dependências

O projeto já possui um arquivo `pyproject.toml`, então basta rodar:

```bash
poetry install
```

👉 Isso vai:

* criar o ambiente virtual automaticamente
* instalar todas as dependências

---

## 4. Subir os contêineres (necessário ter docker instalado)

```bash
docker compose up -d
```

## 5. Rodar a API localmente

```bash
poetry run fastapi dev
```

## 6. Rodar a aplicação desktop localmente

### 6.1. Caso esteja utilizando algumas distros de Ubuntu como 24.04, será necessário instalar o tkinter

```bash
sudo apt update
sudo apt install -y python3-tk
```

### 6.2. Rodar a aplicação desktop no terminal

```bash
sudo apt update
sudo apt install -y python3-tk
```

