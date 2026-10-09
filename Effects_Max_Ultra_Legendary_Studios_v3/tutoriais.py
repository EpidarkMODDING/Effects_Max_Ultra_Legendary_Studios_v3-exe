# -*- coding: utf-8 -*-
"""Tutoriais do Effects Max Ultra Legendary Studios, explicados bem devagar, como para uma criança de 5 anos."""

TOPICS = [
("1. O que é este programa?",
"""Imagine que cada golpe do jogo é um bolo de festa.

O arquivo de efeito (.pak) é a caixa do bolo. Dentro dela tem várias camadas: brilhos, bolinhas, raios, a aura... Cada camada é um MINI-EFEITO.

Este programa abre a caixa, mostra todas as camadas numa lista e deixa você trocar a cor, o tamanho, juntar camadas de outros bolos, esconder camadas e muito mais.

Regra de ouro: sempre teste numa CÓPIA do arquivo. Se algo der errado, o programa também guarda um backup (.bak) e você pode apertar Ctrl+Z para desfazer."""),

("2. Abrir e salvar",
"""ABRIR: menu Arquivo → Abrir .pak. Escolha o arquivo do efeito (por exemplo 02_skill_003.pak).

SALVAR: Ctrl+S ou Arquivo → Salvar. Na primeira vez, o programa cria uma cópia de segurança com o final .bak.

SALVAR COMO: salva com outro nome, sem mexer no original.

DESFAZER: Ctrl+Z volta o último passo, como apagar o último risco de um desenho."""),

("3. Pacote completo do personagem (ex.: Goku_eff.pak)",
"""O Goku_eff.pak é uma caixa GRANDE com várias caixas pequenas dentro: um efeito para cada golpe, mais os efeitos comuns (aura de carga, kidan...).

Quando você abre essa caixa grande, o programa mostra uma listinha com todas as caixas pequenas. Clique duas vezes na que quiser.

Quando você salvar, o efeito volta para dentro da caixa grande, no mesmo lugar. Se usar 'Salvar como', ele sai sozinho, como um arquivo separado."""),

("4. A lista de mini-efeitos",
"""À esquerda fica a lista com todas as camadas do efeito. Cada linha é um mini-efeito.

• Classe: o TIPO da camada (00 global, 02 saídas de luz, 05 complementares, 09 rodelas, 0E V00, 10 iluminação, 11 caudas/feixes, 12 raios).
• Grupo: o MOMENTO em que a camada aparece (grupo 0 = carregando, grupo 1 = soltando o golpe...).
• DBT/Tex: qual figurinha (textura) ela usa.
• Cor: a cor principal dela.

A caixinha ☐ do começo da linha serve para MARCAR. Muitas ferramentas trabalham só nos marcados. Em 'Marcar grupos' você marca um grupo inteiro de uma vez."""),

("5. Classes e grupos (o que é cada coisa)",
"""CLASSE é o tipo do brinquedo: carrinho, boneca, bola...
GRUPO é a hora de brincar: de manhã, de tarde, de noite.

Classes:
• 00 global — as listras brancas que todo golpe tem (não dá para tirar, só esconder).
• 02 — saídas de luz (aquelas luzes do Kamehameha).
• 05 — complementos: faíscas, a bola na ponta do feixe, o rastro de velocidade, auras.
• 09 — rodelas que vão junto com o feixe ou projétil.
• 0E — V00: a base do carregamento (esferas, círculos).
• 10 — iluminação e sombra.
• 11 — a cauda do feixe e de projéteis compridos.
• 12 — raios em volta do personagem.

Grupos:
• 0 — carregando o golpe.
• 1 — soltando o golpe.
• 2 — saídas de luz / fim.
• 3 — auras.
• 4 — explosão no oponente (evento Vfx 5).
• 5 — iluminação."""),

("6. Colorir o efeito",
"""Aba CORES.

'Colorir o efeito inteiro': escolha uma cor e pronto, o golpe todo muda de cor. As partes claras continuam claras e o núcleo branco continua branco, igual a pintar só a borda do desenho.

'Colorir só os marcados': pinta só as camadas que você marcou na lista.

'Colorir grupo': pinta só um grupo (por exemplo, só o carregamento).

'Manter saturação original': troca só o tom (vermelho vira azul), sem deixar a cor mais forte ou mais fraca.

'Colorir também as texturas': pinta também as figurinhas (DBT)."""),

("7. Forçar cor (efeitos muito brancos)",
"""Alguns golpes são quase todos brancos. Branco não tem cor para trocar, então nada muda.

O controle 'Forçar cor em partes brancas/cinzas' é como passar um lápis de cor por cima do branco. 0% não pinta o branco; 100% pinta tudo, até o centro.

Comece com uns 40% e vá aumentando até ficar bonito."""),

("8. Colorir com contraste",
"""O jogo original não pinta tudo de uma cor só: um golpe roxo tem pedacinhos azuis, um laranja tem pedacinhos vermelhos. Fica mais bonito e dá para ver as camadas.

'Colorir com contraste' faz isso sozinho: você escolhe a cor principal e o programa pinta algumas partes com uma cor 'vizinha'.

O 'desvio' diz quão vizinha: -35 é o padrão (roxo → azul, laranja → vermelho). Números positivos vão para o outro lado."""),

("9. RGB manual, Inverter e Copiar",
"""Clique numa camada da lista. Embaixo, em 'RGB manual', aparecem as cores dela em números: R (vermelho), G (verde), B (azul) e A (intensidade).

Você pode digitar os números ou clicar no quadradinho colorido para escolher a cor.

INVERTER: troca uma cor com a outra em todas as linhas. Ex.: Cor 1 = Vermelho, Cor 2 = Azul → o que era vermelho vira azul.
COPIAR: copia a Cor 1 para a Cor 2.

Depois clique em APLICAR para gravar."""),

("10. Reduzir intensidade / opacidade",
"""Às vezes o golpe fica 'estourado', muito forte, tapando tudo.

'Reduzir em X%' deixa ele mais suave:
• Opacidade: mais transparente, como um vidro.
• Brilho: menos luz, menos branco estourado.

Você escolhe se é no efeito todo ou só em alguns grupos."""),

("11. Reduzir cores das texturas (deixar o arquivo leve)",
"""Arquivo muito pesado? As figurinhas (texturas) são as que mais pesam.

'Reduzir cores (256 → 16)' troca as figurinhas de 256 cores por 16 cores. O arquivo fica quase com metade do tamanho (o Madam vai de 153 KB para 87 KB).

O desenho continua igual; só os degradês podem ficar com 'degrauzinhos'."""),

("12. Tamanho e tempo",
"""Cada camada tem até 3 tamanhos:
Tamanho 1 → Tamanho 2 → Tamanho 3, com um tempo entre eles. É assim que um efeito nasce pequeno e cresce.

• 'Escalar os marcados × 1.5' deixa as camadas marcadas 50% maiores (0.5 = metade).
• 'Escalar um grupo inteiro' faz o mesmo com um grupo.
• Padrões de crescimento: 'Argola Turles' (nasce e cresce) e 'Contrai e explode'. 'Reverter' faz ao contrário.

Os botões '?' ao lado de cada campo explicam o que ele faz."""),

("13. Grupos: remover ou ocultar",
"""Aba GRUPOS.

REMOVER tira as camadas do arquivo (ele fica mais leve).
TORNAR INVISÍVEL deixa a camada lá, funcionando, mas sem aparecer. Use isso quando a camada é a que acerta o oponente: assim o golpe continua causando dano."""),

("14. Combinar efeitos",
"""Aba COMBINAR. É como pegar a cobertura de um bolo e colocar em outro.

1. Clique em 'Abrir efeito de origem' e escolha o outro golpe.
2. Marque as camadas ou grupos que você quer trazer.
3. Escolha o que fazer com o que já existe (o recomendado é substituir os mesmos grupos, para não duplicar).
4. Clique em 'Aplicar combinação'.

As texturas vêm junto e os números são arrumados sozinhos."""),

("15. Comportamento (formatos)",
"""Aba COMPORTAMENTO. Aqui você muda o JEITO que o golpe sai: área, feixe, projétil, vertical, barragem, argolas...

1. Escolha um formato no botão (eles estão em grupos, como pastas).
2. O botão 🖼 mostra uma foto de como ele fica.
3. 'Comportamento + formato' traz o desenho do disparo do modelo.
   'Só comportamento' mantém o desenho do SEU golpe e muda só o jeito de sair.
4. Clique em aplicar.

O carregamento do seu golpe é mantido. Lembre: o personagem também precisa ter o parâmetro do golpe certo.

Aqui também ficam: 'Converter em barragem' e 'Ocultar listras brancas'."""),

("16. Pré-disparo",
"""Pré-disparo é o que acontece ANTES do golpe sair (o carregamento).

Na aba Comportamento, em 'Formatos pré-disparo', escolha um (ex.: Cortes Trunks, Bola de Fogo 4 Estrelas) e clique em aplicar. Só o carregamento muda; o disparo continua o seu."""),

("17. Extras (enfeites)",
"""Aba EXTRAS. São enfeites que você liga e desliga: auras, bolinhas, raios, redemoinhos, rodelas...

Marque os que quiser e clique em 'Aplicar extras'. Para tirar, desmarque e aplique de novo.

Eles podem ser pintados com a cor principal do seu golpe. Alguns só funcionam em golpes com feixe (aparece escrito ao lado)."""),

("18. Cena ao acertar (ceninha)",
"""Aba CENA AO ACERTAR.

• Sem cena / Manter no chão / Jogar pro ar: escolhe o que acontece com os personagens quando o golpe acerta.
• 'Editar 02_.dat por mapa': ajusta a altura e a posição dos personagens em cada mapa.
• 'Como o golpe aparece na ceninha': feixe, projétil, feixe vertical ou barragem.
• 'Grupo 01 na ceninha': mantém ou esconde as partes do lançamento durante a ceninha.
• 'Adicionar explosão': coloca a explosão (Vfx 5) no oponente, com a cor do seu golpe.

Se o golpe NÃO tem ceninha, escolha 'Sem cena': o arquivo fica 2,8 KB mais leve."""),

("19. Auras (01_charge_aura.pak)",
"""Abra um 01_charge_aura.pak e o programa entra no modo aura: aparecem só as abas úteis.

Na aba 'Formato da aura' você troca a aura inteira (os formatos da lista) e ela é pintada com a cor da aura que você já tinha."""),

("20. Suportes / Skills",
"""Arquivos 00_skill_001, 01_skill_002, 00_effect_skill_1 e 01_effect_skill_2 são as skills de suporte (paralisia, Taiyoken, barreira...).

• Aba Suporte/Skills: troca o efeito por outro formato de suporte.
• Aba Parâmetros de suporte: 'Disparar até o adversário', 'Ficar até usar um especial' e os números de cada suporte."""),

("21. Flags",
"""Aba FLAGS. São interruptores do 03_.dat. Cada um tem um número (1, 2, 4, 8, 16, 32, 64, 128) e o programa soma sozinho.

Exemplos: 32 = o efeito fica sempre na frente da câmera; 64 = a posição fica fixa; 128 = arruma as argolas do Makankosappo em choque de poderes.

Marque, olhe o valor 'novo' e clique em Aplicar."""),

("22. Texturas",
"""Botão TEXTURAS no topo. Mostra todas as figurinhas do efeito.

• Clique numa imagem para vê-la grande.
• 'Exportar PNG' salva a figura no computador para você editar.
• 'Importar PNG' coloca a sua figura de volta (o programa ajusta o tamanho e as cores sozinho).
• 'Mudar cor' pinta só aquela figurinha.
• Embaixo aparecem as camadas que usam a figura, com posição e tamanho para editar.
• 'Ocultar tudo que usa este DBT' esconde todas as camadas que usam aquela figura."""),

("23. Editor 3D (quadros-chave)",
"""Botão EDITOR 3D no topo. É como um palco de teatro visto de cima e de lado.

• Cada CÍRCULO é uma camada do efeito: o lugar onde ela está, o tamanho dela e a cor.
• À esquerda fica a lista de objetos. Os V00 (classe 0E) aparecem divididos em sessões.
• Embaixo fica a LINHA DO TEMPO. Cada losango é um QUADRO-CHAVE: uma 'foto' de como a camada está naquele momento.
  Entre um quadro-chave e outro, o programa mostra o caminho (linha amarela tracejada).
• Aperte ▶ (ou Espaço) para ver o filme.

Como mexer:
1. Clique num círculo ou num quadradinho amarelo (um quadro-chave do caminho) e ARRASTE para mudar a posição. Escolha antes em qual plano arrastar (XZ é o chão).
2. Arraste um losango da linha do tempo para a direita ou esquerda para mudar QUANDO aquele quadro-chave acontece.
3. À direita dá para digitar posição, rotação, tamanho, cor e momento exatos e clicar em Aplicar.

Girar a câmera: arraste num lugar vazio. Mover a câmera: botão direito. Zoom: rodinha do mouse.

A vista é um esquema (círculos), não o desenho real do efeito."""),

("24. Editor hexadecimal",
"""Botão HEXADECIMAL. Mostra os bytes (os números escondidos) de cada arquivo do efeito.

1. Escolha o arquivo em cima (03_ parâmetros, shaders, V00, DBT, 02_ cena...).
2. Clique em qualquer byte.
3. À direita aparece: a que parte DAQUELE arquivo ele pertence, o que ele faz, o valor dele e os valores conhecidos. O campo inteiro fica amarelo.

Para mudar, digite outro número no lugar e clique em Aplicar. Se a mudança quebrar o efeito, o programa avisa e não aplica.

Também dá para abrir um .dat solto pelo menu Ferramentas."""),

("25. Modelos protegidos",
"""Os modelos (formatos, extras, auras, suportes) ficam guardados dentro do recursos.dat, como num cofre. Você pode usá-los nos seus efeitos, mas não dá para salvar um modelo sem mudar nada.

Para colocar seus próprios modelos, crie as pastas 'modelos', 'extras', 'auras'... ao lado do programa e coloque os .pak lá."""),

("26. Exibição, idioma e modo noturno",
"""Menu EXIBIÇÃO: tamanho da janela, escala (letras maiores ou menores), posição do painel e MODO NOTURNO (fundo escuro, bom para os olhos à noite).

Menu IDIOMA: português, espanhol ou inglês.

Na primeira vez que abre o programa, ele já pergunta tudo isso."""),
]


