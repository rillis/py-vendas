#!/usr/bin/env bash
# Equivalente Linux do run.bat: ativa o venv, roda vendas.py e repete a cada Enter.

cd "$(dirname "$0")" || exit 1

if ! command -v wl-copy >/dev/null && ! command -v xclip >/dev/null && ! command -v xsel >/dev/null; then
    echo "Erro: nenhum utilitario de area de transferencia encontrado."
    echo "Instale wl-clipboard (Wayland) ou xclip/xsel (X11) para o pyperclip funcionar."
    exit 1
fi

if [ ! -f venv/bin/activate ]; then
    echo "Criando venv e instalando dependencias..."
    if ! python3 -m venv venv || ! venv/bin/pip install -r requirements.txt; then
        echo "Erro: falha ao criar o venv."
        rm -rf venv
        exit 1
    fi
fi

# shellcheck disable=SC1091
source venv/bin/activate

while true; do
    clear
    echo "Iniciando execucao"
    echo
    python vendas.py
    echo
    read -rp "Pressione Enter para continuar . . . " || exit 0
done
