# -*- coding: utf-8 -*-
"""
Conhecimento do programa sobre cada byte dos arquivos de efeito do BT3.
Cada anotação: (offset, tamanho, tipo_do_valor, título, explicação, valores_conhecidos)
tipo_do_valor: 'u8', 'u16', 'u32', 'f32', 'rgba8', 'raw'
Fontes: documentação Madeirada BR (partes 1 e 2), tutorial de efeitos, documentação da comunidade e análise própria.
"""
import struct
from bt3eff_core import dbt_info, CLASS_NAMES, SCENE_MAPS, SCENE_EVENTS, MAP_NAMES

FLAGS = {1: "desconhecido", 2: "parece ligado a efeitos lançados (como o feixe do Kamehameha)", 4: "desconhecido",
         8: "usa os ossos dos parâmetros em vez do osso da animação", 16: "desconhecido",
         32: "o efeito fica sempre na frente da câmera (não pode ser coberto)", 64: "mantém a posição do efeito fixa",
         128: "corrige os anéis do Makankosappo que bugam em choque de poderes ou em ceninha"}
GROUPS = {0: "Pré-Disparo",
          1: "Pós-Disparo",
          2: "Pré/Pós-Disparo (a confirmar)",
          3: "Aura (em volta do personagem)",
          4: "Desconhecido (à descobrir; o programa usa no evento 'Vfx 5', a explosão no oponente)",
          5: "Iluminação (sobrepõe a sombra padrão pela indicada pelo shader/forma do mini efeito)"}
PERSIST = {5: "NÃO aparece durante ceninhas (confirmado)",
           3: "valor original de rodelas que aparecem na ceninha (a estudar)"}
POSITION = {0: "sem orientação (a confirmar)", 1: "orientado ao adversário (a confirmar)",
            2: "orientado para cima, usado em auras que se sobrepõem 'apontadas' para cima (a confirmar)",
            4: "orientado de dentro pra fora, usado só em iluminação (a confirmar)",
            3: "visto no estágio 4 de golpes de várias etapas, junto com +0x0B de 1 a 4 (a estudar)",
            5: "o efeito vai atrás do adversário e causa dano (confirmado)",
            6: "visto em explosões e em golpes de várias etapas (estágios 1 e 5) (a estudar)"}
STATE = {0: "normal", 1: "visto em vários efeitos (significado desconhecido)",
         4: "continua enquanto o estado estiver ativo — auras de carregamento e auras que ficam até usar especial (hipótese)"}


def A(off, size, kind, title, text, known=None):
    return (off, size, kind, title, text, known or {})


