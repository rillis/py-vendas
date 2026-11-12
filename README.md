# py-vendas

Transforma a lista de etiquetas do Mercado Livre (copiada da página de impressão) na mensagem de vendas para o fornecedor, já pronta para colar no WhatsApp.

## O que faz

1. Fica olhando a área de transferência até aparecer uma lista de etiquetas (o texto com "Identificação Produtos").
2. Lê a tabela de produtos: uma linha por etiqueta, com o nome do comprador e os SKUs do carrinho.
3. Aplica os tratamentos de SKU (dicionário `TRATAMENTOS_SKU` no topo de `vendas.py`) e o multiplicador de kit (`2x KF-101` com quantidade 3 vira `6x KF-101`).
4. Monta a mensagem e copia de volta para a área de transferência:

   ```
   Bom dia! Tudo bem? Segue vendas de hoje:
   - Maria Exemplo: 1x KF-101
   - João Exemplo: 1x Chv-gangorra + 1x Conj-solenoide
   - Ana Exemplo: *2x* KF-232 *(duas unidades)*
   ```

5. Cruza os SKUs vendidos com o estoque de devoluções (tabela `estoque` no MySQL) e lista os possíveis matches: `[MESMO SKU]` para SKU idêntico e `[PARECIDO]` para variações com a mesma base (`KF-234.ADM` / `KF-234.ESCAPE`). Só consulta, não altera o estoque.

## Configuração

Requer Python 3.10+.

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Preencha o `.env` com a conexão do MySQL do estoque:

| Variável | O que é |
|---|---|
| `DB_HOST` | Endereço do MySQL |
| `DB_PORT` | Porta (padrão 3306) |
| `DB_USER` | Usuário |
| `DB_PASS` | Senha |
| `DB_NAME` | Banco onde está a tabela `estoque` (colunas `sku`, `qtd`) |

Sem o `.env`, ou sem acesso ao banco, a mensagem é gerada e copiada normalmente; só o cruzamento com o estoque mostra um aviso.

## Como usar

Rode `run.bat`. Ele ativa o `venv`, executa `vendas.py` e, depois de cada lista, espera um Enter para aguardar a próxima.

1. Na página de etiquetas do Mercado Livre, selecione tudo (Ctrl+A) e copie (Ctrl+C).
2. O script detecta a lista, imprime a mensagem e copia para a área de transferência.
3. Cole no WhatsApp do fornecedor.

## Ajustes comuns

No topo de `vendas.py`:

- `SAUDACAO`: primeira linha da mensagem.
- `TRATAMENTOS_SKU`: trocas aplicadas nos SKUs antes de montar a mensagem (regex, sem diferenciar maiúsculas).
- `ESTOQUE_TABELA` / `ESTOQUE_TIMEOUT`: tabela do estoque e tempo máximo de espera do banco.