# ================================================================ v1.5
_NEW = {
"4.": ("4. A lista de mini-efeitos",
"""A lista da esquerda mostra cada camada do bolo, uma por linha. As colunas, da esquerda para a direita:

✓ Marcar/Desmarcar: clique no quadradinho para marcar a camada.
# ID do mini efeito: o número dele (passe o mouse em cima do título da coluna para ver a dica).
DBT/Textura: qual arquivo de textura e qual imagem ele usa.
Classe: o tipo da camada (Linhas de Foco, Saídas de Luz, Complementos/Acabamentos, Destaque, V00, Iluminação, Cauda/Feixe, Raios).
Estágio de invocação: QUANDO a camada aparece (Pré-Disparo, Pós-Disparo, Aura...).
Estágio de desaparecimento: QUANDO ela some. 05 = some na ceninha.
Orientação posicional: para onde ela 'olha' (05 = vai atrás do adversário e causa dano).

Botão DIREITO numa linha abre um menu: ver as texturas dela, abrir no editor hexadecimal (o arquivo dela ou os parâmetros no 03_.dat) e ver no Editor 3D.

'Marcar estágios' em cima da lista marca de uma vez todas as camadas de um estágio."""),
"5.": ("5. Classes e estágios (o que é cada coisa)",
"""CLASSE é o tipo de peça de LEGO:
• Linhas de Foco: as listras brancas que todo golpe tem. Não dá para tirar, só esconder.
• Saídas de Luz: os feixes de luz dos Kamehamehas.
• Complementos/Acabamentos: faíscas, a bola na ponta do feixe, rastros.
• Destaque: rodelas e raios em volta do feixe, coisas que mostram a força do golpe.
• V00: brilhos base, com etapas que se mexem.
• Iluminação, Cauda/Feixe e Raios.

ESTÁGIO é o MOMENTO da festa:
• Pré-Disparo: enquanto carrega.
• Pós-Disparo: depois que o golpe sai.
• Aura: em volta do personagem.
• Iluminação: a luz que cobre a sombra.

Aperte 'Classes e estágios' no topo para ver tudo."""),
"13.": ("13. Esconder ou remover um estágio inteiro",
"""A antiga aba Grupos saiu. Agora é assim:
1. Em 'Marcar estágios', em cima da lista, marque o estágio (por exemplo Pré-Disparo).
2. Clique em 'Ocultar marcados' (fica invisível, mas continua lá) ou 'Remover marcados' (sai do arquivo).

Pronto! É o mesmo resultado, com menos cliques."""),
"15.": ("15. Pré-disparo e disparo",
"""A aba 'Pré-disparo e disparo' tem duas partes, uma embaixo da outra:

1. PRÉ-DISPARO (em cima): escolha um formato pronto OU clique em '...ou o pré-disparo de outro .pak' e escolha QUALQUER efeito. O programa pega só as partes do estágio 0 (o carregamento) desse arquivo e coloca no seu.

2. DISPARO (embaixo): escolha um formato pronto (ou '...ou de outro .pak') e veja quantas partes ele tem em cada estágio. Clique em 'Aplicar o disparo escolhido'. O Pré-Disparo do seu efeito fica igual.

Trocar várias vezes não acumula texturas repetidas: quando o efeito já tem a mesma imagem (só com outra cor), o programa reaproveita a que já existe.

Os dois podem pintar o que veio com a cor do seu efeito."""),
"16.": ("16. Pré-disparo de outro efeito",
"""Gostou do carregamento de outro golpe? Fácil:
1. Aba 'Pré-disparo e disparo', parte 2.
2. '...ou o pré-disparo de outro .pak' e escolha o arquivo.
3. Clique em 'Trocar o Pré-Disparo (estágio 0) por este'.

O carregamento antigo sai e o novo entra, com as texturas junto."""),
"17.": ("17. Complementares (enfeites)",
"""A aba 'Complementares' (antiga Extras) põe enfeites sem mudar o formato do golpe. As seções agora têm o nome do estágio:
• Aura
• Pré-Disparo
• Pré-Disparo + Pós-Disparo
• Pós-Disparo

Nas auras você escolhe onde elas entram: no Pré-Disparo (como antes) ou no estágio 3, Aura (como no golpe original).

NOVO: 'Importar complementar de outro .pak'. Escolha o arquivo, marque as partes, diga em qual seção elas entram e clique em Importar. Se marcar 'Guardar na lista', o enfeite fica salvo na pasta extras e aparece sempre na aba."""),
"21.": ("21. Avançado (flags e colisão)",
"""A aba Avançado (antiga Flags) tem três partes:
1. Flags das Linhas de Foco (o primeiro bloco do 03_.dat).
2. Flags dos marcados: cada mini efeito tem as suas. A coluna mostra quantos marcados têm cada flag; Ligar/Desligar muda em todos.
3. Cabeçalho do 03_.dat: colisão base (0x08), colisões extras e a parte de colisão de tipo desconhecido."""),
}
_ADD = [
("27. Efeitos negros",
"""Por que pintar de preto não funciona? Porque o jogo SOMA a luz do efeito com o que está atrás. Somar preto é somar nada, aí some.

O truque: o V00 tem um byte de 'cor inversa'. Em 0, o jogo TIRA a cor em vez de somar. Aí precisa de cor clara para tirar bastante e sobrar preto.

Como fazer:
1. Marque as partes (aba Cores, seção 'Efeitos negros').
2. Escolha o tom da sombra (preto, roxo bem escuro...) e a força.
3. Clique em 'Transformar em efeito negro'.

O programa liga a cor inversa, ajusta as cores e deixa as texturas em cinza para tirar a cor por igual. Nos Complementos/Acabamentos (experimental) ele usa a mistura normal, a mesma das fumaças.

Embaixo aparece a tabela com o byte de cada sessão: 'Pôr em 0' e 'Restaurar', um por um."""),
("28. Colorir com degradê",
"""Em vez de uma cor só, o efeito ganha DUAS ou TRÊS cores que seguem a textura:
• bordas e partes escuras: a 1ª cor;
• meio: a 2ª cor;
• núcleo claro: a 3ª cor.

1. Aba Cores, 'Colorir com degradê'.
2. Escolha as cores (ou um pronto: Final Flash, Big Bang, Hakai...).
3. Veja o antes e depois numa textura do próprio efeito.
4. Aplicar.

Com 'Manter o brilho original' a forma do brilho não muda, só a cor."""),
("29. Escolher cor (roda, imagem e paleta)",
"""Toda vez que o programa pede uma cor, abre o seletor novo:
• Roda de cor: escolha o tom na barra e o claro/escuro no quadrado.
• Imagem de referência: carregue um PNG e clique na cor que quiser (conta-gotas). Não precisa sair do programa para achar o tom.
• Paleta da textura: clique numa cor de qualquer textura do efeito.
As últimas cores ficam em 'Recentes'."""),
("30. Prévia do crescimento",
"""Na aba Tamanho e tempo, em cima, aparece a prévia: as partes marcadas (ou a selecionada) com a TEXTURA e a cor delas, crescendo do tamanho 1 ao 3.
Aperte ▶ ou arraste a barra. Embaixo, a curva mostra o tamanho de cada parte ao longo do tempo.
O Editor 3D usa as mesmas texturas e deixa ligar e desligar cada estágio."""),
]
TOPICS = [(_NEW[t.split(" ", 1)[0]] if t.split(" ", 1)[0] in _NEW else (t, b)) for t, b in TOPICS] + _ADD