# ---------------------------------------------------------------- 03_.dat (parâmetros)
def params(f, fname="03_.dat"):
    a = []
    a.append(A(0, 3, "raw", "Bitmask das classes presentes",
               "Três bytes em que cada bit diz se uma classe existe neste efeito. A classe T fica no byte T÷8, bit T%8. "
               "Ex.: classe 05 → byte 0, bit 5 (valor 0x20); classe 0E → byte 1, bit 6 (0x40); classe 10 → byte 2, bit 0 (0x01). "
               "O programa recalcula sozinho ao salvar; editar à mão sem mudar as categorias quebra o efeito."))
    a.append(A(3, 1, "u8", "Reservado", "Sempre 00 em todos os efeitos analisados."))
    a.append(A(4, 1, "u8", "Quantidade de classes", "Quantas categorias (classes) de mini-efeitos existem logo abaixo, a partir de 0x40. Cada uma ocupa 32 bytes."))
    a.append(A(5, 1, "u8", "Total de mini-efeitos",
               "Soma dos mini-efeitos de todas as classes. Define quantos blocos de parâmetros de 64 bytes existem depois das categorias. "
               "(Raras exceções, como a aura Blue, trazem um valor 1 acima da soma.)"))
    a.append(A(6, 1, "u8", "Tipo de lançamento",
               "Byte que muda conforme o jeito do golpe sair. Valores vistos: 00 na maioria; 07 e 08 em ataques verticais; 09 no Kikoho; 0A no projétil.",
               {0: "padrão", 7: "vertical", 8: "vertical (Super Buu)", 9: "Kikoho", 10: "projétil"}))
    a.append(A(7, 1, "u8", "Desconhecido", "Sem função conhecida até agora."))
    a.append(A(8, 4, "f32", "Colisão BASE do ataque (float)",
               "Tamanho da colisão principal do golpe (ex.: 80,0 e 12,0). Vale 5 nos verticais, 8 na barragem, 20 no Madam, 80 no Horizontal do Nappa."))
    for i in range(1, 6):
        a.append(A(8 + 4 * i, 4, "f32", "Colisão extra %d (float)" % i,
                   "Usado quando o ataque precisa de mais caixas de colisão, como uma onda de energia em área "
                   "(no Kamehameha Madan esta faixa tem 20, 120, 130, 1,0 e 0,5). Nos suportes os 5 primeiros variam (ex.: 8, 25, 25, 1, 0.5)."))
    a.append(A(0x20, 1, "u8", "Início/encerramento do efeito", "Bytes 0x20 a 0x27: parâmetros específicos de inicialização/encerramento do efeito e da ceninha. Este byte ainda não tem função conhecida."))
    a.append(A(0x21, 1, "u8", "Cena: o golpe aparece na ceninha", "01 = o golpe aparece durante a ceninha (feixe final, projétil, feixe vertical...). 00 = não aparece.",
               {0: "não aparece", 1: "aparece"}))
    a.append(A(0x22, 1, "u8", "Cena: feixe vertical", "01 junto com 0x21 = 01 faz o feixe vir de cima para baixo ou de baixo para cima (Trunks Dome, Ultimate do Kid Gohan).",
               {0: "não", 1: "feixe vertical"}))
    a.append(A(0x23, 2, "raw", "Desconhecido", "Sem função conhecida."))
    a.append(A(0x25, 1, "u8", "Cena: projétil", "05 junto com 0x21 = 01 faz o golpe aparecer como PROJÉTIL na ceninha (Comet Attack do Jeice, Gotenks Volleyball).",
               {0: "não", 5: "projétil"}))
    a.append(A(0x26, 1, "u8", "Cena: modo de aparição", "Normalmente 10 quando o golpe aparece na ceninha; 50 no Ultimate do Kid Gohan; 20 na barragem do Cui."))
    a.append(A(0x27, 1, "u8", "Modo barragem", "02 = o efeito se comporta como BARRAGEM (vários disparos). 03 = barragem que também aparece na ceninha (Ultimate do Cui). 00 = disparo único.",
               {0: "disparo único", 2: "barragem", 3: "barragem na ceninha", 8: "visto no Frieza Torture"}))
    for i in range(6):
        a.append(A(0x28 + 4 * i, 4, "f32", "Colisão (tipo desconhecido) %d" % (i + 1),
                   "Bytes 0x28 a 0x3F: algo de colisão, tipo ainda desconhecido (exemplo: floats 15, 10, 0, 1,0 e 0,5 a partir de 0x2C)."))
    ncat = f[4] if len(f) > 4 else 0
    types = []
    for c in range(ncat):
        o = 64 + 32 * c
        t, n = f[o], f[o + 1]
        types += [t] * n
        nm = "%02X — %s" % (t, CLASS_NAMES.get(t, "?"))
        a.append(A(o, 1, "u8", "Categoria %d: classe" % (c + 1),
                   "Qual classe esta categoria descreve. Classe %s." % nm, {k: "%02X %s" % (k, v) for k, v in CLASS_NAMES.items()}))
        a.append(A(o + 1, 1, "u8", "Categoria %d: quantidade de mini-efeitos" % (c + 1),
                   "Quantos mini-efeitos da classe %02X existem. Os blocos de parâmetros seguem a ordem das categorias." % t))
        a.append(A(o + 2, 1, "u8", "Categoria %d: quantidade de DBTs" % (c + 1),
                   "Quantos arquivos de textura (DBT) pertencem à classe %02X. Eles vêm antes dos arquivos de forma/shader dessa classe." % t))
        a.append(A(o + 3, 29, "raw", "Categoria %d: não usado" % (c + 1), "Os outros 29 bytes de cada categoria são zeros."))
    base = 64 + 32 * ncat
    for i, t in enumerate(types):
        b = base + 64 * i
        who = "Mini-efeito #%d (classe %02X — %s)" % (i, t, CLASS_NAMES.get(t, "?"))
        glob_ = t == 0 and i == 0
        if glob_:
            a.append(A(b, 64, "raw", who + " — GLOBAL",
                       "O primeiro mini-efeito de todo 03_.dat é o efeito GLOBAL de listras brancas, guardado nos arquivos globais do jogo. "
                       "Ele não pode ser removido; para escondê-lo, zere os floats de tamanho (0x1C, 0x20, 0x24 deste bloco)."))
        a.append(A(b, 1, "flags", who + ": flags",
                   "Valores somados (1, 2, 4, 8, 16, 32, 64, 128). Cada bit liga um comportamento; para ligar dois, some os valores (8 + 32 = 40).", FLAGS))
        a.append(A(b + 1, 1, "u8", who + ": DBT usado", "Índice do DBT dentro da classe deste mini-efeito: 00 = primeiro DBT da classe, 01 = segundo..."))
        a.append(A(b + 2, 1, "u8", who + ": textura", "Qual imagem dentro do DBT escolhido: 00 = primeira imagem da lista (como no Sparking Studio)."))
        a.append(A(b + 3, 1, "u8", who + ": desconhecido", "Vale 00 ou 01; função desconhecida."))
        a.append(A(b + 4, 1, "u8", who + ": atraso A", "Atrasa a aparição do mini-efeito depois de invocado (um dos dois bytes de atraso atrasa e o outro adianta)."))
        a.append(A(b + 5, 1, "u8", who + ": atraso B", "Segundo byte de atraso da aparição, em quadros. Ex.: o clarão do Taiyoken usa 6; em golpes de várias etapas vai até 218, "
                                                       "montando uma sequência inteira a partir de um único Vfx."))
        a.append(A(b + 6, 1, "u8", who + ": duração A", "Aumenta quanto tempo o mini-efeito fica na tela depois que a animação termina."))
        a.append(A(b + 7, 1, "u8", who + ": duração B", "Segundo byte de duração."))
        a.append(A(b + 8, 1, "u8", who + ": estágio de invocação", "Momento em que o mini-efeito aparece (coluna 'Estágio de invocação' da lista).", GROUPS))
        a.append(A(b + 9, 1, "u8", who + ": estágio de desaparecimento",
                   "Define o estágio em que o mini-efeito deixa de aparecer, não só na ceninha mas durante o ataque. Só o 05 já tem nome.", PERSIST))
        a.append(A(b + 10, 1, "u8", who + ": orientação posicional", "Define mais ou menos o comportamento posicional do mini-efeito.", POSITION))
        a.append(A(b + 11, 1, "u8", who + ": estado", "Comportamento enquanto um estado está ativo.", STATE))
        a.append(A(b + 12, 4, "raw", who + ": desconhecido", "Normalmente zeros."))
        if glob_:
            a.append(A(b + 0x10, 4, "f32", who + ": parâmetro 1 das listras", "Float das listras globais (1,5 no Madam)."))
            a.append(A(b + 0x14, 4, "f32", who + ": parâmetro 2 das listras", "Float das listras globais (0,3 no Madam)."))
        else:
            a.append(A(b + 0x10, 4, "f32", who + ": posição X", "Posição X do mini-efeito (float)."))
            a.append(A(b + 0x14, 4, "f32", who + ": posição Y", "Posição Y do mini-efeito (float), confirmada."))
            a.append(A(b + 0x18, 4, "f32", who + ": posição Z", "Posição Z do mini-efeito (float), confirmada."))
        a.append(A(b + 0x1C, 4, "f32", who + ": tamanho 1", "Tamanho inicial. Se os tamanhos 2 e 3 forem 0, o mini-efeito fica sempre com este tamanho." + (" Zerar esconde as listras globais." if glob_ else "")))
        a.append(A(b + 0x20, 4, "f32", who + ": tamanho 2", "Tamanho para o qual cresce/encolhe, levando o 'tempo 1→2'."))
        a.append(A(b + 0x24, 4, "f32", who + ": tamanho 3", "Tamanho final, alcançado no 'tempo 2→3'."))
        a.append(A(b + 0x28, 4, "f32", who + ": tempo 1→2", "Tempo (float) para ir do tamanho 1 ao 2."))
        a.append(A(b + 0x2C, 4, "f32", who + ": tempo 2→3", "Tempo (float) para ir do tamanho 2 ao 3."))
        a.append(A(b + 0x30, 4, "f32", who + ": desconhecido", "Float de função desconhecida (0,08 em alguns efeitos)."))
        a.append(A(b + 0x34, 12, "raw", who + ": não usado", "Zeros nos efeitos analisados."))
    return a


