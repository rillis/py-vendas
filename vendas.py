"""Lê a lista de etiquetas do Mercado Livre copiada para a área de transferência
e gera a mensagem de vendas para o fornecedor (já copiada de volta)."""

import os
import re
import time

import pyperclip

PASTA = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

SAUDACAO = 'Bom dia! Tudo bem? Segue vendas de hoje:'
INTERVALO_CLIPBOARD = 1  # segundos entre leituras da área de transferência

# Tratamentos de SKU, aplicados em ordem (regex, sem diferenciar maiúsculas).
TRATAMENTOS_SKU = {
    r'Kfi-': 'KF-',
    r'KIT-6-TP-SANGRADOR': 'Tp-016.K+016.P+016.T+016.MERV+016.UNIVER+023.GM',
}

# Estoque de devoluções (MySQL do homeserver). Conexão vem do .env desta pasta.
ESTOQUE_TABELA = 'estoque'
ESTOQUE_TIMEOUT = 3  # segundos

# ---------------------------------------------------------------------------
# Marcadores do texto do ML
# ---------------------------------------------------------------------------

# Início da tabela de produtos ("Identifiicação Produtos" — o ML escreve com 'ii').
RE_INICIO = re.compile(r'Identifi+ca[cç][aã]o\s+Produtos', re.IGNORECASE)
# Fim da tabela ("Despachem as suas vendas...") ou fim do texto.
RE_FIM = re.compile(r'Despachem\b|\Z', re.IGNORECASE)
# Linha que identifica uma etiqueta. Já foi "Venda:" (com ou sem "Pack ID:"), hoje é "Envio:".
RE_CABECALHO = re.compile(r'^(?:Venda|Envio|Pack\s*ID)\s*:', re.IGNORECASE)
# Código da etiqueta que vem antes do cabeçalho (ex.: ABCDEFGHIJKLMNOPQRSTUVWXYZ).
# Copiando no Linux o título do produto vem grudado no código, então basta o começo da linha.
RE_CODIGO = re.compile(r'^[A-Z0-9]{20,32}(?:$|(?=[A-Z][a-z]))')
# Copiando no Linux "SKU:" e "Quantidade:" vêm grudados na linha anterior
# ("Envio: 123SKU: XYZ", "FulanoQuantidade: 1"); separa em linhas próprias.
RE_QUEBRA = re.compile(r'(?<=[^\n])[ \t]*(?=(?:SKU|Quantidade):)')
RE_SKU = re.compile(r'^(.*?)\s*SKU:\s*(.+)$')
RE_QTD = re.compile(r'^Quantidade:\s*(\d+)')
RE_KIT = re.compile(r'^(\d+)\s*x\s*(.+)$', re.IGNORECASE)
# Cada etiqueta da parte de cima tem uma linha "Despachar: ..."; serve para conferir o total.
RE_ETIQUETA = re.compile(r'Despachar:')

# ---------------------------------------------------------------------------
# Número por extenso (feminino, para "unidades")
# ---------------------------------------------------------------------------

_UNIDADES = ['zero', 'uma', 'duas', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove',
             'dez', 'onze', 'doze', 'treze', 'quatorze', 'quinze', 'dezesseis', 'dezessete',
             'dezoito', 'dezenove']
_DEZENAS = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta',
            'oitenta', 'noventa']
_CENTENAS = ['', 'cento', 'duzentas', 'trezentas', 'quatrocentas', 'quinhentas', 'seiscentas',
             'setecentas', 'oitocentas', 'novecentas']


def _ate_999(n):
    if n == 100:
        return 'cem'
    partes = []
    c, resto = divmod(n, 100)
    if c:
        partes.append(_CENTENAS[c])
    if resto >= 20:
        d, u = divmod(resto, 10)
        partes.append(_DEZENAS[d] + (f' e {_UNIDADES[u]}' if u else ''))
    elif resto:
        partes.append(_UNIDADES[resto])
    return ' e '.join(partes)


def por_extenso(n):
    """Número inteiro (0 a 999.999) por extenso, no feminino: 22 -> 'vinte e duas'."""
    if n < 1000:
        return _ate_999(n)
    milhar, resto = divmod(n, 1000)
    texto = 'mil' if milhar == 1 else f'{_ate_999(milhar)} mil'
    if resto:
        # "mil e duzentas", "mil e trinta", mas "mil duzentas e trinta"
        sep = ' e ' if resto < 100 or resto % 100 == 0 else ' '
        texto += sep + _ate_999(resto)
    return texto


# ---------------------------------------------------------------------------
# Leitura das etiquetas
# ---------------------------------------------------------------------------

def tabelas_de_produtos(texto):
    """Devolve o trecho de cada tabela 'Identificação Produtos' (pode haver várias páginas)."""
    tabelas = []
    for inicio in RE_INICIO.finditer(texto):
        fim = RE_FIM.search(texto, inicio.end())
        tabelas.append(texto[inicio.end():fim.start()])
    return tabelas


