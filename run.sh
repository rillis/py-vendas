#!/usr/bin/env bash
# Equivalente Linux do run.bat: ativa o venv, roda vendas.py e repete a cada Enter.

cd "$(dirname "$0")" || exit 1

if [ ! -f venv/bin/activate ]; then
    echo "venv nao encontrado. Crie com:"
    echo "  python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

if ! command -v wl-copy >/dev/null && ! command -v xclip >/dev/null && ! command -v xsel >/dev/null; then
    echo "Aviso: nenhum utilitario de area de transferencia encontrado."
    echo "Instale wl-clipboard (Wayland) ou xclip/xsel (X11) para o pyperclip funcionar."
    echo
fi

# shellcheck disable=SC1091
source venv/bin/activate

while true; do
    clear
    echo "Iniciando execucao"
    echo
    python vendas.py
    echo
    read -rp "Pressione Enter para continuar . . . "
done