# ---------------------------------------------------------------- shader (320 ou 192 bytes)
def shader(f, fname="shader"):
    a = []
    ch = ("vermelho (R)", "verde (G)", "azul (B)", "intensidade/alfa (A)")
    for r in range(len(f) // 16):
        if r < 12:
            s, rr = r // 3 + 1, r % 3 + 1
            for k in range(4):
                a.append(A(r * 16 + 4 * k, 4, "f32", "Sessão %d, linha %d: %s" % (s, rr, ch[k]),
                           "As 12 primeiras linhas do shader são 4 sessões de 3 linhas de cor RGBA em float (0 a 255). "
                           "As sessões 1 e 3 costumam ter as cores principais; as sessões 2 e 4 às vezes são pretas (0, 0, 0, N) e às vezes "
                           "têm uma cor secundária. É o que o 'RGB manual' edita."))
        else:
            for k in range(4):
                a.append(A(r * 16 + 4 * k, 4, "f32", "Linha %d: parâmetro %d" % (r + 1, k + 1),
                           "Da linha 13 em diante o shader guarda parâmetros entre 0 e 1 (não são cores; o antigo editor marcava 'Ignore'). "
                           "Função exata desconhecida."))
    return a


# ---------------------------------------------------------------- V00 (classe 0E)
def v00(f, fname="V00"):
    a = [A(0, 4, "raw", "Assinatura 'V000'", "Identifica o arquivo como V00: os efeitos BASE da classe 0E (esferas, círculos, brilhos do carregamento)."),
         A(4, 1, "u8", "Quantidade de sessões",
           "Quantas sessões este V00 tem. Cada sessão é um mini efeito dentro do V00. Quase sempre cada sessão tem 3 etapas "
           "(3 sessões = 9 etapas); a quantidade exata de cada sessão fica no byte +4 da entrada dela na parte inicial."),
         A(5, 3, "raw", "Desconhecido", "Normalmente 00 00 00."),
         A(8, 2, "u16", "Início das sessões gerais",
           "Offset (em bytes) onde começam as sessões 'gerais', com as etapas de posição, rotação, tamanho e cor. "
           "Sempre 32 + 32 × (quantidade de sessões): 64, 96, 128, 160... Antes disso fica a parte inicial."),
         A(10, 22, "raw", "Desconhecido", "Restante do cabeçalho de 32 bytes; zeros.")]
    if len(f) < 32:
        return a
    n = f[4]
    start = struct.unpack_from("<H", f, 8)[0]
    for i in range(n):
        o = 32 + 32 * i
        if o + 32 > len(f):
            break
        a.append(A(o, 1, "u8", "Parte inicial, sessão %d: imagem da textura" % (i + 1),
                   "Qual imagem do DBT do mini-efeito esta sessão usa (00 = primeira). Conferido nos 784 V00 dos modelos: sempre menor que a quantidade de imagens do DBT."))
        a.append(A(o + 1, 1, "u8", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Sempre 00."))
        a.append(A(o + 2, 1, "u8", "Parte inicial, sessão %d: byte de cor inversa (modo de cor)" % (i + 1),
                   "Como o jogo mistura a cor desta sessão com o que está atrás. Em 00 a cor é SUBTRAÍDA (cor inversa): é assim que se fazem efeitos negros "
                   ". 00 aparece em partes escuras do Ulti Hatchiyak, Big Bang Kamehameha, Final Shine e nos cortes do Janemba. "
                   "01, 02 e 03 são os modos claros (brilho), diferença ainda a estudar.",
                   {0: "cor inversa (efeito negro)", 1: "claro (o mais comum)", 2: "claro (variação)", 3: "claro (variação)"}))
        a.append(A(o + 3, 1, "u8", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Quase sempre 01."))
        a.append(A(o + 4, 1, "u8", "Parte inicial, sessão %d: quantidade de etapas" % (i + 1),
                   "Quantas etapas (quadros-chave de 64 bytes) esta sessão tem. Normalmente 3, mas alguns V00 têm sessões com 2, 4, 5 ou 8 etapas. "
                   "Conferido em todos os 267 V00 dos modelos do programa: a soma destes bytes é sempre o total de etapas do arquivo."))
        a.append(A(o + 5, 3, "raw", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Normalmente 02 00 FF."))
        a.append(A(o + 8, 2, "u16", "Parte inicial, sessão %d: provável duração (quadros)" % (i + 1),
                   "Valores redondos (20, 30, 60, 90, 120, 180, 330): parece a duração da sessão em quadros. A confirmar."))
        a.append(A(o + 10, 2, "raw", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Ainda não documentado."))
        a.append(A(o + 12, 1, "u8", "Parte inicial, sessão %d: colunas da folha de sprites" % (i + 1),
                   "Quando a textura é animada (bit 0x10 em +0x10): 0 = 2 colunas, 1 = 4 colunas; sempre 2 linhas (conferido nos 41 casos).",
                   {0: "2 × 2 (4 quadros)", 1: "4 × 2 (8 quadros)"}))
        a.append(A(o + 13, 3, "raw", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Ainda não documentado."))
        a.append(A(o + 16, 1, "flags", "Parte inicial, sessão %d: flags" % (i + 1),
                   "Bit 0x10 = a textura é uma folha de sprites que troca de quadro (texturas animadas). Outros bits ainda em estudo.",
                   {16: "textura animada (folha de sprites)"}))
        a.append(A(o + 17, 7, "raw", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Ainda não documentado."))
        a.append(A(o + 24, 1, "u8", "Parte inicial, sessão %d: ritmo da animação? (quadros por sprite)" % (i + 1),
                   "Nas texturas animadas costuma ser 2. A prévia usa como quadros por sprite (estimado)."))
        a.append(A(o + 25, 7, "raw", "Parte inicial, sessão %d: desconhecido" % (i + 1), "Ainda não documentado."))
    total = (len(f) - start) // 64 if start <= len(f) else 0
    counts = [f[32 + 32 * i + 4] for i in range(n) if 32 + 32 * i + 4 < len(f)]
    owner = []
    if sum(counts) == total:
        for si, c in enumerate(counts):
            owner += [(si + 1, j + 1) for j in range(c)]
    for k in range(total):
        o = start + 64 * k
        who = "Etapa %d" % (k + 1) + (" (sessão %d, etapa %d)" % owner[k] if owner else "")
        for j, ax in enumerate("XYZ"):
            a.append(A(o + 4 * j, 4, "f32", who + ": posição " + ax,
                       "1ª linha da etapa: posição XYZ do mini efeito, três floats seguidos (X, depois Y, depois Z)."))
        a.append(A(o + 12, 4, "f32", who + ": marcador da 1ª linha",
                   "As 3 primeiras linhas de cada etapa terminam com 00 00 80 3F (float 1). Parece só indicar a leitura do parâmetro."))
        for j, ax in enumerate("XYZ"):
            a.append(A(o + 16 + 4 * j, 4, "f32", who + ": rotação " + ax, "2ª linha da etapa: rotação do mini efeito (quando necessária), em floats."))
        a.append(A(o + 28, 4, "f32", who + ": marcador da 2ª linha", "Float 1 (00 00 80 3F), indicador de leitura."))
        for j, ax in enumerate("XYZ"):
            a.append(A(o + 32 + 4 * j, 4, "f32", who + ": tamanho " + ax, "3ª linha da etapa: tamanho do mini efeito, em floats."))
        a.append(A(o + 44, 4, "f32", who + ": marcador da 3ª linha", "Float 1 (00 00 80 3F), indicador de leitura."))
        a.append(A(o + 48, 4, "rgba8", who + ": cor RGBA",
                   "4ª linha da etapa: os 4 primeiros bytes são Vermelho, Verde, Azul e Alfa, de 0 a 255. É o que a pintura do programa altera nos V00."))
        a.append(A(o + 52, 1, "u8", who + ": momento de aparição", "O 5º byte da 4ª linha define o MOMENTO em que esta etapa aparece."))
        a.append(A(o + 53, 11, "raw", who + ": desconhecido", "Restante da 4ª linha; zeros nos exemplos."))
    rest = start + 64 * total
    if rest < len(f):
        a.append(A(rest, len(f) - rest, "raw", "Final do arquivo", "Bytes depois da última etapa completa; normalmente zeros."))
    return a


# ---------------------------------------------------------------- classe 02 (saídas de luz)
def anim02(f, fname="classe 02"):
    """Documentação do Vras: animação das Saídas de Luz. Até 10 partes de 120 bytes; quantidade em 1200."""
    a = []
    etapa = ("início", "segunda parte", "final")
    for s in range(min(10, len(f) // 120)):
        b = s * 120
        P = "Parte %d: " % (s + 1)
        for j, o in enumerate((0, 16, 32)):
            nm = etapa[j]
            a.append(A(b + o, 4, "f32", P + "comprimento (%s)" % nm, "Float: comprimento (largo) da imagem do efeito na %s da sequência." % nm))
            a.append(A(b + o + 4, 4, "f32", P + "largura (%s)" % nm, "Float: largura (ancho) da imagem do efeito na %s da sequência." % nm))
            a.append(A(b + o + 8, 4, "f32", P + "altura? (%s)" % nm, "Float: provável altura da imagem; mudar não mostra diferença visível."))
            a.append(A(b + o + 12, 4, "rgba8", P + "cor RGBA (%s)" % nm,
                       "Vermelho, Verde, Azul e Intensidade em bytes (0 a 255) na %s da sequência. É o que a pintura do programa altera." % nm))
        a.append(A(b + 48, 48, "raw", P + "floats desconhecidos", "Sempre 0 ou 1; não parecem ter função muito visível no efeito."))
        a.append(A(b + 96, 4, "f32", P + "rotação inicial", "Float: onde começa a rotação do efeito."))
        a.append(A(b + 100, 4, "f32", P + "velocidade de rotação", "Float: velocidade com que o efeito gira."))
        a.append(A(b + 104, 4, "f32", P + "tempo da 2ª parte para a 3ª", "Float: tempo para passar da segunda parte da sequência para a terceira (se for 0 o efeito não aparece)."))
        a.append(A(b + 108, 4, "f32", P + "tempo do início para a 2ª parte", "Float: tempo para passar do início da sequência para a segunda parte."))
        a.append(A(b + 112, 1, "u8", P + "ordem", "Int que começa em 0 e soma 2 a cada parte (0, 2, 4, 6...); na última parte soma 3."))
        a.append(A(b + 113, 1, "u8", P + "preenchimento?", "Provável preenchimento."))
        a.append(A(b + 114, 1, "u8", P + "sempre 01", "Sempre 01; se não for, o efeito buga.", {1: "correto"}))
        a.append(A(b + 115, 5, "raw", P + "preenchimento?", "Provável preenchimento."))
    if len(f) >= 1208:
        a.append(A(1200, 4, "u32", "Quantidade de partes", "Int: quantas partes o efeito tem (máximo 10)."))
        a.append(A(1204, 4, "u32", "Sempre 1", "Int: sempre 1 segundo a documentação (5 visto na Cena Especial do Kamehameha Pai e Filho)."))
    if len(f) > 1208:
        a.append(A(1208, len(f) - 1208, "raw", "Preenchimento", "Bytes de preenchimento."))
    return a


def shape05(f, fname="forma da classe 05"):
    a = [A(0, len(f), "raw", "Forma (shape) da classe 05", "Define o formato/animação do mini efeito; quase toda a estrutura ainda não foi documentada.")]
    if len(f) > 0x24:
        a.append(A(0x20, 2, "u16", "Quantidade de partículas (hipótese)",
                   "Quantas cópias da textura a forma solta: 1 a 20 nos modelos (Bolinhas 7, Madam 4). A prévia desenha essas cópias flutuando."))
    if len(f) > 10:
        a.append(A(10, 1, "u8", "Modo de cor (hipótese)",
                   "01 = brilho (soma a cor; a grande maioria). 00 aparece nas fumaças, poeiras e partes quase pretas (Assault Tornado, explosão, "
                   "Kamehameha Pai e Filho): parece a mistura normal, em que o preto aparece. O programa usa 00 no efeito negro da classe 05 (experimental).",
                   {0: "mistura normal (preto aparece)", 1: "brilho (soma)", 2: "visto em um feixe e em um projétil dos modelos", 3: "visto nas argolas e no Trunks Dome"}))
    return a


# ---------------------------------------------------------------- DBT (texturas)
def dbt(f, fname="DBT"):
    a = [A(0, 4, "u32", "Quantidade de imagens", "Quantas texturas este DBT contém (cada uma com sua paleta)."),
         A(4, 4, "u32", "Desconhecido", "Normalmente 8."),
         A(8, 4, "u32", "Soma dos blocos de pixels", "Soma dos campos 'blocos de pixels' de todas as imagens (às vezes somada a um endereço usado pelo jogo)."),
         A(12, 4, "u32", "Soma dos blocos de paleta", "Soma dos campos 'blocos de paleta' de todas as imagens."),
         A(16, 16, "raw", "Endereços usados pelo jogo", "Ponteiros preenchidos em tempo de execução; não precisam ser editados.")]
    for i, im in enumerate(dbt_info(f)):
        b = 0x20 + 0x40 * i
        cores = 256 if im["psm"] == 0x13 else 16
        who = "Imagem %d (%d×%d, %d cores)" % (i, im["w"], im["h"], cores)
        a += [A(b, 4, "u32", who + ": offset/4 dos pixels", "Posição do pacote de pixels dividida por 4."),
              A(b + 4, 4, "u32", who + ": offset/4 da paleta", "Posição do pacote da paleta dividida por 4."),
              A(b + 8, 4, "u32", who + ": tamanho do pacote de pixels", "Bytes do pacote de pixels (dados + 128 bytes de comandos do PS2)."),
              A(b + 12, 4, "u32", who + ": tamanho do pacote de paleta", "Bytes do pacote da paleta."),
              A(b + 16, 4, "u32", who + ": blocos de pixels", "Tamanho dos pixels em blocos de 256 bytes."),
              A(b + 20, 4, "u32", who + ": blocos de paleta", "4 para paleta de 256 cores, 1 para 16 cores."),
              A(b + 24, 8, "raw", who + ": desconhecido", "Cresce com o tamanho da imagem (1 para 128×128, 2 para 256×256)."),
              A(b + 32, 16, "raw", who + ": desconhecido", "Sem função conhecida."),
              A(b + 48, 8, "raw", who + ": registrador TEX0 do PS2",
                "Formato (PSM: 0x13 = 256 cores, 0x14 = 16 cores), largura e altura (em potência de 2) da textura."),
              A(b + 56, 8, "raw", who + ": endereços usados pelo jogo", "Ponteiros de tempo de execução.")]
        if im["pixels"]:
            a.append(A(im["pixels"][0], im["pixels"][1], "raw", who + ": pixels",
                       "Índices de cor de cada pixel, embaralhados no formato de memória do PS2. Use a janela de Texturas para ver/importar."))
        if im["clut"]:
            a.append(A(im["clut"][0], im["clut"][1], "raw", who + ": paleta RGBA",
                       "Cores da textura: 4 bytes por cor (R, G, B, A). O alfa do PS2 vai de 0 a 128 (128 = opaco)."))
    return a


# ---------------------------------------------------------------- 02_.dat (cena)
def scene(f, fname="02_.dat"):
    a = []
    for mp in range(SCENE_MAPS):
        nm = MAP_NAMES[mp] if mp < len(MAP_NAMES) else "?"
        for ev in range(SCENE_EVENTS):
            o = (mp * SCENE_EVENTS + ev) * 16
            who = "Mapa %02d (%s), evento %d" % (mp, nm, ev + 1)
            a.append(A(o, 4, "f32", who + ": posição X", "Posição X global dos dois personagens durante a ceninha (confirmado)."))
            a.append(A(o + 4, 4, "f32", who + ": posição Y (altura)",
                       "Altura GLOBAL dos dois personagens durante a ceninha, neste mapa e neste evento. -160 nas cenas que jogam para o alto."))
            a.append(A(o + 8, 4, "f32", who + ": posição Z", "Posição Z global dos dois personagens a partir do centro do mapa."))
            a.append(A(o + 12, 4, "f32", who + ": não usado", "Último float da linha; zero nos arquivos analisados."))
    a.append(A(2800, 16, "raw", "Última linha", "Sempre vazia. O 02_.dat tem 2800 bytes úteis: 35 mapas × 5 eventos × 16 bytes. "
                                                    "Efeitos sem ceninha não precisam de 02_.dat (o Super Energy Wave Volley do Vegeta não tem)."))
    return a


def unknown(text):
    def f(data, fname=""):
        return [A(0, len(data), "raw", "Estrutura não documentada", text)]
    return f


def value_text(data, ann, off):
    """Texto com o valor atual do campo e o significado, se conhecido."""
    s, size, kind, title, text, known = ann
    chunk = bytes(data[s:s + size])
    lines = []
    if kind == "u8" or kind == "flags":
        v = chunk[0]
        lines.append("Valor atual: %d (0x%02X, binário %s)" % (v, v, format(v, "08b")))
        if kind == "flags":
            on = [b for b in (1, 2, 4, 8, 16, 32, 64, 128) if v & b]
            lines.append("Flags ligadas: " + (", ".join("%d" % b for b in on) if on else "nenhuma"))
            for b in on:
                lines.append("  • %d = %s" % (b, known.get(b, "?")))
        elif v in known:
            lines.append("Significado deste valor: " + known[v])
    elif kind == "u16" and len(chunk) == 2:
        lines.append("Valor atual: %d" % struct.unpack("<H", chunk)[0])
    elif kind == "u32" and len(chunk) == 4:
        lines.append("Valor atual: %d (0x%X)" % (struct.unpack("<I", chunk)[0], struct.unpack("<I", chunk)[0]))
    elif kind == "f32" and len(chunk) == 4:
        lines.append("Valor atual: %g (float de 4 bytes: %s)" % (struct.unpack("<f", chunk)[0], chunk.hex(" ").upper()))
    elif kind == "rgba8" and len(chunk) == 4:
        lines.append("Cor atual: R %d, G %d, B %d, A %d  (#%02X%02X%02X)" % (chunk[0], chunk[1], chunk[2], chunk[3], chunk[0], chunk[1], chunk[2]))
    else:
        lines.append("Bytes: " + (chunk[:16].hex(" ").upper() + (" …" if len(chunk) > 16 else "")))
    if known and kind != "flags":
        lines.append("")
        lines.append("Valores conhecidos:")
        for k in sorted(known):
            lines.append("  %s = %s" % (("%02X" % k) if isinstance(k, int) else k, known[k]))
    if size > 1:
        lines.append("")
        lines.append("Este campo ocupa %d bytes (0x%04X–0x%04X); você está no byte %d dele." % (size, s, s + size - 1, off - s + 1))
    return "\n".join(lines)


def value_short(data, ann):
    """Valor interpretado, curto, para a coluna 'Valor' do glossário."""
    s, size, kind, title, text, known = ann
    chunk = bytes(data[s:s + size])
    try:
        if kind in ("u8", "flags") and chunk:
            v = chunk[0]
            return ("%d (%s)" % (v, known[v])) if v in known and kind == "u8" else str(v)
        if kind == "u16" and len(chunk) == 2:
            return str(struct.unpack("<H", chunk)[0])
        if kind == "u32" and len(chunk) == 4:
            return str(struct.unpack("<I", chunk)[0])
        if kind == "f32" and len(chunk) == 4:
            return "%g" % struct.unpack("<f", chunk)[0]
        if kind == "rgba8" and len(chunk) == 4:
            return "#%02X%02X%02X A%d" % (chunk[0], chunk[1], chunk[2], chunk[3])
    except (struct.error, IndexError):
        pass
    return chunk[:6].hex(" ").upper() + (" …" if len(chunk) > 6 else "")