def ler_etiquetas(tabela):
    """Lê uma tabela de produtos e devolve [{'nome': str, 'itens': [[sku, qtd], ...]}]."""
    etiquetas = []
    atual = None

    def nova():
        nonlocal atual
        atual = {'nome': None, 'itens': []}
        etiquetas.append(atual)

    for linha in RE_QUEBRA.sub('\n', tabela).splitlines():
        linha = linha.strip()
        if not linha:
            continue

        # Código ou cabeçalho abrem uma etiqueta nova, a menos que a atual ainda
        # esteja vazia (ex.: código + "Pack ID:" + "Venda:" são a mesma etiqueta).
        if RE_CODIGO.match(linha) or RE_CABECALHO.match(linha):
            if atual is None or atual['nome'] or atual['itens']:
                nova()
            continue

        if atual is None:
            nova()

        m = RE_SKU.match(linha)
        if m:
            nome, sku = m.group(1).strip(), m.group(2).strip()
            if nome and not atual['nome']:  # "Fulano SKU: XYZ" na mesma linha
                atual['nome'] = nome
            atual['itens'].append([sku, None])
            continue

        m = RE_QTD.match(linha)
        if m and atual['itens']:
            atual['itens'][-1][1] = int(m.group(1))
            continue

        # Primeira linha "solta" é o nome; o resto (Voltagem, Cor...) é ignorado.
        # O nome pode vir antes do SKU ou entre o SKU e a "Quantidade:" (cópia no Linux).
        if not atual['nome'] and (not atual['itens'] or atual['itens'][-1][1] is None):
            atual['nome'] = linha

    return [e for e in etiquetas if e['nome'] or e['itens']]


def tratar_item(sku, qtd, avisos, debug):
    """Aplica os tratamentos de SKU e o multiplicador de kit ("2x KF-101")."""
    original = sku
    for padrao, troca in TRATAMENTOS_SKU.items():
        sku = re.sub(padrao, troca, sku, flags=re.IGNORECASE)

    if qtd is None:
        avisos.append(f'SKU "{original}" sem "Quantidade:" — considerado 1.')
        qtd = 1

    m = RE_KIT.match(sku)
    if m:
        antes = f'{qtd}x {sku}'
        qtd *= int(m.group(1))
        sku = m.group(2).strip()
        debug.append(f'"{antes}" -> {qtd}x {sku}')

    return sku, qtd


def formatar_item(sku, qtd):
    if qtd > 1:
        return f'*{qtd}x* {sku} *({por_extenso(qtd)} unidades)*'
    return f'{qtd}x {sku}'


def gerar_mensagem(texto):
    """Devolve (mensagem, total_de_etiquetas, avisos, debug, vendidos).

    vendidos: [(nome, sku_tratado, qtd), ...] — usado no cruzamento com o estoque."""
    texto = texto.replace('\r', '')
    avisos, debug, linhas, vendidos = [], [], [], []

    etiquetas = [e for tabela in tabelas_de_produtos(texto) for e in ler_etiquetas(tabela)]

    for i, etiqueta in enumerate(etiquetas, 1):
        nome = etiqueta['nome'] or f'(sem nome #{i})'
        if not etiqueta['nome']:
            avisos.append(f'Etiqueta #{i} sem nome do comprador.')
        if not etiqueta['itens']:
            avisos.append(f'Etiqueta #{i} ({nome}) sem SKU.')
        itens = []
        for sku, qtd in etiqueta['itens']:
            sku, qtd = tratar_item(sku, qtd, avisos, debug)
            itens.append(formatar_item(sku, qtd))
            vendidos.append((nome, sku, qtd))
        linhas.append(f'- {nome}: ' + ' + '.join(itens))

    # Confere com a quantidade de etiquetas impressas na parte de cima.
    impressas = len(RE_ETIQUETA.findall(texto))
    if impressas and impressas != len(etiquetas):
        avisos.append(f'{impressas} etiquetas no texto, mas {len(etiquetas)} lidas na tabela de produtos.')

    mensagem = '\n'.join([SAUDACAO, *linhas])
    return mensagem, len(etiquetas), avisos, debug, vendidos


# ---------------------------------------------------------------------------
# Estoque de devoluções (só leitura: aponta possíveis matches, não altera nada)
# ---------------------------------------------------------------------------