# ================================================================ v1.6
_NEW16 = {
"27.": ("27. Efeitos negros",
"""Por que pintar de preto não funciona? Porque quase todo efeito do jogo SOMA a luz com o que está atrás. Somar preto é somar nada, aí a parte fica transparente.

Para o preto aparecer, a parte precisa parar de somar luz. É isso que 'Preto de verdade' faz:
• Complementos/Acabamentos passam para a mistura normal (a mesma das fumaças), o shader para de tingir e o branco da textura vira preto.
• Nos V00, a parte colorida continua numa camada e uma cópia escurece o miolo.
• As outras classes ainda só perdem o branco.

A cor que fica é a própria cor da textura sem o branco, então o tom continua perto do original.

Na janela de Texturas também tem o botão 'Efeito negro', para uma imagem ou o DBT inteiro."""),
}
_ADD16 = [
("31. Backup e histórico",
"""A aba 'Backup e histórico' guarda tudo o que você fez, uma ação por linha.
• Desfazer (Ctrl+Z) e Refazer (Ctrl+Y).
• Clique numa linha e em 'Voltar para antes da ação selecionada' para desfazer várias de uma vez.

Ao salvar, o arquivo antigo vai para a pasta 'backups' do programa, separado por EFF e por arquivo, com data e hora. Nada fica na pasta do EFF, então o Sparking Studio exporta sem precisar limpar."""),
("32. Analisar animação",
"""Menu Ferramentas, 'Analisar animação'. Abra o .anm ou .canm do golpe (eventos 1, 2, 3 juntos, porque continuam o mesmo ataque).

Você vê:
• cada Vfx da animação e o estágio que ele chama (Vfx 1 = estágio 0, Vfx 2 = estágio 1... Vfx 6 = estágio 5);
• em que quadro e em qual osso (mãos, cintura, utility...);
• quais partes do seu efeito aparecem ali e quando, somando o atraso;
• estágios que nenhuma animação chama (essas partes nunca aparecem).

É assim que dá para descobrir efeitos 'escondidos' e criar golpes em várias etapas."""),
("33. Hitbox no Editor 3D",
"""No Editor 3D, aba Hitbox:
• a esfera vermelha é a colisão base do golpe (0x08 do cabeçalho);
• a caixa laranja mostra as colisões extras (interpretação ainda em teste).
Mude os números e aperte Enter, ou use ×1.25 e ×0.8 para aumentar ou diminuir a base. Tudo entra no histórico."""),
]
TOPICS = [(_NEW16[t.split(" ", 1)[0]] if t.split(" ", 1)[0] in _NEW16 else (t, b)) for t, b in TOPICS] + _ADD16