def ler_env(caminho=os.path.join(PASTA, '.env')):
    """Lê um .env simples (CHAVE=valor, # comentário). Sem dependência extra."""
    env = {}
    if not os.path.exists(caminho):
        return env
    with open(caminho, encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#') or '=' not in linha:
                continue
            chave, valor = linha.split('=', 1)
            env[chave.strip()] = valor.strip().strip('"\'')
    return env


def buscar_estoque():
    """Devolve {SKU_MAIUSCULO: (sku_original, qtd)} dos SKUs com qtd > 0."""
    import pymysql

    env = ler_env()
    tls = {}
    if env.get('DB_SSL_CA'):
        # TLS obrigatório, validando o certificado do servidor pela CA do .env.
        # O certificado auto-gerado do MySQL não tem o hostname, então só a CA é conferida.
        tls = dict(ssl_ca=os.path.join(PASTA, env['DB_SSL_CA']),
                   ssl_verify_cert=True, ssl_verify_identity=False)
    conexao = pymysql.connect(
        **tls,
        host=env.get('DB_HOST', ''),
        port=int(env.get('DB_PORT') or 3306),
        user=env.get('DB_USER', ''),
        password=env.get('DB_PASS', ''),
        database=env.get('DB_NAME', ''),
        connect_timeout=ESTOQUE_TIMEOUT,
        read_timeout=ESTOQUE_TIMEOUT,
        charset='utf8mb4',
    )
    try:
        with conexao.cursor() as cur:
            cur.execute('SET SESSION TRANSACTION READ ONLY')
            cur.execute(f'SELECT sku, qtd FROM `{ESTOQUE_TABELA}` WHERE qtd > 0')
            return {sku.strip().upper(): (sku.strip(), qtd) for sku, qtd in cur.fetchall()}
    finally:
        conexao.close()


def partes_do_sku(sku):
    """Separa kits por '+'. Partes sem prefixo herdam o da primeira
    (Tp-016.K+016.P -> TP-016.K, TP-016.P). Também expande macho+fêmea
    (TP-036.M+F.GM2 -> TP-036.M.GM2, TP-036.F.GM2) e corrige 'TP.036' -> 'TP-036'."""
    sku = re.sub(r'\b([A-Z]+)\.(\d)', r'\1-\2', sku.upper())
    sku = re.sub(r'([A-Z]+-\d+)\.M\+F\.([A-Z0-9]+)', r'\1.M.\2+\1.F.\2', sku)
    partes = [p.strip() for p in sku.split('+') if p.strip()]
    if not partes:
        return []
    m = re.match(r'^([A-Z]+-)', partes[0])
    prefixo = m.group(1) if m else ''
    return [prefixo + p if prefixo and re.match(r'^\d', p) else p for p in partes]


def base_do_sku(sku):
    """Base para variações: tudo antes do primeiro '.' (KF-234.ADM -> KF-234)."""
    return sku.split('.', 1)[0]


def cruzar_estoque(vendidos, estoque):
    """Devolve (exatos, parecidos): listas de
    (nome, sku_vendido, qtd_vendida, sku_estoque, qtd_estoque)."""
    por_base = {}
    for chave in estoque:
        por_base.setdefault(base_do_sku(chave), []).append(chave)

    exatos, parecidos = [], []
    for nome, sku, qtd in vendidos:
        for parte in partes_do_sku(sku):
            if parte in estoque:
                exatos.append((nome, parte, qtd, *estoque[parte]))
                continue
            for chave in sorted(por_base.get(base_do_sku(parte), [])):
                parecidos.append((nome, parte, qtd, *estoque[chave]))

    # Não repete como "parecido" uma peça que já bateu exata na mesma venda.
    ja_exatos = {(nome, sku_estoque.upper()) for nome, _, _, sku_estoque, _ in exatos}
    parecidos = [p for p in parecidos if (p[0], p[3].upper()) not in ja_exatos]
    return exatos, parecidos


def mostrar_estoque(vendidos):
    print('-' * 40)
    print('ESTOQUE DE DEVOLUÇÕES (possíveis matches, nada foi alterado):')
    try:
        estoque = buscar_estoque()
    except Exception as e:  # sem rede, senha errada, pymysql ausente...
        print(f'  Não consegui consultar o estoque ({type(e).__name__}: {e}).')
        return

    exatos, parecidos = cruzar_estoque(vendidos, estoque)
    if not exatos and not parecidos:
        print('  Nenhum item das vendas está no estoque de devoluções.')
        return
    blocos = [(rotulo, lista) for rotulo, lista in
              (('[MESMO SKU]', exatos), ('[PARECIDO]', parecidos)) if lista]
    for i, (rotulo, lista) in enumerate(blocos):
        if i:
            print()
        print(rotulo)
        for nome, vendido, levando, no_estoque, total in lista:
            print(f'- {levando}x {vendido} ({nome}) -> tem {total}x {no_estoque}')


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def esperar_lista():
    print(f'Esperando a lista de etiquetas na área de transferência... (a cada {INTERVALO_CLIPBOARD}s)')
    while True:
        texto = pyperclip.paste() or ''
        if RE_INICIO.search(texto):
            return texto
        time.sleep(INTERVALO_CLIPBOARD)


def main():
    texto = esperar_lista()
    print(f'Lista encontrada (tamanho: {len(texto)})')

    mensagem, total, avisos, debug, vendidos = gerar_mensagem(texto)

    print(f'Total: {total}')
    print('-' * 40)
    print(mensagem)
    print('-' * 40)

    if debug:
        print('KITS:')
        for linha in debug:
            print(f'  {linha}')
    if avisos:
        print('ATENÇÃO:')
        for linha in avisos:
            print(f'  {linha}')

    if total:
        pyperclip.copy(mensagem)
        print('Mensagem copiada para a área de transferência.')
        mostrar_estoque(vendidos)
    else:
        print('Nenhuma venda encontrada — nada foi copiado.')


if __name__ == '__main__':
    main()
