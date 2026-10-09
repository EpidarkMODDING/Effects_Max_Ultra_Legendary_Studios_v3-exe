# -*- coding: utf-8 -*-
"""
BT3 Effect Studio - núcleo (leitura/escrita de .pak de efeitos de Budokai Tenkaichi 3)
Formato documentado pela equipe da Ariel Sofia + análise da Kaya.
"""
import os, struct, copy, colorsys

# (tamanho do shape, tamanho do shader) por categoria; None = categoria sem par shape/shader
SHAPE_SHADER = {0x05: (768, 320), 0x09: (640, 320), 0x0A: (576, 320), 0x0F: (448, 320),
                0x10: (192, 192), 0x11: (192, 192), 0x12: (512, 320)}
SPECIAL_TYPES = {0x00: "sem arquivos", 0x02: "animação (1216 bytes)", 0x0E: "V00"}
KNOWN_TYPES = set(SHAPE_SHADER) | set(SPECIAL_TYPES)

# linhas de cor dentro do shader float (RGBA 0-255, 4 floats por linha):
# 4 sessões de 3 linhas = linhas 0 a 11. As linhas 12+ são parâmetros (0 a 1), não cores.
SHADER_COLOR_ROWS = tuple(range(12))
MIN_COLOR = 2.0   # linhas com R, G e B todos abaixo disso não são tratadas como cor ao recolorir


class PakError(Exception):
    pass


# ---------------------------------------------------------------- classe 02 (documentação do Vras)
ANIM02_PART, ANIM02_MAX, ANIM02_COUNT = 120, 10, 1200


def anim02_count(a):
    """Quantidade de partes da animação da classe 02 (int em 1200). Se o valor não fizer sentido,
       conta as partes que têm alguma cor (comportamento antigo)."""
    if len(a) >= ANIM02_COUNT + 4:
        n = struct.unpack_from('<I', a, ANIM02_COUNT)[0]
        if 0 < n <= ANIM02_MAX:
            return n
    return sum(1 for s in range(min(ANIM02_MAX, len(a) // ANIM02_PART))
               if any(a[s * ANIM02_PART + 0x0C: s * ANIM02_PART + 0x30]))


# ---------------------------------------------------------------- container .pak
def pak_unpack(data):
    if len(data) < 8:
        raise PakError("arquivo muito pequeno")
    n = struct.unpack_from('<I', data, 0)[0]
    if n == 0 or n > 5000 or 4 + 4 * (n + 1) > len(data):
        raise PakError("cabeçalho de .pak inválido")
    offs = struct.unpack_from('<%dI' % (n + 1), data, 4)
    files = []
    for i in range(n):
        a, b = offs[i], offs[i + 1]
        if not (0 <= a <= b <= len(data)):
            raise PakError("offset inválido no arquivo %d" % i)
        files.append(data[a:b])
    return files, offs[0]


def pak_pack(files, header_size=None):
    n = len(files)
    min_hdr = 4 + 4 * (n + 1)
    if header_size is None or header_size < min_hdr:
        header_size = (min_hdr + 15) // 16 * 16
    offs, pos = [], header_size
    for f in files:
        offs.append(pos)
        pos += len(f)
    offs.append(pos)
    out = bytearray(header_size)
    struct.pack_into('<I', out, 0, n)
    struct.pack_into('<%dI' % (n + 1), out, 4, *offs)
    for f in files:
        out += f
    return bytes(out)


# ---------------------------------------------------------------- mini-efeito
class Mini:
    # offsets dentro do bloco de 64 bytes
    F = {'unk0': 0x00, 'dbt': 0x01, 'tex': 0x02, 'unk3': 0x03,
         'delay_a': 0x04, 'delay_b': 0x05, 'dur_a': 0x06, 'dur_b': 0x07,
         'invoke': 0x08, 'unk9': 0x09, 'unkA': 0x0A, 'unkB': 0x0B}
    FL = {'pos_x': 0x10, 'pos_y': 0x14, 'pos_z': 0x18, 'size1': 0x1C, 'size2': 0x20,
          'size3': 0x24, 'time1': 0x28, 'time2': 0x2C, 'unk30': 0x30}

    def __init__(self, mtype, param, files, group=""):
        self.type = mtype
        self.param = bytearray(param)
        self.files = [bytearray(f) for f in files]
        self.group = group

    def clone(self):
        m = Mini(self.type, bytes(self.param), [bytes(f) for f in self.files], self.group)
        m.shader_idx = getattr(self, "shader_idx", 1)
        return m

    def get(self, name):
        if name in self.F:
            return self.param[self.F[name]]
        return struct.unpack_from('<f', self.param, self.FL[name])[0]

    def set(self, name, value):
        if name in self.F:
            self.param[self.F[name]] = int(value) & 0xFF
        else:
            old = struct.unpack_from('<f', self.param, self.FL[name])[0]
            if abs(old - float(value)) > 1e-6:          # só grava se mudou (preserva precisão)
                struct.pack_into('<f', self.param, self.FL[name], float(value))

    @property
    def hits(self):
        return self.get('invoke') in (4, 5)

    # ---- cores
    def color_rows(self):
        """Lista de (indice_arquivo, offset, 'f'|'b') de cada linha RGBA editável."""
        rows = []
        if self.type in SHAPE_SHADER and len(self.files) == 2:
            si = getattr(self, "shader_idx", 1)
            sh = self.files[si]
            for r in SHADER_COLOR_ROWS:
                if (r + 1) * 16 <= len(sh):
                    rows.append((si, r * 16, 'f'))
        elif self.type == 0x0E and self.files:
            v = self.files[0]
            if v[:4] == b'V000' and len(v) >= 10:
                start = struct.unpack_from('<H', v, 8)[0]
                i = start + 48
                while i + 4 <= len(v):
                    rows.append((0, i, 'b'))
                    i += 64
        elif self.type == 0x02 and self.files:
            # classe 02 (saídas/feixes de luz): sessões de 120 bytes, RGBA em bytes nos
            # offsets 0x0C, 0x1C e 0x2C de cada sessão (documentação Madeirada)
            # documentação do Vras: até 10 partes de 120 bytes; quantidade de partes no int em 1200
            a = self.files[0]
            nparts = anim02_count(a)
            for s in range(nparts):
                base = s * 120
                for o in (0x0C, 0x1C, 0x2C):
                    rows.append((0, base + o, 'b'))
        return rows

    def read_rgba(self, row):
        fi, off, kind = row
        buf = self.files[fi]
        if kind == 'f':
            return list(struct.unpack_from('<4f', buf, off))
        return list(buf[off:off + 4])

    def write_rgba(self, row, rgba):
        fi, off, kind = row
        buf = self.files[fi]
        if kind == 'f':
            old = struct.unpack_from('<4f', buf, off)
            for k in range(4):
                if abs(old[k] - float(rgba[k])) > 1e-6:
                    struct.pack_into('<f', buf, off + 4 * k, float(rgba[k]))
        else:
            for k in range(4):
                buf[off + k] = max(0, min(255, int(round(rgba[k]))))

    def recolor(self, target_rgb, keep_saturation=False):
        th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
        for row in self.color_rows():
            r, g, b, a = self.read_rgba(row)
            mx = max(r, g, b)
            if mx <= 0 or (row[2] == 'f' and mx < MIN_COLOR):
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            ns = s if keep_saturation else s * ts
            nr, ng, nb = colorsys.hsv_to_rgb(th, ns, v)
            self.write_rgba(row, [round(nr * 255), round(ng * 255), round(nb * 255), a])

    def scale_size(self, factor):
        for k in ('size1', 'size2', 'size3'):
            self.set(k, self.get(k) * factor)


# ---------------------------------------------------------------- categoria
class Category:
    def __init__(self, ctype, raw=None):
        self.type = ctype
        self.raw = bytearray(raw if raw else bytes(32))
        self.dbts = []
        self.minis = []


def _looks_like_params(files, i):
    """O arquivo i tem cara de arquivo de parâmetros (cabeçalho + categorias + blocos de 64)?"""
    if i >= len(files):
        return False
    f = files[i]
    if len(f) < 64:
        return False
    ncat, total = f[4], f[5]
    if ncat == 0:
        return i == 3 and total == 0 and not any(f[:6])
    if len(f) < 64 + 32 * ncat:
        return False
    s = 0
    for c in range(ncat):
        t, cnt = f[64 + 32 * c], f[65 + 32 * c]
        if t not in KNOWN_TYPES:
            return False
        s += cnt
    return len(f) >= 64 + 32 * ncat + 64 * s and abs(s - total) <= 2


# ---------------------------------------------------------------- efeito
class Effect:
    def __init__(self):
        self.pre = []        # arquivos 00, 01, 02
        self.header = bytearray(64)
        self.cats = []
        self.post = []       # arquivos que sobram no fim (ex.: vazios)
        self.header_size = None
        self.n_files = 0
        self.tail03 = b''
        self.kind = "skill"

    # ---- leitura
    @classmethod
    def from_bytes(cls, data):
        files, hsize = pak_unpack(data)
        if len(files) < 2:
            raise PakError("o .pak não parece ser um efeito")
        # golpe: parâmetros no arquivo 03 (depois dos arquivos 00-02)
        # aura (01_charge_aura.pak): parâmetros no arquivo 00
        # Tenta os dois e fica com o que consome todos os arquivos (menos arquivos sobrando no fim).
        best, err, empty = None, None, None
        for start in (3, 0):
            if start >= len(files) or not _looks_like_params(files, start):
                continue
            try:
                e = cls._parse(files, hsize, start)
            except PakError as ex:
                err = ex
                continue
            except (IndexError, struct.error) as ex:
                # arquivo truncado/corrompido: faltam sub-arquivos ou bytes. Vira um erro normal
                # em vez de fechar o programa sem mensagem.
                err = PakError("arquivo corrompido ou incompleto (%s)" % ex)
                continue
            if not e.all_minis():
                if start == 3 and empty is None:
                    empty = e            # efeito sem mini-efeitos (ex.: Paralisia General Blue: só cena)
                continue
            if best is None or len(e.post) < len(best.post):
                best = e
        if best is None:
            best = empty
        if best is None:
            raise err or PakError("o .pak não parece ser um efeito")
        return best

    @classmethod
    def _parse(cls, files, hsize, start):
        e = cls()
        e.kind = "aura" if start == 0 else "skill"
        e.header_size, e.n_files = hsize, len(files)
        e.pre = [bytes(f) for f in files[:start]]
        f3 = files[start]
        if len(f3) < 64:
            raise PakError("arquivo 03 muito pequeno")
        e.header = bytearray(f3[:64])
        ncat = f3[4]
        if 64 + 32 * ncat > len(f3):
            raise PakError("arquivo de parâmetros inconsistente")
        total = sum(f3[65 + 32 * c] for c in range(ncat))
        e.total_delta = f3[5] - total          # alguns arquivos (ex.: aura Blue) trazem o total diferente da soma
        base = 64 + 32 * ncat
        if base + 64 * total > len(f3):
            raise PakError("arquivo 03 inconsistente (tamanho)")
        idx, k = start + 1, 0
        for c in range(ncat):
            raw = f3[64 + 32 * c: 96 + 32 * c]
            t, cnt, ndbt = raw[0], raw[1], raw[2]
            if t not in KNOWN_TYPES:
                raise PakError("categoria desconhecida: %02X" % t)
            cat = Category(t, raw)
            for _ in range(ndbt):
                cat.dbts.append(bytes(files[idx])); idx += 1
            for _ in range(cnt):
                p = f3[base + 64 * k: base + 64 * k + 64]; k += 1
                if t == 0x00:
                    fl = []
                elif t in (0x02, 0x0E):
                    fl = [files[idx]]; idx += 1
                else:
                    a, b = SHAPE_SHADER[t]
                    fl = [files[idx], files[idx + 1]]
                    if len(fl[0]) == a and len(fl[1]) == b:
                        sidx = 1
                    elif len(fl[0]) == b and len(fl[1]) == a:
                        sidx = 0              # alguns arquivos (ex.: Giant Storm) trazem o shader antes do shape
                    else:
                        raise PakError("tamanhos inesperados na categoria %02X (arquivo %d)" % (t, idx))
                    idx += 2
                    mm = Mini(t, p, fl)
                    mm.shader_idx = sidx
                    cat.minis.append(mm)
                    continue
                cat.minis.append(Mini(t, p, fl))
            e.cats.append(cat)
        if k != total:
            raise PakError("total de mini-efeitos não confere")
        e.tail03 = bytes(f3[base + 64 * total:])   # bytes extras no fim do 03 (preservados)
        e.post = [bytes(f) for f in files[idx:]]
        e.default_groups()
        return e

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as fh:
            return cls.from_bytes(fh.read())

    # ---- escrita
    def build_03(self):
        self.cats = [c for c in self.cats if c.minis or c.type == 0x00]
        # a ordem das categorias é preservada (a aura Blue, por exemplo, não está em ordem crescente)
        h = bytearray(self.header)
        mask = [0, 0, 0]
        for c in self.cats:
            mask[c.type // 8] |= 1 << (c.type % 8)
        h[0:3] = bytes(mask)
        h[4] = len(self.cats)
        total = sum(len(c.minis) for c in self.cats)
        if total > 255:
            raise PakError("mais de 255 mini-efeitos")
        h[5] = max(0, min(255, total + getattr(self, "total_delta", 0)))
        out = bytearray(h)
        for c in self.cats:
            raw = bytearray(c.raw)
            raw[0], raw[1], raw[2] = c.type, len(c.minis), len(c.dbts)
            out += raw
        for c in self.cats:
            for m in c.minis:
                out += m.param
        out += self.tail03
        return bytes(out)

    def file_list(self):
        files = list(self.pre) + [self.build_03()]
        for c in self.cats:
            files += c.dbts
            for m in c.minis:
                files += [bytes(f) for f in m.files]
        return files + list(self.post)

    def to_bytes(self):
        files = self.file_list()
        hs = self.header_size if len(files) == self.n_files else None
        return pak_pack(files, hs)

    def save(self, path):
        # grava num arquivo temporário e só depois troca: se der erro no meio (disco cheio,
        # arquivo aberto em outro programa), o .pak original não fica pela metade.
        data = self.to_bytes()
        tmp = path + ".tmp"
        try:
            with open(tmp, 'wb') as fh:
                fh.write(data)
            os.replace(tmp, path)
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    # ---- utilidades
    def all_minis(self):
        return [m for c in self.cats for m in c.minis]

    def cat_of(self, mini):
        for c in self.cats:
            if mini in c.minis:
                return c
        return None

    def default_groups(self):
        for m in self.all_minis():
            if not m.group:
                m.group = "impact" if m.hits else "phase%d" % m.get('invoke')

    def get_or_create_cat(self, ctype):
        for c in self.cats:
            if c.type == ctype:
                return c
        c = Category(ctype)
        pos = next((i for i, x in enumerate(self.cats) if x.type > ctype), len(self.cats))
        self.cats.insert(pos, c)
        return c

    def import_minis(self, src_effect, minis):
        """Copia mini-efeitos de outro efeito, trazendo os DBTs e remapeando os índices."""
        added = []
        for m in minis:
            sc = src_effect.cat_of(m)
            tc = self.get_or_create_cat(m.type)
            nm = m.clone()
            if sc is not None and sc.dbts:
                di = m.get('dbt')
                if di < len(sc.dbts):
                    data = sc.dbts[di]
                    try:
                        ni = tc.dbts.index(data)
                    except ValueError:
                        tc.dbts.append(data); ni = len(tc.dbts) - 1
                    nm.set('dbt', ni)
            tc.minis.append(nm)
            added.append(nm)
        return added

    def remove_minis(self, minis):
        ids = set(id(m) for m in minis)
        for c in self.cats:
            c.minis = [m for m in c.minis if id(m) not in ids]
        self.prune_dbts()

    def prune_dbts(self):
        for c in self.cats:
            if not c.dbts:
                continue
            used = sorted(set(m.get('dbt') for m in c.minis if m.get('dbt') < len(c.dbts)))
            remap = {old: new for new, old in enumerate(used)}
            c.dbts = [c.dbts[i] for i in used]
            for m in c.minis:
                if m.get('dbt') in remap:
                    m.set('dbt', remap[m.get('dbt')])

    def validate(self):
        """Reconstrói e relê; devolve lista de problemas (vazia = ok)."""
        probs = []
        try:
            e2 = Effect.from_bytes(self.to_bytes())
            if len(e2.all_minis()) != len(self.all_minis()):
                probs.append("contagem de mini-efeitos mudou ao reler")
        except PakError as ex:
            probs.append(str(ex))
        for c in self.cats:
            for m in c.minis:
                if c.dbts and m.get('dbt') >= len(c.dbts):
                    probs.append("mini-efeito da categoria %02X aponta para DBT inexistente" % c.type)
        return probs


# ---------------------------------------------------------------- DBT (texturas)
# Estrutura (descoberta com 07_texture.dbt e conferida nos 67 DBTs dos modelos):
#   0x00 uint32 = número de imagens
#   0x20 + 0x40*i = descritor da imagem i:
#       +0x00 uint32 offset/4 do pacote de PIXELS   +0x04 uint32 offset/4 do pacote da PALETA (CLUT)
#       +0x08 tamanho do pacote de pixels           +0x0C tamanho do pacote da paleta
#       +0x30 registrador GS TEX0 (PSM 0x13 = 8 bits/256 cores, 0x14 = 4 bits/16 cores; TW/TH = log2 da largura/altura)
#   Cada pacote = VIF DIRECT + GIFtags (BITBLTBUF/TRXPOS/TRXREG/TRXDIR) + GIFtag IMAGE + dados.
#   A paleta é RGBA 8 bits por canal, alfa de 0 a 0x80 (padrão PS2).

def _image_data(d, pkt):
    """Devolve (offset, tamanho) dos dados IMAGE dentro de um pacote VIF DIRECT."""
    if pkt + 16 > len(d):
        return None
    vif = struct.unpack_from('<I', d, pkt + 12)[0]
    if (vif >> 24) != 0x50:
        return None
    r, end = pkt + 16, pkt + 16 + (vif & 0xFFFF) * 16
    while r + 16 <= min(end, len(d)):
        tag = struct.unpack_from('<Q', d, r)[0]
        nloop, flg = tag & 0x7FFF, (tag >> 58) & 3
        nreg = (tag >> 60) & 0xF or 16
        r += 16
        if flg == 2:                       # IMAGE
            return (r, nloop * 16) if r + nloop * 16 <= len(d) else None
        if flg == 0:                       # PACKED: nloop * nreg qwords
            r += nloop * nreg * 16
        elif flg == 1:                     # REGLIST: nloop * nreg dwords (alinhado a 16)
            r += (nloop * nreg * 8 + 15) // 16 * 16
        else:
            return None
    return None


def dbt_info(d):
    """Lista de dicts com informações de cada imagem do DBT."""
    out = []
    if len(d) < 0x20:
        return out
    n = struct.unpack_from('<I', d, 0)[0]
    if n == 0 or n > 256 or 0x20 + 0x40 * n > len(d):
        return out
    for i in range(n):
        b = 0x20 + 0x40 * i
        pix_o, clut_o = struct.unpack_from('<2I', d, b)
        tex0 = struct.unpack_from('<Q', d, b + 0x30)[0]
        psm = (tex0 >> 20) & 0x3F
        out.append({'psm': psm, 'w': 1 << ((tex0 >> 26) & 0xF), 'h': 1 << ((tex0 >> 30) & 0xF),
                    'colors': 256 if psm == 0x13 else 16 if psm == 0x14 else 0,
                    'pixels': _image_data(d, pix_o * 4), 'clut': _image_data(d, clut_o * 4)})
    return out


def recolor_dbt(d, target_rgb, keep_saturation=False):
    """Troca o tom das paletas de todas as imagens do DBT. Pixels (índices) não são tocados."""
    th, ts, _ = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
    buf = bytearray(d)
    for img in dbt_info(d):
        if not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        for p in range(off, off + size - 3, 4):
            r, g, b = buf[p], buf[p + 1], buf[p + 2]
            if max(r, g, b) == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            ns = s if keep_saturation else s * ts
            nr, ng, nb = colorsys.hsv_to_rgb(th, ns, v)
            buf[p], buf[p + 1], buf[p + 2] = int(round(nr * 255)), int(round(ng * 255)), int(round(nb * 255))
    return bytes(buf)


def _effect_recolor_textures(self, target_rgb, keep_saturation=False):
    n = 0
    for c in self.cats:
        for i, d in enumerate(c.dbts):
            nd = recolor_dbt(d, target_rgb, keep_saturation)
            if nd != d:
                c.dbts[i] = nd
                n += 1
    return n


def _effect_behavior_summary(self):
    """Mini-efeitos que acertam o oponente (invocação 04/05), incluindo o tipo 00."""
    return [m for m in self.all_minis() if m.hits]


def _effect_apply_behavior(self, template):
    """Troca a 'parte que acerta' deste efeito pela do modelo:
       - remove os mini-efeitos com invocação 04/05 (exceto tipo 00)
       - importa os mini-efeitos 04/05 do modelo (com DBTs)
       - copia o bloco de parâmetros do mini-efeito tipo 00 do modelo."""
    self.remove_minis([m for m in self.all_minis() if m.hits and m.type != 0x00])
    added = self.import_minis(template, [m for m in template.all_minis() if m.hits and m.type != 0x00])
    t00 = [m for m in template.all_minis() if m.type == 0x00]
    s00 = [m for m in self.all_minis() if m.type == 0x00]
    if t00 and s00:
        s00[0].param[:] = t00[0].param
    elif t00:
        self.import_minis(template, t00[:1])
    for m in added:
        m.group = "impact"
    return added


Effect.recolor_textures = _effect_recolor_textures
Effect.behavior_summary = _effect_behavior_summary
Effect.apply_behavior = _effect_apply_behavior


# ---------------------------------------------------------------- invisibilidade
def _mini_hide(self, method="alpha"):
    """Deixa o mini-efeito invisível sem removê-lo (ele continua existindo e sendo invocado).
       'alpha': zera a transparência (A) de todas as linhas de cor do shader/V00 — mantém o tamanho.
       'size' : zera os três tamanhos."""
    if method == "size":
        if self.type != 0x00:
            for k in ('size1', 'size2', 'size3'):
                self.set(k, 0.0)
        return True
    rows = self.color_rows()
    for row in rows:
        r, g, b, a = self.read_rgba(row)
        self.write_rgba(row, [r, g, b, 0])
    return bool(rows)


Mini.hide = _mini_hide


# ---------------------------------------------------------------- cor predominante / comportamento v2 / explosão
LAUNCH_PHASES = (1, 2, 3)     # fases do lançamento (bits 00000100, fim, 00010000)
EXPLOSION_PHASE = 4           # invocação 04 = evento "Vfx 5" da animação


def _effect_dominant_color(self, only=None):
    """Cor predominante (média circular do tom, ponderada por saturação × brilho × alfa)."""
    import math
    sx = sy = wsum = ssum = 0.0
    for m in (only if only is not None else self.all_minis()):
        for row in m.color_rows():
            r, g, b, a = m.read_rgba(row)
            if max(r, g, b) < MIN_COLOR:
                continue
            h, s, v = colorsys.rgb_to_hsv(min(r, 255) / 255.0, min(g, 255) / 255.0, min(b, 255) / 255.0)
            w = s * v * (0.25 + min(max(a, 0), 128) / 128.0)
            sx += math.cos(2 * math.pi * h) * w
            sy += math.sin(2 * math.pi * h) * w
            ssum += s * w
            wsum += w
    if wsum < 1e-6 or math.hypot(sx, sy) < 1e-6:
        return None
    h = (math.atan2(sy, sx) / (2 * math.pi)) % 1.0
    s = max(0.35, min(1.0, ssum / wsum))
    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def _effect_recolor_parts(self, minis, rgb, keep_saturation=False):
    """Recolore mini-efeitos e as texturas usadas SOMENTE por eles."""
    ids = set(id(m) for m in minis)
    for m in minis:
        m.recolor(rgb, keep_saturation)
    for c in self.cats:
        for i, d in enumerate(c.dbts):
            users = [m for m in c.minis if m.get('dbt') == i]
            if users and all(id(m) in ids for m in users):
                c.dbts[i] = recolor_dbt(d, rgb, keep_saturation)


def _effect_apply_behavior2(self, template, launch=True, recolor=True):
    """Troca o comportamento pelo do modelo:
       - partes que acertam (invocação 04/05) + bloco do tipo 00 (sempre)
       - formato do lançamento: fases 1, 2 e 3 (opcional)
       - pinta o que veio com a cor predominante do efeito atual (opcional)
       O carregamento (fase 0) do efeito atual é mantido."""
    color = self.dominant_color() if recolor else None
    def wanted(m):
        return m.type != 0x00 and (m.hits or (launch and m.get('invoke') in LAUNCH_PHASES))
    self.remove_minis([m for m in self.all_minis() if wanted(m)])
    added = self.import_minis(template, [m for m in template.all_minis() if wanted(m)])
    t00 = [m for m in template.all_minis() if m.type == 0x00]
    s00 = [m for m in self.all_minis() if m.type == 0x00]
    if t00 and s00:
        s00[0].param[:] = t00[0].param
    elif t00:
        self.import_minis(template, t00[:1])
    for m in added:
        m.group = "impact" if m.hits else "phase%d" % m.get('invoke')
    if color and added:
        self.recolor_parts(added, color)
    return added, color


def _effect_add_explosion(self, explosion, recolor=True):
    """Adiciona a explosão (mini-efeitos com invocação 04 = 'Vfx 5') de outro efeito,
       substituindo a fase 4 atual e pintando com a cor predominante deste efeito."""
    color = self.dominant_color() if recolor else None
    self.remove_minis([m for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == EXPLOSION_PHASE])
    src = [m for m in explosion.all_minis() if m.type != 0x00 and m.get('invoke') == EXPLOSION_PHASE]
    added = self.import_minis(explosion, src)
    for m in added:
        m.group = "explosion"
    if color and added:
        self.recolor_parts(added, color)
    return added, color


Effect.dominant_color = _effect_dominant_color
Effect.recolor_parts = _effect_recolor_parts
Effect.apply_behavior = _effect_apply_behavior2
Effect.add_explosion = _effect_add_explosion


# ---------------------------------------------------------------- extras (mini-efeitos complementares)
def _effect_launch_phase(self):
    """Fase do disparo deste efeito: a invocação do mini-efeito tipo 00 (1 no Madam, 3 na Barragem)."""
    for m in self.all_minis():
        if m.type == 0x00 and m.get('invoke') in (1, 3):
            return m.get('invoke')
    return 1


def _effect_add_extra(self, extra, slot, tag, recolor=True):
    """Adiciona um extra (não muda formato nem classe). slot: 'charge' = fase 0, 'launch' = fase do disparo."""
    color = self.dominant_color() if recolor else None
    self.remove_minis([m for m in self.all_minis() if m.group == tag])
    added = self.import_minis(extra, [m for m in extra.all_minis() if m.type != 0x00])
    phase = 0 if slot == 'charge' else self.launch_phase()
    for m in added:
        m.set('invoke', phase)
        m.group = tag
    if color and added:
        self.recolor_parts(added, color)
    return added


def _effect_remove_extra(self, tag):
    ms = [m for m in self.all_minis() if m.group == tag]
    self.remove_minis(ms)
    return len(ms)


Effect.launch_phase = _effect_launch_phase
Effect.add_extra = _effect_add_extra
Effect.remove_extra = _effect_remove_extra


# ---------------------------------------------------------------- reduzir cores (256 → 16) das texturas
def _make_packet(orig_pkt, trx_w, trx_h, data):
    """Monta um pacote de upload com o mesmo formato do original (VIF DIRECT + A+D + IMAGE + TEXFLUSH)."""
    head = bytearray(orig_pkt[:0x50])          # 16 (VIF) + 64 (GIFtag A+D com TRXPOS/TRXREG/TRXDIR)
    tail = bytes(orig_pkt[-32:])               # GIFtag + TEXFLUSH
    nq = len(data) // 16
    struct.pack_into('<Q', head, 0x10 + 16 * 2, trx_w | (trx_h << 32))      # TRXREG
    img_tag = struct.unpack_from('<Q', orig_pkt, 0x50)[0]
    img_tag = (img_tag & ~0x7FFF) | nq
    body = bytes(head) + struct.pack('<QQ', img_tag, struct.unpack_from('<Q', orig_pkt, 0x58)[0]) + data + tail
    qwc = (len(body) - 16) // 16
    vif = struct.unpack_from('<I', body, 12)[0]
    body = body[:12] + struct.pack('<I', (vif & 0xFFFF0000) | qwc) + body[16:]
    return body


def dbt_reduce_colors(d, only=None):
    """Converte imagens de 256 cores (PSMT8) para 16 cores (PSMT4): pixels pela metade e paleta de 1 KB → 64 B.
       only: conjunto de índices de imagem a converter (None = todas). Devolve (novo_dbt, convertidas)."""
    import ps2tex
    infos = dbt_info(d)
    n = len(infos)
    if not n:
        return d, 0
    descs = [bytearray(d[0x20 + 0x40 * i: 0x60 + 0x40 * i]) for i in range(n)]
    pkts = []
    last_end = 0
    for i, im in enumerate(infos):
        po4, pc4, ps, cs = struct.unpack_from('<4I', descs[i], 0)
        pix_pkt, clut_pkt = d[po4 * 4: po4 * 4 + ps], d[pc4 * 4: pc4 * 4 + cs]
        last_end = max(last_end, po4 * 4 + ps, pc4 * 4 + cs)
        conv = im['psm'] == 0x13 and (only is None or i in only) and im['pixels'] and im['clut'] \
            and im['w'] >= 8 and im['h'] >= 8
        if conv:
            po, psz = im['pixels']
            co, csz = im['clut']
            idx, pal = ps2tex.decode(d[po:po + psz], d[co:co + csz], im['w'], im['h'], 0x13)
            qidx, pal16 = ps2tex.quantize16(idx, pal)
            pix4, clut4 = ps2tex.encode4(qidx, pal16, im['w'], im['h'])
            pix_pkt = _make_packet(pix_pkt, im['w'] // 2, im['h'] // 4, pix4)
            clut_pkt = _make_packet(clut_pkt, 8, 2, clut4)
            tex0 = struct.unpack_from('<Q', descs[i], 0x30)[0]
            tex0 = (tex0 & ~(0x3F << 20)) | (0x14 << 20)
            struct.pack_into('<Q', descs[i], 0x30, tex0)
            struct.pack_into('<I', descs[i], 0x10, (len(pix4) + 255) // 256)
            struct.pack_into('<I', descs[i], 0x14, 1)
        pkts.append((pix_pkt, clut_pkt, conv))
    if not any(p[2] for p in pkts):
        return d, 0
    hdr = bytearray(d[:0x20])
    old_pb = sum(struct.unpack_from('<I', d, 0x30 + 0x40 * i)[0] for i in range(n))
    old_cb = sum(struct.unpack_from('<I', d, 0x34 + 0x40 * i)[0] for i in range(n))
    new_pb = sum(struct.unpack_from('<I', x, 0x10)[0] for x in descs)
    new_cb = sum(struct.unpack_from('<I', x, 0x14)[0] for x in descs)
    struct.pack_into('<I', hdr, 8, struct.unpack_from('<I', hdr, 8)[0] - old_pb + new_pb)
    struct.pack_into('<I', hdr, 12, struct.unpack_from('<I', hdr, 12)[0] - old_cb + new_cb)
    pos = 0x20 + 0x40 * n
    first = min(min(struct.unpack_from('<2I', d, 0x20 + 0x40 * i)) for i in range(n)) * 4
    gap = bytes(d[pos:first])                 # alinhamento original antes do 1º pacote
    body = bytearray()
    cur = first
    for i, (pp, cp, _) in enumerate(pkts):
        struct.pack_into('<I', descs[i], 0, cur // 4)
        struct.pack_into('<I', descs[i], 8, len(pp))
        body += pp
        cur += len(pp)
        struct.pack_into('<I', descs[i], 4, cur // 4)
        struct.pack_into('<I', descs[i], 12, len(cp))
        body += cp
        cur += len(cp)
    out = bytes(hdr) + b''.join(bytes(x) for x in descs) + gap + bytes(body) + bytes(d[last_end:])
    return out, sum(1 for p in pkts if p[2])


def _effect_reduce_colors(self, minis=None):
    """Reduz para 16 cores as texturas (todas, ou só as usadas pelos mini-efeitos indicados)."""
    before = len(self.to_bytes())
    count = 0
    for c in self.cats:
        for i, d in enumerate(c.dbts):
            if minis is None:
                only = None
            else:
                ids = set(id(m) for m in minis)
                only = set(m.get('tex') for m in c.minis if m.get('dbt') == i and id(m) in ids)
                if not only:
                    continue
            nd, k = dbt_reduce_colors(d, only)
            if k:
                c.dbts[i] = nd
                count += k
    return count, before, len(self.to_bytes())


def _effect_color_depth(self):
    """(imagens de 256 cores, imagens de 16 cores)"""
    a = b = 0
    for c in self.cats:
        for d in c.dbts:
            for im in dbt_info(d):
                a += im['psm'] == 0x13
                b += im['psm'] == 0x14
    return a, b


Effect.reduce_colors = _effect_reduce_colors
Effect.color_depth = _effect_color_depth


# ---------------------------------------------------------------- v0.9: encaixe de fase (+0x09/+0x0A) e cabeçalho
_DEFAULT_SIG = {0: (2, 0), 1: (3, 1), 2: (0, 1), 3: (5, 2), 4: (6, 6), 5: (3, 4)}


def _effect_phase_signature(self, phase):
    """Par (+0x09, +0x0A) mais comum nos mini-efeitos desta fase. Esses bytes acompanham a invocação
       (ex.: fase 1 → 03/01, fase 3 da barragem → 05/02) e parecem dizer a que parte do golpe o
       mini-efeito se prende (mão, projétil, tiros da barragem, oponente)."""
    from collections import Counter
    c = Counter((m.param[9], m.param[10]) for m in self.all_minis()
                if m.type != 0x00 and m.get('invoke') == phase)
    if c:
        return c.most_common(1)[0][0]
    return _DEFAULT_SIG.get(phase, (0, 0))


def _mini_move_to_phase(self, phase, sig):
    self.set('invoke', phase)
    self.param[9], self.param[10] = sig[0], sig[1]


Mini.move_to_phase = _mini_move_to_phase
Effect.phase_signature = _effect_phase_signature


def _effect_add_extra2(self, extra, slot, tag, recolor=True):
    color = self.dominant_color() if recolor else None
    self.remove_minis([m for m in self.all_minis() if m.group == tag])
    phase = 0 if slot == 'charge' else self.launch_phase()
    sig = self.phase_signature(phase)
    added = self.import_minis(extra, [m for m in extra.all_minis() if m.type != 0x00])
    for m in added:
        m.move_to_phase(phase, sig)
        m.group = tag
    if color and added:
        self.recolor_parts(added, color)
    return added


def _effect_apply_behavior3(self, template, launch=True, recolor=True, header=True):
    added, color = _effect_apply_behavior2(self, template, launch=launch, recolor=recolor)
    if header:
        # parâmetros de lançamento do cabeçalho do arquivo 03 (ex.: byte 6 ≠ 0 nos ataques verticais,
        # float em 0x08 = alcance). Bitmask e contagens são recalculados ao salvar.
        self.header[:] = template.header
    return added, color


Effect.add_extra = _effect_add_extra2
Effect.apply_behavior = _effect_apply_behavior3


# ---------------------------------------------------------------- v0.10: extras em par e "só comportamento"
def _effect_add_extra3(self, extra, slot, tag, recolor=True):
    """Extras vêm como no efeito original: o mini-efeito da fase 0 (carregamento) e, quando existe,
       o 'par' dele no disparo, na mesma ordem. Só o que é do disparo muda de fase, e só se preciso."""
    color = self.dominant_color() if recolor else None
    self.remove_minis([m for m in self.all_minis() if m.group == tag])
    lp = self.launch_phase()
    sig = self.phase_signature(lp)
    added = self.import_minis(extra, [m for m in extra.all_minis() if m.type != 0x00])
    for m in added:
        inv = m.get('invoke')
        if inv != 0 and inv != lp:
            m.move_to_phase(lp, sig)
        m.group = tag
    if color and added:
        self.recolor_parts(added, color)
    return added


def _effect_apply_behavior4(self, template, launch=True, recolor=True, header=True, keep_shape=False):
    """keep_shape=True: muda só o comportamento. Copia cabeçalho e tipo 00 do modelo e move os
       mini-efeitos do disparo DESTE efeito para a fase/encaixe de disparo do modelo; nada é importado."""
    if not keep_shape:
        return _effect_apply_behavior3(self, template, launch=launch, recolor=recolor, header=header)
    own_lp = self.launch_phase()
    tpl_lp = template.launch_phase()
    sig = template.phase_signature(tpl_lp)
    moved = [m for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == own_lp]
    for m in moved:
        m.move_to_phase(tpl_lp, sig)
        if not m.group.startswith("extra:"):
            m.group = "phase%d" % tpl_lp
    t00 = [m for m in template.all_minis() if m.type == 0x00]
    s00 = [m for m in self.all_minis() if m.type == 0x00]
    if t00 and s00:
        s00[0].param[:] = t00[0].param
    elif t00:
        self.import_minis(template, t00[:1])
    if header:
        self.header[:] = template.header
    return moved, None


Effect.add_extra = _effect_add_extra3
Effect.apply_behavior = _effect_apply_behavior4


def _effect_launch_phase2(self):
    """Fase do disparo: entre as fases 1 e 3, a que tem mais mini-efeitos visuais
       (Madam → 1, Barragem/Vertical → 3, Hellzone/Janemba → 1). Empate: invocação do tipo 00."""
    n1 = sum(1 for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == 1)
    n3 = sum(1 for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == 3)
    if n1 != n3:
        return 1 if n1 > n3 else 3
    return _effect_launch_phase(self)


Effect.launch_phase = _effect_launch_phase2


# ---------------------------------------------------------------- v0.11: extras com fase de origem, auras e flags
FLAG_BITS = [1, 2, 4, 8, 16, 32, 64, 128]


def _effect_add_extra4(self, extra, slot, tag, recolor=True, src_lp=1, to_charge=False):
    """- to_charge: tudo vai para a fase 0 (auras de carregamento), com +0x0A = 0.
       - senão: só o que estava na fase do disparo da ORIGEM (src_lp) vai para o disparo deste efeito;
         fase 0 e outras fases ficam como estão (mantém a sequência original do extra)."""
    color = self.dominant_color() if recolor else None
    self.remove_minis([m for m in self.all_minis() if m.group == tag])
    lp = self.launch_phase()
    sig = self.phase_signature(lp)
    added = self.import_minis(extra, [m for m in extra.all_minis() if m.type != 0x00])
    for m in added:
        inv = m.get('invoke')
        if to_charge:
            if inv != 0:
                m.set('invoke', 0)
                m.param[10] = 0
        elif inv == src_lp and src_lp != lp:
            m.move_to_phase(lp, sig)
        m.group = tag
    if color and added:
        self.recolor_parts(added, color)
    return added


Effect.add_extra = _effect_add_extra4


# ---------------------------------------------------------------- v0.12: encaixe (+0x09/+0x0A) que existe no destino
def _effect_add_extra5(self, extra, slot, tag, recolor=True, src_lp=1, to_charge=False):
    """Como a v0.11, mas se o encaixe (+0x09, +0x0A) de um mini-efeito importado não existir no efeito
       de destino naquela fase (ex.: +0x0A = 05 das argolas do Makankosappo num ataque de área, que não
       tem nada preso nesse ponto), ele é trocado pelo encaixe usado pelo destino."""
    before = {}
    for m in self.all_minis():
        if m.type != 0x00 and m.group != tag:
            before.setdefault(m.get('invoke'), set()).add((m.param[9], m.param[10]))
    added = _effect_add_extra4(self, extra, slot, tag, recolor=recolor, src_lp=src_lp, to_charge=to_charge)
    for m in added:
        inv = m.get('invoke')
        if inv == 0:
            continue
        have = before.get(inv, set())
        if have and (m.param[9], m.param[10]) not in have:
            sig = self.phase_signature(inv)
            m.param[9], m.param[10] = sig[0], sig[1]
    return added


Effect.add_extra = _effect_add_extra5


# ---------------------------------------------------------------- v0.14: "forçar cor" (tingir partes brancas/cinzas)
DARK_KNEE = 0.35   # cores escolhidas com brilho (V) abaixo disso escurecem o efeito; acima, o brilho original é mantido


def _tint(r, g, b, th, ts, keep_saturation, force, tv=1.0):
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    ns = s if keep_saturation else s * ts
    if force > 0:
        ns = ns + (max(ts, 0.35) - ns) * force if ns < max(ts, 0.35) else ns
    # cores escuras (principalmente o preto): sem isto o programa só trocava o tom e mantinha o brilho,
    # então "colorir de preto" deixava as partes claras em branco/cinza. Agora o brilho acompanha a cor.
    v *= min(1.0, max(0.0, tv) / DARK_KNEE)
    return colorsys.hsv_to_rgb(th, max(0.0, min(1.0, ns)), v)


def _mini_recolor2(self, target_rgb, keep_saturation=False, force=0.0):
    th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
    for row in self.color_rows():
        r, g, b, a = self.read_rgba(row)
        if max(r, g, b) <= 0 or (row[2] == 'f' and max(r, g, b) < MIN_COLOR):
            continue
        nr, ng, nb = _tint(min(r, 255), min(g, 255), min(b, 255), th, ts, keep_saturation, force, tv)
        self.write_rgba(row, [round(nr * 255), round(ng * 255), round(nb * 255), a])


def recolor_dbt2(d, target_rgb, keep_saturation=False, force=0.0):
    th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
    buf = bytearray(d)
    for img in dbt_info(d):
        if not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        for p in range(off, off + size - 3, 4):
            r, g, b = buf[p], buf[p + 1], buf[p + 2]
            if max(r, g, b) == 0:
                continue
            nr, ng, nb = _tint(r, g, b, th, ts, keep_saturation, force, tv)
            buf[p], buf[p + 1], buf[p + 2] = int(round(nr * 255)), int(round(ng * 255)), int(round(nb * 255))
    return bytes(buf)


def _effect_recolor_textures2(self, target_rgb, keep_saturation=False, force=0.0):
    n = 0
    for c in self.cats:
        for i, d in enumerate(c.dbts):
            nd = recolor_dbt2(d, target_rgb, keep_saturation, force)
            if nd != d:
                c.dbts[i] = nd
                n += 1
    return n


Mini.recolor = _mini_recolor2
recolor_dbt = recolor_dbt2
Effect.recolor_textures = _effect_recolor_textures2


def _effect_swap_aura(self, template, recolor=True, force=0.0):
    """Troca o formato da aura pelo do modelo, pintando com a cor predominante da aura atual."""
    color = self.dominant_color() if recolor else None
    new = Effect.from_bytes(template.to_bytes())
    if color:
        for m in new.all_minis():
            m.recolor(color, False, force)
        new.recolor_textures(color, False, force)
    return new, color


Effect.swap_aura = _effect_swap_aura


# ---------------------------------------------------------------- v0.15: troca de conteúdo mantendo o layout, opacidade, ir até o adversário
import re as _re
SUPPORT_NAME = _re.compile(r'(00_skill_001|01_skill_002|00_effect_skill_1|01_effect_skill_2)', _re.I)


def _effect_swap_content(self, template, recolor=True, force=0.0):
    """Troca todos os mini-efeitos pelos do modelo, mantendo o layout deste arquivo
       (golpe/suporte com arquivos 00-02, ou aura sem eles). Pinta com a cor atual se pedido."""
    color = self.dominant_color() if recolor else None
    new = Effect.from_bytes(template.to_bytes())
    new.pre = list(self.pre)
    new.post = list(self.post)
    new.kind = self.kind
    new.header_size = None
    new.n_files = -1
    if color:
        for m in new.all_minis():
            m.recolor(color, False, force)
        new.recolor_textures(color, False, force)
    return new, color


def _effect_swap_aura2(self, template, recolor=True, force=0.0):
    return _effect_swap_content(self, template, recolor, force)


def _effect_reduce_opacity(self, minis, percent, alpha=True, brightness=False, textures=False):
    """Reduz a opacidade (canal A) e/ou o brilho (RGB) das cores dos mini-efeitos indicados.
       textures=True também reduz o alfa das paletas usadas SOMENTE por esses mini-efeitos."""
    k = max(0.0, min(1.0, 1.0 - percent / 100.0))
    n = 0
    for m in minis:
        for row in m.color_rows():
            r, g, b, a = m.read_rgba(row)
            if brightness:
                r, g, b = r * k, g * k, b * k
            if alpha:
                a = a * k
            m.write_rgba(row, [r, g, b, a])
            n += 1
    if textures and alpha:
        ids = set(id(m) for m in minis)
        for c in self.cats:
            for i, d in enumerate(c.dbts):
                users = [m for m in c.minis if m.get('dbt') == i]
                if users and all(id(m) in ids for m in users):
                    buf = bytearray(d)
                    for img in dbt_info(d):
                        if img['clut']:
                            off, size = img['clut']
                            for p in range(off + 3, off + size, 4):
                                buf[p] = int(round(buf[p] * k))
                    c.dbts[i] = bytes(buf)
    return n


def _effect_go_to_opponent(self, reference, attach=True, hits=True):
    """EXPERIMENTAL (suportes): faz o efeito ir até o adversário como a 'paralisia que se move'.
       - copia o mini-efeito tipo 00 (controlador do projétil) do efeito de referência
       - prende os mini-efeitos da fase 1 ao projétil (+0x09 = 03, +0x0A = 05)
       - opcional: traz o impacto no adversário (fase 5) da referência."""
    t00 = [m for m in reference.all_minis() if m.type == 0x00]
    s00 = [m for m in self.all_minis() if m.type == 0x00]
    if t00:
        if s00:
            s00[0].param[:] = t00[0].param
        else:
            self.import_minis(reference, t00[:1])
    moved = 0
    if attach:
        for m in self.all_minis():
            if m.type != 0x00 and m.get('invoke') == 1:
                m.param[9], m.param[10] = 3, 5
                moved += 1
    added = []
    if hits:
        self.remove_minis([m for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == 5])
        added = self.import_minis(reference, [m for m in reference.all_minis() if m.type != 0x00 and m.get('invoke') == 5])
        for m in added:
            m.group = "impact"
    return moved, len(added)


Effect.swap_content = _effect_swap_content
Effect.swap_aura = _effect_swap_aura2
Effect.reduce_opacity = _effect_reduce_opacity
Effect.go_to_opponent = _effect_go_to_opponent


# ---------------------------------------------------------------- v0.16: parâmetros de suporte, pré-disparo, crescimento
def _effect_go_to_opponent2(self, reference, attach=True, zero_delay=True, hits=False, to_impact=False):
    """EXPERIMENTAL: só a 'função de disparar' da paralisia móvel.
       Diferença que faz ir até o adversário: tipo 00 (projétil) + parâmetros do cabeçalho do arquivo
       de parâmetros (bytes 0x06-0x3F) + partes da fase 1 presas ao projétil (03 05).
       zero_delay: zera os atrasos das partes presas (ex.: o flash do Taiyoken tem atraso 6 e aparece
       depois que o projétil já passou). to_impact: em vez de viajar, as partes da fase 1 aparecem no
       acerto (fase 5)."""
    t00 = [m for m in reference.all_minis() if m.type == 0x00]
    s00 = [m for m in self.all_minis() if m.type == 0x00]
    if t00:
        if s00:
            s00[0].param[:] = t00[0].param
        else:
            self.import_minis(reference, t00[:1])
    self.header[6:] = reference.header[6:]
    touched = 0
    for m in self.all_minis():
        if m.type == 0x00 or m.get('invoke') != 1:
            continue
        if to_impact:
            m.move_to_phase(5, (3, 4))
        elif attach:
            m.param[9], m.param[10] = 3, 5
        if zero_delay:
            m.set('delay_a', 0)
            m.set('delay_b', 0)
        touched += 1
    added = []
    if hits:
        self.remove_minis([m for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == 5 and m.group == "impact"])
        added = self.import_minis(reference, [m for m in reference.all_minis() if m.type != 0x00 and m.get('invoke') == 5])
        for m in added:
            m.group = "impact"
    return touched, len(added)


def _effect_persist(self, phases=None, on=True):
    """'Ficar até usar um especial' (experimental): byte +0x0B = 04 nas partes escolhidas.
       Todas as auras de carregamento e as auras que ficam até usar especial usam 04 nesse byte."""
    n = 0
    for m in self.all_minis():
        if m.type == 0x00 or (phases is not None and m.get('invoke') not in phases):
            continue
        if on:
            m.param[11] = 4
        elif m.param[11] == 4:
            m.param[11] = 0
        n += 1
    return n


def _effect_apply_prelaunch(self, pre, recolor=True):
    """Formato pré-disparo: troca a fase 0 (carregamento) pelas partes do modelo, na fase 0,
       presas ao personagem (+0x09 03/05 → 02; +0x0A = 0)."""
    color = self.dominant_color() if recolor else None
    self.remove_minis([m for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == 0
                       and not m.group.startswith("extra:")])
    added = self.import_minis(pre, [m for m in pre.all_minis() if m.type != 0x00])
    for m in added:
        m.set('invoke', 0)
        if m.param[9] in (3, 5):
            m.param[9] = 2
        m.param[10] = 0
        m.group = "prelaunch"
    if color and added:
        self.recolor_parts(added, color)
    return added, color


GROWTH_PATTERNS = {
    # tamanhos relativos (1, 2, 3) e tempos (1→2, 2→3), tirados dos efeitos originais
    "turles": ((0.0, 0.5, 1.0), (0.2, 0.5)),       # Argola Turles, antes do disparo: nasce do nada e cresce
    "bills": ((0.53, 0.07, 1.0), (0.5, 1.2)),      # contrai e depois explode
}


def _mini_apply_growth(self, pattern, reverse=False):
    if self.type == 0x00:
        return False
    rel, times = GROWTH_PATTERNS[pattern]
    base = max(self.get('size1'), self.get('size2'), self.get('size3'))
    if base <= 0:
        return False
    if reverse:
        rel, times = tuple(reversed(rel)), tuple(reversed(times))
    for k, r in zip(('size1', 'size2', 'size3'), rel):
        self.set(k, base * r)
    self.set('time1', times[0])
    self.set('time2', times[1])
    return True


def _effect_copy_scene(self, template):
    if len(self.pre) > 2 and len(template.pre) > 2 and template.pre[2]:
        self.pre[2] = template.pre[2]
        return True
    return False


Effect.go_to_opponent = _effect_go_to_opponent2
Effect.persist = _effect_persist
Effect.apply_prelaunch = _effect_apply_prelaunch
Effect.copy_scene = _effect_copy_scene
Mini.apply_growth = _mini_apply_growth


# ---------------------------------------------------------------- v0.18: reduzir para 128/64/32 cores (continua 8 bits)
def dbt_reduce_palette(d, ncolors, only=None):
    """Reduz imagens de 256 cores para 'ncolors' (128, 64 ou 32) mantendo o formato PSMT8.
       O arquivo NÃO fica menor (continua 1 byte por pixel e paleta de 256 entradas); muda só o visual."""
    import ps2tex
    infos = dbt_info(d)
    buf = bytearray(d)
    n = 0
    for i, im in enumerate(infos):
        if im['psm'] != 0x13 or not im['pixels'] or not im['clut'] or (only is not None and i not in only):
            continue
        po, ps = im['pixels']
        co, cs = im['clut']
        idx, pal = ps2tex.decode(d[po:po + ps], d[co:co + cs], im['w'], im['h'], 0x13)
        if len(set(idx)) <= ncolors:
            continue
        qidx, qpal = ps2tex.quantizeN(idx, pal, ncolors)
        pix, clut = ps2tex.encode8(qidx, qpal, im['w'], im['h'])
        buf[po:po + ps] = pix
        buf[co:co + cs] = clut
        n += 1
    return bytes(buf), n


def _effect_reduce_colors2(self, minis=None, ncolors=16):
    if ncolors == 16:
        return _effect_reduce_colors(self, minis)
    before = len(self.to_bytes())
    count = 0
    for c in self.cats:
        for i, d in enumerate(c.dbts):
            if minis is None:
                only = None
            else:
                ids = set(id(m) for m in minis)
                only = set(m.get('tex') for m in c.minis if m.get('dbt') == i and id(m) in ids)
                if not only:
                    continue
            nd, k = dbt_reduce_palette(d, ncolors, only)
            if k:
                c.dbts[i] = nd
                count += k
    return count, before, len(self.to_bytes())


Effect.reduce_colors = _effect_reduce_colors2


# ---------------------------------------------------------------- v0.20 (documentação Madeirada)
# nomes da documentação Madeirada parte 3 (a ferramenta mostra só o nome, sem o número da classe)
CLASS_NAMES = {0x00: "Linhas de Foco", 0x02: "Saídas de Luz", 0x05: "Complementos/Acabamentos", 0x09: "Destaque",
               0x0A: "Classe 0A", 0x0E: "V00", 0x0F: "Classe 0F", 0x10: "Iluminação", 0x11: "Cauda/Feixe",
               0x12: "Raios"}

# bytes 0x20-0x27 do cabeçalho do 03.dat: como o golpe aparece durante a ceninha
SCENE_APPEAR = {
    "none":       {0x21: 0, 0x22: 0, 0x25: 0, 0x26: 0},
    "beam":       {0x21: 1, 0x22: 0, 0x25: 0, 0x26: 0x10},   # feixe que encerra o golpe (Burst Rush, Nail...)
    "projectile": {0x21: 1, 0x22: 0, 0x25: 5, 0x26: 0x10},   # projétil (Comet Attack do Jeice, Gotenks Volleyball)
    "vertical":   {0x21: 1, 0x22: 1, 0x25: 0, 0x26: 0x10},   # feixe de cima p/ baixo ou de baixo p/ cima (Trunks Dome)
}
BARRAGE_BYTE = 0x27          # 02 = modo barragem; 03 = barragem que aparece na ceninha (Cui)


def _effect_scene_appear(self):
    h = self.header
    for k, d in SCENE_APPEAR.items():
        if all(h[o] == v for o, v in d.items()):
            return k
    return "custom"


def _effect_set_scene_appear(self, key):
    for o, v in SCENE_APPEAR[key].items():
        self.header[o] = v


def _effect_is_barrage(self):
    return self.header[BARRAGE_BYTE] in (2, 3)


def _effect_set_barrage(self, on, in_scene=False):
    self.header[BARRAGE_BYTE] = (3 if in_scene else 2) if on else 0
    if on and in_scene and not self.header[0x26]:
        self.header[0x26] = 0x10


def _effect_scene_persist(self, on):
    """Grupo 01: byte +0x09 = 04 mantém o mini-efeito durante a ceninha; 03 faz ele sumir nela."""
    n = 0
    for m in self.all_minis():
        if m.type != 0x00 and m.get('invoke') == 1 and m.param[9] in (3, 4):
            m.param[9] = 4 if on else 3
            n += 1
    return n


def _effect_global_stripes(self):
    """O primeiro mini-efeito do 03.dat (tipo 00) é o efeito global de listras brancas."""
    for m in self.all_minis():
        if m.type == 0x00:
            return m
    return None


def _effect_hide_stripes(self, hide=True):
    m = self.global_stripes()
    if m is None:
        return False
    if hide:
        m.saved_sizes = (m.get('size1'), m.get('size2'), m.get('size3'))
        for k in ('size1', 'size2', 'size3'):
            m.set(k, 0.0)
    else:
        m.set('size1', 0.15)
        m.set('size2', 0.15)
    return True


# 02_.dat: altura (Y) e posição Z dos dois personagens na ceninha, por mapa (35) e evento (5)
SCENE_MAPS, SCENE_EVENTS = 35, 5


def scene_table(data):
    rows = []
    for mp in range(SCENE_MAPS):
        for ev in range(SCENE_EVENTS):
            o = (mp * SCENE_EVENTS + ev) * 16
            if o + 16 <= len(data):
                v = struct.unpack_from('<4f', data, o)
                rows.append((mp, ev, v[1], v[2]))
            else:
                rows.append((mp, ev, 0.0, 0.0))
    return rows


def scene_set(data, mp, ev, y=None, z=None):
    buf = bytearray(data if len(data) >= 2816 else bytes(2816))
    o = (mp * SCENE_EVENTS + ev) * 16
    if y is not None:
        struct.pack_into('<f', buf, o + 4, float(y))
    if z is not None:
        struct.pack_into('<f', buf, o + 8, float(z))
    return bytes(buf)


def _effect_recolor_contrast(self, target_rgb, shift_deg=-35, force=0.0, textures=True):
    """Colorir com contraste (como o jogo faz: roxo com partes azuis, laranja com partes vermelhas).
       Partes que no original já tinham um tom diferente do predominante (> 20°) e as classes de
       raios (12) e iluminação (10) recebem a cor 'vizinha' (tom deslocado); o resto recebe a cor escolhida."""
    th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
    alt_h = (th + shift_deg / 360.0) % 1.0
    ar, ag, ab = colorsys.hsv_to_rgb(alt_h, ts, tv)
    alt = (int(ar * 255), int(ag * 255), int(ab * 255))
    dom = self.dominant_color()
    dh = colorsys.rgb_to_hsv(*[c / 255.0 for c in dom])[0] if dom else None
    for m in self.all_minis():
        use_alt = m.type in (0x10, 0x12)
        if not use_alt and dh is not None:
            hs = []
            for row in m.color_rows():
                r, g, b, a = m.read_rgba(row)
                if max(r, g, b) >= MIN_COLOR:
                    h, s, v = colorsys.rgb_to_hsv(min(r, 255) / 255, min(g, 255) / 255, min(b, 255) / 255)
                    if s > 0.2:
                        hs.append(h)
            if hs:
                avg = sum(hs) / len(hs)
                diff = min(abs(avg - dh), 1 - abs(avg - dh))
                use_alt = diff > 20 / 360.0
        m.recolor(alt if use_alt else target_rgb, False, force)
    if textures:
        self.recolor_textures(target_rgb, False, force)
    return alt


def _mini_channels(self, a, b, mode):
    """mode 'swap': troca os canais a e b; 'copy': copia a → b. Canais: 0 R, 1 G, 2 B, 3 A."""
    for row in self.color_rows():
        v = self.read_rgba(row)
        if mode == 'swap':
            v[a], v[b] = v[b], v[a]
        else:
            v[b] = v[a]
        self.write_rgba(row, v)


def _effect_texture_users(self, cat, dbt_index, tex=None):
    return [m for m in cat.minis if m.get('dbt') == dbt_index and (tex is None or m.get('tex') == tex)]


def dbt_replace_image(d, index, rgba, w, h):
    """Troca a imagem 'index' do DBT pelos pixels RGBA (lista de tuplas, alfa 0-255, já em w×h iguais
       ao original), convertendo para a quantidade de cores original (16 ou 256)."""
    import ps2tex
    info = dbt_info(d)[index]
    if (w, h) != (info['w'], info['h']):
        raise PakError("dimensões diferentes")
    ncol = 256 if info['psm'] == 0x13 else 16
    uniq = {}
    idx = []
    pal = []
    for c in rgba:
        c = (c[0], c[1], c[2], (c[3] + 1) // 2)       # alfa do PS2: 0-128
        k = uniq.get(c)
        if k is None:
            k = uniq[c] = len(pal)
            pal.append(c)
        idx.append(k)
    if len(pal) > 4096:                              # pré-redução para acelerar (5 bits por canal)
        uniq2, pal2, remap = {}, [], []
        for c in pal:
            q = (c[0] & 0xF8, c[1] & 0xF8, c[2] & 0xF8, c[3] & 0xFC)
            k = uniq2.get(q)
            if k is None:
                k = uniq2[q] = len(pal2)
                pal2.append(q)
            remap.append(k)
        idx = [remap[i] for i in idx]
        pal = pal2
    qidx, qpal = ps2tex.quantizeN(idx, pal, ncol)
    buf = bytearray(d)
    po, ps = info['pixels']
    co, cs = info['clut']
    if ncol == 256:
        pix, clut = ps2tex.encode8(qidx, qpal, w, h)
    else:
        pix, clut = ps2tex.encode4(qidx, qpal, w, h)
    buf[po:po + ps] = pix
    buf[co:co + cs] = clut[:cs]
    return bytes(buf)


def dbt_image_rgba(d, index):
    import ps2tex
    im = dbt_info(d)[index]
    po, ps = im['pixels']
    co, cs = im['clut']
    idx, pal = ps2tex.decode(d[po:po + ps], d[co:co + cs], im['w'], im['h'], im['psm'])
    return [pal[i][:3] + (min(255, pal[i][3] * 2),) for i in idx], im['w'], im['h']


Effect.scene_appear = _effect_scene_appear
Effect.set_scene_appear = _effect_set_scene_appear
Effect.is_barrage = _effect_is_barrage
Effect.set_barrage = _effect_set_barrage
Effect.scene_persist = _effect_scene_persist
Effect.global_stripes = _effect_global_stripes
Effect.hide_stripes = _effect_hide_stripes
Effect.recolor_contrast = _effect_recolor_contrast
Effect.texture_users = _effect_texture_users
Mini.channels = _mini_channels


# ---------------------------------------------------------------- pacote completo de efeitos (ex.: Goku_eff.pak)
SKILL_SLOT_NAMES = ["00_skill_001.pak", "01_skill_002.pak", "02_skill_003.pak", "03_skill_004.pak",
                    "04_skill_005.pak", "05_effect_common.pak"]
# nomes da lista do Sparking Studio (z3_paklist: "Chara EFF\\05_effect_common")
COMMON_NAMES = {0: "00_common_param.dat", 1: "01_charge_aura.pak", 2: "02_kidan.pak", 3: "03_charge_kidan.pak",
                4: "04_.pak", 5: "05_ki_wave.pak", 6: "06_energy_wave.pak", 7: "07_skill_cameras.pak",
                8: "08_jetpack.pak", 9: "09_.pak", 10: "10_absorb.pak"}
# mapas do jogo (Sparking Studio: maps.txt), na ordem usada pelo 02_.dat
MAP_NAMES = ["Plains (Noon)", "Rocky Area (Noon)", "Namek", "Ruined Namek", "World Tour (Noon)", "Kami Palace",
             "Cell Arena (Evening)", "Supreme Planet", "Time Chamber", "City Ruins (Noon)", "Mountain Road (Noon)",
             "Islands", "Kame House", "Planet (Night)", "Glaciar", "Ruined Earth", "Space", "Penguin Village", "Hell",
             "Desert (Noon)", "King Castle", "Muscle Tower", "Mount Paozu", "Plains (Evening)", "Plains (Night)",
             "Rocky Area (Evening)", "Rocky Area (Night)", "World Tour (Evening)", "Cell Arena (Noon)",
             "City Ruins (Evening)", "City Ruins (Night)", "Desert (Evening)", "Desert (Night)",
             "Mountain Road (Evening)", "Planet (Evening)"]


def container_entries(data):
    """Se 'data' for um pacote de efeitos de personagem, devolve a lista de entradas abríveis:
       [(caminho_de_índices, nome, tipo)], senão None."""
    try:
        files, _ = pak_unpack(data)
    except PakError:
        return None
    out, effects = [], 0
    special = len(files) > 1 and len(files[0]) == 64          # 05_effect_special: 00 = 00_effect_parameter.dat
    for i, f in enumerate(files):
        if special:
            name = COMMON_NAMES.get(i, "%02d.pak" % i)
        else:
            name = SKILL_SLOT_NAMES[i] if i < len(SKILL_SLOT_NAMES) else "%02d.pak" % i
        try:
            e = Effect.from_bytes(f)
            out.append(((i,), name, e.kind, len(e.all_minis())))
            effects += 1
            continue
        except PakError:
            pass
        try:
            sub, _ = pak_unpack(f)
        except PakError:
            continue
        for j, g in enumerate(sub):
            try:
                e = Effect.from_bytes(g)
            except PakError:
                continue
            sname = COMMON_NAMES.get(j, "%02d.pak" % j)
            out.append(((i, j), name + " › " + sname, e.kind, len(e.all_minis())))
            effects += 1
    return out if effects >= 2 else None


def container_get(data, path):
    cur = data
    for i in path:
        files, _ = pak_unpack(cur)
        cur = files[i]
    return cur


def container_put(data, path, new):
    files, hs = pak_unpack(data)
    if len(path) == 1:
        files[path[0]] = new
    else:
        files[path[0]] = container_put(files[path[0]], path[1:], new)
    return pak_pack(files, hs)


# ================================================================ v1.5 (documentação Madeirada parte 3)
# Estágios (byte +0x08 do bloco de parâmetros), desaparecimento (+0x09) e orientação (+0x0A).
STAGE_HIDE_IN_SCENE = 5          # +0x09 = 05: não aparece durante ceninhas (confirmado)
STAGE_SHOW_IN_SCENE = 3          # +0x09 = 03: valor original visto nas partes que aparecem na ceninha


def _effect_scene_persist2(self, on, minis=None):
    """Partes do pós-disparo (estágio 1) na ceninha. Esconder = +0x09 → 05; mostrar = 05 → 03.
       minis: só esses (senão todas as partes do estágio 1)."""
    pool = minis if minis is not None else [m for m in self.all_minis() if m.get('invoke') == 1]
    n = 0
    for m in pool:
        if m.type == 0x00:
            continue
        if on:
            if m.param[9] == STAGE_HIDE_IN_SCENE:
                m.param[9] = getattr(m, "scene_orig9", STAGE_SHOW_IN_SCENE)
                n += 1
        elif m.param[9] != STAGE_HIDE_IN_SCENE:
            m.scene_orig9 = m.param[9]
            m.param[9] = STAGE_HIDE_IN_SCENE
            n += 1
    return n


def _effect_hide_stripes2(self, hide=True):
    """Linhas de Foco (classe 00, 1º bloco): esconder zera os tamanhos; mostrar devolve os originais."""
    m = self.global_stripes()
    if m is None:
        return False
    if hide:
        cur = (m.get('size1'), m.get('size2'), m.get('size3'))
        if any(cur):
            m.saved_sizes = cur
        for k in ('size1', 'size2', 'size3'):
            m.set(k, 0.0)
    else:
        sizes = getattr(m, "saved_sizes", None) or (0.15, 0.15, 0.0)
        for k, v in zip(('size1', 'size2', 'size3'), sizes):
            m.set(k, v)
    return True


Effect.scene_persist = _effect_scene_persist2
Effect.hide_stripes = _effect_hide_stripes2


def _effect_apply_prelaunch2(self, pre, recolor=True, stage0_only=False):
    """Pré-disparo vindo de um formato pronto (todas as partes) ou de OUTRO efeito qualquer
       (stage0_only=True: só as partes do estágio 0 desse efeito)."""
    color = self.dominant_color() if recolor else None
    src = [m for m in pre.all_minis() if m.type != 0x00 and (not stage0_only or m.get('invoke') == 0)]
    if not src:
        return [], color
    self.remove_minis([m for m in self.all_minis() if m.type != 0x00 and m.get('invoke') == 0
                       and not m.group.startswith("extra:")])
    added = self.import_minis(pre, src)
    for m in added:
        m.set('invoke', 0)
        if not stage0_only:
            if m.param[9] in (3, 5):
                m.param[9] = 2
            m.param[10] = 0
        m.group = "prelaunch"
    if color and added:
        self.recolor_parts(added, color)
    return added, color


Effect.apply_prelaunch = _effect_apply_prelaunch2


# ---------------------------------------------------------------- V00: parte inicial (32 bytes por sessão)
V00_TEX, V00_BLEND, V00_STEPS = 0x00, 0x02, 0x04
BLEND_INVERSE = 0                # cor inversa (subtrai a cor do fundo: efeitos negros)
SHAPE05_BLEND = 0x0A             # forma da classe 05: 01 = brilho (soma), 00 = mistura normal (fumaça, poeira)


def v00_entries(mini):
    """[(offset_da_entrada, [offsets_das_etapas])] de um V00."""
    v = mini.files[0] if mini.files else b""
    if len(v) < 32 or v[:4] != b"V000":
        return []
    n = v[4]
    start = struct.unpack_from('<H', v, 8)[0]
    total = (len(v) - start) // 64 if start <= len(v) else 0
    counts = [v[32 + 32 * i + V00_STEPS] for i in range(n) if 32 + 32 * i + 32 <= len(v)]
    if sum(counts) != total:
        counts = [3] * n if n * 3 == total else [total]
    out, k = [], 0
    for i, c in enumerate(counts):
        out.append((32 + 32 * i, [start + 64 * (k + j) for j in range(c)]))
        k += c
    return out


def _mini_blend_points(self):
    """Bytes de modo de mistura deste mini-efeito: [(arquivo, offset, rótulo)]."""
    if self.type == 0x0E and self.files:
        return [(0, o + V00_BLEND, "V00 %d" % (i + 1)) for i, (o, _) in enumerate(v00_entries(self))]
    if self.type == 0x05 and len(self.files) == 2:
        return [(1 - getattr(self, "shader_idx", 1), SHAPE05_BLEND, "forma")]
    return []


def _mini_textures(self, cat):
    """Imagens (índices) do DBT usadas por este mini-efeito."""
    if self.type == 0x00 or not cat or self.get('dbt') >= len(cat.dbts):
        return set()
    if self.type == 0x0E:
        return set(self.files[0][o + V00_TEX] for o, _ in v00_entries(self))
    return {self.get('tex')}


Mini.blend_points = _mini_blend_points
Mini.textures = _mini_textures


def _effect_isolate_dbt(self, minis):
    """Se um DBT usado pelos mini-efeitos indicados também é usado por outros, cria uma cópia só para eles.
       Assim pintar/escurecer a textura não estraga as outras partes. Devolve quantos DBTs foram copiados."""
    ids = set(id(m) for m in minis)
    n = 0
    for c in self.cats:
        for di in range(len(c.dbts)):
            users = [m for m in c.minis if m.get('dbt') == di]
            mine = [m for m in users if id(m) in ids]
            if mine and len(mine) < len(users):
                c.dbts.append(bytes(c.dbts[di]))
                for m in mine:
                    m.set('dbt', len(c.dbts) - 1)
                n += 1
    return n


def _palette_map(d, images, fn):
    """Aplica fn(r, g, b, a) -> (r, g, b, a) nas paletas das imagens indicadas (None = todas)."""
    buf = bytearray(d)
    for i, img in enumerate(dbt_info(d)):
        if (images is not None and i not in images) or not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        for p in range(off, off + size - 3, 4):
            buf[p], buf[p + 1], buf[p + 2], buf[p + 3] = [max(0, min(255, int(round(v)))) for v in
                                                          fn(buf[p], buf[p + 1], buf[p + 2], buf[p + 3])]
    return bytes(buf)


def _effect_make_dark(self, minis, tint=(0, 0, 0), strength=1.0, textures=True, isolate=True, classic=True):
    """EFEITOS NEGROS.
       • V00 (classe 0E): byte +02 de cada sessão = 0 (cor inversa: o jogo SUBTRAI a cor). A cor das etapas vira o
         complemento do tom desejado (preto → branco) e a textura vira tons de cinza pelo brilho, para subtrair por igual.
       • Classe 05 (experimental, classic=True): forma +0x0A = 00 (mistura normal, como nas fumaças) e o shader recebe o
         próprio tom escuro; a textura vira branca com o brilho no alfa (o formato fica, a cor vem do shader).
       Só textura preta não funciona porque, no modo de brilho (soma), preto não acrescenta nada.
       Devolve (feitos, ignorados, dbts_copiados)."""
    tint = [max(0, min(255, int(c))) for c in tint[:3]]
    comp = [255 - c for c in tint]
    k = max(0.0, min(1.5, float(strength)))
    done, skipped = [], []
    for m in minis:
        if m.type == 0x0E and v00_entries(m):
            m.orig_blend = getattr(m, "orig_blend", None) or {o: m.files[0][o] for _, o, _ in
                                                                [(f, o, l) for f, o, l in m.blend_points()]}
            for fi, o, _ in m.blend_points():
                m.files[fi][o] = BLEND_INVERSE
            for row in m.color_rows():
                r, g, b, a = m.read_rgba(row)
                m.write_rgba(row, [comp[0] * k, comp[1] * k, comp[2] * k, a])
            done.append(m)
        elif m.type == 0x05 and classic and m.blend_points():
            fi, o, _ = m.blend_points()[0]
            m.orig_blend = getattr(m, "orig_blend", None) or {o: m.files[fi][o]}
            m.files[fi][o] = 0
            for row in m.color_rows():
                r, g, b, a = m.read_rgba(row)
                if max(r, g, b) < MIN_COLOR and a < MIN_COLOR:
                    continue
                m.write_rgba(row, [tint[0], tint[1], tint[2], min(255.0, a * max(0.5, k))])
            done.append(m)
        elif m.type != 0x00:
            skipped.append(m)
    copied = 0
    if textures and done:
        if isolate:
            copied = self.isolate_dbt(done)
        for c in self.cats:
            for di, d in enumerate(c.dbts):
                users = [m for m in c.minis if m.get('dbt') == di]
                mine = [m for m in users if m in done]
                if not mine or (not isolate and len(mine) < len(users)):
                    continue
                v00_imgs, s05_imgs = set(), set()
                for m in mine:
                    (v00_imgs if m.type == 0x0E else s05_imgs).update(m.textures(c))
                def gray(r, g, b, a):
                    v = max(r, g, b)
                    return v, v, v, a
                def white_alpha(r, g, b, a):
                    v = max(r, g, b)
                    return 255, 255, 255, min(128, a * v / 255.0 * 1.15)
                if v00_imgs:
                    d = _palette_map(d, v00_imgs, gray)
                if s05_imgs:
                    d = _palette_map(d, s05_imgs - v00_imgs, white_alpha)
                c.dbts[di] = d
    return done, skipped, copied


def _effect_restore_blend(self, minis):
    n = 0
    for m in minis:
        orig = getattr(m, "orig_blend", None)
        for fi, o, _ in m.blend_points():
            val = orig.get(o) if orig else None
            if val is None:
                val = 1
            if m.files[fi][o] != val:
                m.files[fi][o] = val
                n += 1
    return n


Effect.isolate_dbt = _effect_isolate_dbt
Effect.make_dark = _effect_make_dark
Effect.restore_blend = _effect_restore_blend


# ---------------------------------------------------------------- colorir com degradê (de acordo com a textura)
def gradient_at(stops, t):
    """stops: [(pos 0-1, (r, g, b))] em ordem. Devolve a cor (r, g, b) em t."""
    t = max(0.0, min(1.0, t))
    if t <= stops[0][0]:
        return stops[0][1]
    for (pa, ca), (pb, cb) in zip(stops, stops[1:]):
        if t <= pb:
            u = 0.0 if pb <= pa else (t - pa) / (pb - pa)
            return tuple(ca[i] + (cb[i] - ca[i]) * u for i in range(3))
    return stops[-1][1]


def _grad_pixel(r, g, b, stops, keep_light=True, gamma=1.0):
    """Mapeia a cor pelo brilho: partes escuras/bordas pegam o começo do degradê, núcleo claro pega o fim.
       keep_light: mantém o brilho original (a forma do brilho não muda, só a cor)."""
    mx = max(r, g, b)
    if mx <= 0:
        return r, g, b
    lum = (0.299 * min(r, 255) + 0.587 * min(g, 255) + 0.114 * min(b, 255)) / 255.0
    t = lum ** gamma if gamma != 1.0 else lum
    gr, gg, gb = gradient_at(stops, t)
    if not keep_light:
        return gr, gg, gb
    h, s, _ = colorsys.rgb_to_hsv(gr / 255.0, gg / 255.0, gb / 255.0)
    v = min(1.0, mx / 255.0)
    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
    scale = mx / 255.0 if mx > 255 else 1.0          # floats do shader acima de 255 continuam estourados
    return nr * 255 * scale, ng * 255 * scale, nb * 255 * scale


def _mini_recolor_gradient(self, stops, keep_light=True, gamma=1.0):
    rows = self.color_rows()
    for row in rows:
        r, g, b, a = self.read_rgba(row)
        if max(r, g, b) <= 0 or (row[2] == 'f' and max(r, g, b) < MIN_COLOR):
            continue
        nr, ng, nb = _grad_pixel(r, g, b, stops, keep_light, gamma)
        self.write_rgba(row, [nr, ng, nb, a])
    return len(rows)


def recolor_dbt_gradient(d, stops, images=None, keep_light=True, gamma=1.0):
    return _palette_map(d, images, lambda r, g, b, a: _grad_pixel(r, g, b, stops, keep_light, gamma) + (a,))


def _effect_recolor_gradient(self, minis, stops, textures=True, keep_light=True, gamma=1.0, isolate=False,
                             per_class=None):
    """Degradê no efeito: shaders/V00/saídas de luz e (opcional) as paletas das texturas usadas pelos
       mini-efeitos indicados. per_class: {classe: stops} para dar um degradê diferente a algumas classes
       (contraste: raios e iluminação com o tom vizinho)."""
    per_class = per_class or {}
    for m in minis:
        m.recolor_gradient(per_class.get(m.type, stops), keep_light, gamma)
    n = 0
    if textures:
        if isolate:
            self.isolate_dbt(minis)
        ids = set(id(m) for m in minis)
        for c in self.cats:
            for di, d in enumerate(c.dbts):
                users = [m for m in c.minis if m.get('dbt') == di]
                mine = [m for m in users if id(m) in ids]
                if not mine:
                    continue
                st = per_class.get(c.type, stops)
                imgs = None if len(mine) == len(users) else set().union(*[m.textures(c) for m in mine])
                nd = recolor_dbt_gradient(d, st, imgs, keep_light, gamma)
                if nd != d:
                    c.dbts[di] = nd
                    n += 1
    return n


Mini.recolor_gradient = _mini_recolor_gradient
Effect.recolor_gradient = _effect_recolor_gradient


def contrast_stops(stops, shift_deg):
    """Mesmo degradê com o tom deslocado (para as partes de contraste)."""
    out = []
    for p, c in stops:
        h, s, v = colorsys.rgb_to_hsv(*[x / 255.0 for x in c])
        r, g, b = colorsys.hsv_to_rgb((h + shift_deg / 360.0) % 1.0, s, v)
        out.append((p, (r * 255, g * 255, b * 255)))
    return out


# ---------------------------------------------------------------- textura de cada mini-efeito (para prévias)
def mini_sprite(eff, mini, session=None):
    """(rgba, w, h) da textura usada pelo mini-efeito (ou pela sessão do V00). None se não houver."""
    c = eff.cat_of(mini)
    if c is None or mini.type == 0x00 or mini.get('dbt') >= len(c.dbts):
        return None
    d = c.dbts[mini.get('dbt')]
    idx = mini.get('tex')
    if mini.type == 0x0E:
        ents = v00_entries(mini)
        if ents:
            o = ents[min(session or 0, len(ents) - 1)][0]
            idx = mini.files[0][o + V00_TEX]
    infos = dbt_info(d)
    if not infos:
        return None
    idx = min(idx, len(infos) - 1)
    try:
        return dbt_image_rgba(d, idx)
    except Exception:
        return None


def scene_row(data, mp, ev):
    """(X, Y, Z) da linha mapa/evento do 02_.dat (os três primeiros floats, conferido)."""
    o = (mp * SCENE_EVENTS + ev) * 16
    if o + 12 <= len(data):
        return struct.unpack_from('<3f', data, o)
    return (0.0, 0.0, 0.0)


def scene_set3(data, mp, ev, x, y, z):
    buf = bytearray(data if len(data) >= 2816 else bytes(2816))
    struct.pack_into('<3f', buf, (mp * SCENE_EVENTS + ev) * 16, float(x), float(y), float(z))
    return bytes(buf)


# ================================================================ v1.6
# ---------------------------------------------------------------- efeito negro por inversão (método do Lord)
def _dominant_hs(pal_entries):
    """Tom e saturação predominantes de uma lista de (r, g, b, a)."""
    import math
    sx = sy = ws = ss = 0.0
    for r, g, b, a in pal_entries:
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        w = s * v * (a / 128.0 + 0.05)
        sx += math.cos(2 * math.pi * h) * w
        sy += math.sin(2 * math.pi * h) * w
        ss += s * w
        ws += w
    if ws < 1e-6:
        return None
    return (math.atan2(sy, sx) / (2 * math.pi)) % 1.0, max(0.35, min(1.0, ss / ws))


def dbt_invert_recolor(d, images=None, fallback_rgb=None, strength=1.0):
    """'Ctrl+I' na textura e recolorir: a cor é invertida, o que ficou preto (núcleo branco) continua preto e o
       resto recebe de volta o tom que a textura tinha (tom da própria cor; cinzas usam o tom predominante).
       strength < 1 mistura com o original."""
    buf = bytearray(d)
    fb = colorsys.rgb_to_hsv(*[c / 255.0 for c in fallback_rgb])[:2] if fallback_rgb else None
    for i, img in enumerate(dbt_info(d)):
        if (images is not None and i not in images) or not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        ents = [tuple(buf[p:p + 4]) for p in range(off, off + size - 3, 4)]
        dom = _dominant_hs([e for e in ents if e[3] > 4]) or (0.0, 0.0)   # textura cinza continua cinza
        # fundo preto opaco (texturas feitas para somar luz): o preto era 'invisível'; depois de inverter ele
        # ficaria claro, então o alfa passa a seguir o brilho original
        black_bg = False
        if img['pixels']:
            import ps2tex
            po, ps = img['pixels']
            idx, _pal = ps2tex.decode(d[po:po + ps], d[off:off + size], img['w'], img['h'], img['psm'])
            if idx:
                dark = sum(1 for q in idx[::7] if q < len(ents) and ents[q][3] >= 96 and max(ents[q][:3]) < 26)
                black_bg = dark > 0.3 * len(idx[::7])
        k2 = max(0.0, min(1.0, strength))
        for k, p in enumerate(range(off, off + size - 3, 4)):
            r, g, b, a = ents[k]
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.18:
                h, s = dom
            lv = max(255 - r, 255 - g, 255 - b) / 255.0          # brilho da cor invertida
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, lv)
            buf[p] = int(round(r + (nr * 255 - r) * k2))
            buf[p + 1] = int(round(g + (ng * 255 - g) * k2))
            buf[p + 2] = int(round(b + (nb * 255 - b) * k2))
            if black_bg:
                na = a * min(1.0, v * 1.6)
                buf[p + 3] = int(round(a + (na - a) * k2))
    return bytes(buf)


def _effect_make_dark_invert(self, minis, strength=1.0, set_blend=False, isolate=True):
    """Efeito negro pelo método da inversão: texturas usadas pelos mini-efeitos indicados passam por
       'Ctrl+I + recolorir'. set_blend também liga a cor inversa (byte +02) dos V00 (experimental).
       Devolve (feitos, dbts_alterados, dbts_copiados)."""
    ms = [m for m in minis if m.type != 0x00]
    copied = self.isolate_dbt(ms) if isolate else 0
    ids = set(id(m) for m in ms)
    changed = 0
    for c in self.cats:
        for di, d in enumerate(c.dbts):
            mine = [m for m in c.minis if m.get('dbt') == di and id(m) in ids]
            if not mine:
                continue
            users = [m for m in c.minis if m.get('dbt') == di]
            imgs = None if len(mine) == len(users) else set().union(*[m.textures(c) for m in mine])
            fb = None
            for m in mine:
                rows = m.color_rows()
                if rows:
                    fb = max((m.read_rgba(r)[:3] for r in rows), key=lambda v: max(v))
                    fb = [min(255, x) for x in fb]
                    break
            nd = dbt_invert_recolor(d, imgs, fb, strength)
            if nd != d:
                c.dbts[di] = nd
                changed += 1
    if set_blend:
        for m in ms:
            if m.type == 0x0E:
                m.orig_blend = getattr(m, "orig_blend", None) or {o: m.files[fi][o] for fi, o, _ in m.blend_points()}
                for fi, o, _ in m.blend_points():
                    m.files[fi][o] = BLEND_INVERSE
    return ms, changed, copied


Effect.make_dark_invert = _effect_make_dark_invert


# ---------------------------------------------------------------- texturas animadas (sprite sheet do V00)
V00_SHEET_FLAG = 0x10            # bit 0x10 do byte +0x10 da sessão: a textura é uma folha de quadros (sprites)


def v00_sheet(mini, session):
    """(colunas, linhas, quadros_por_sprite) se a sessão do V00 anima a textura como folha de sprites.
       Conferido nos 41 casos com o bit ligado: +0x0C = 0 → 2×2, +0x0C = 1 → 4×2. O ritmo (+0x18) é estimado."""
    ents = v00_entries(mini)
    if not ents:
        return None
    o = ents[min(session or 0, len(ents) - 1)][0]
    v = mini.files[0]
    if not v[o + 0x10] & V00_SHEET_FLAG:
        return None
    cols = 2 << min(2, v[o + 0x0C])
    return cols, 2, max(1, v[o + 0x18] or 2)


def v00_session_life(mini, session):
    """Duração da sessão do V00 em quadros (u16 em +0x08 da parte inicial; 20 a 330 nos modelos)."""
    ents = v00_entries(mini)
    if not ents:
        return 0
    o = ents[min(session or 0, len(ents) - 1)][0]
    return struct.unpack_from('<H', mini.files[0], o + 8)[0]


# ---------------------------------------------------------------- partículas da classe 05 (hipótese)
def shape05_particles(mini):
    """Quantas cópias da textura a forma da classe 05 emite (u16 em +0x20 da forma: 1 a 20 nos modelos;
       ex.: Bolinhas 7, Madam 4). É uma hipótese tirada dos dados; o movimento é aproximado na prévia."""
    if mini.type != 0x05 or len(mini.files) != 2:
        return 1
    sp = mini.files[1 - getattr(mini, "shader_idx", 1)]
    if len(sp) < 0x24:
        return 1
    n = struct.unpack_from('<H', sp, 0x20)[0]
    return max(1, min(24, n))


# ---------------------------------------------------------------- importar respeitando o original
def _effect_alpha_profile(self, minis=None):
    """Alfa médio das cores (por classe) dos mini-efeitos (ou do efeito todo)."""
    acc = {}
    for m in (minis if minis is not None else self.all_minis()):
        for row in m.color_rows():
            r, g, b, a = m.read_rgba(row)
            if max(r, g, b) < MIN_COLOR or a <= 0:
                continue
            s = acc.setdefault(m.type, [0.0, 0])
            s[0] += min(a, 255)
            s[1] += 1
    return {t: v[0] / v[1] for t, v in acc.items() if v[1]}


def _effect_match_import(self, added, ref_profile, depth16=None, opacity=True, colors=True):
    """Depois de importar: aproxima a opacidade dos importados da do efeito original (por classe; sem a classe,
       usa a média geral) e reduz as texturas importadas para 16 cores se o original usa 16 cores."""
    n_alpha = n_tex = 0
    if opacity and ref_profile and added:
        mine = _effect_alpha_profile(self, added)
        overall = sum(ref_profile.values()) / len(ref_profile)
        for m in added:
            cur = mine.get(m.type)
            want = ref_profile.get(m.type, overall)
            if not cur or cur <= 0:
                continue
            k = max(0.15, min(1.0, want / cur))          # só abaixa (o importado costuma vir brilhoso demais)
            if k >= 0.999:
                continue
            for row in m.color_rows():
                r, g, b, a = m.read_rgba(row)
                m.write_rgba(row, [r, g, b, a * k])
            n_alpha += 1
    if colors and depth16 and added:
        cnt, _, _ = self.reduce16(added, self.reduce16_check(added))   # pula as que perderiam a transparência
        n_tex = cnt
    return n_alpha, n_tex


def _effect_prefers_16(self):
    a, b = self.color_depth()
    return b > 0 and b >= a


Effect.alpha_profile = _effect_alpha_profile
Effect.match_import = _effect_match_import
Effect.prefers_16 = _effect_prefers_16


# ================================================================ v1.7
# ---------------------------------------------------------------- reduzir para 16 cores sem estragar a transparência
def _images_for(self, minis):
    """{(cat, di): set(imagens)} das texturas usadas pelos mini-efeitos (None = todas de todos os DBTs)."""
    out = {}
    for c in self.cats:
        for di, d in enumerate(c.dbts):
            if minis is None:
                imgs = set(range(len(dbt_info(d))))
            else:
                ids = set(id(m) for m in minis)
                imgs = set()
                for m in c.minis:
                    if id(m) in ids and m.get('dbt') == di:
                        imgs |= m.textures(c)
            if imgs:
                out[(id(c), di)] = (c, di, imgs)
    return out


def _effect_reduce16_check(self, minis=None):
    """Simula a redução 256 → 16 e devolve [(cat, di, img)] das imagens em que a transparência quebraria."""
    import ps2tex
    broken = []
    for c, di, imgs in _images_for(self, minis).values():
        d = c.dbts[di]
        for i, im in enumerate(dbt_info(d)):
            if i not in imgs or im['psm'] != 0x13 or not im['pixels'] or not im['clut']:
                continue
            po, ps = im['pixels']
            co, cs = im['clut']
            idx, pal = ps2tex.decode(d[po:po + ps], d[co:co + cs], im['w'], im['h'], 0x13)
            qi, qp = ps2tex.quantize16(idx, pal)
            if ps2tex.transparency_broken(idx, pal, qi, qp):
                broken.append((c, di, i))
    return broken


def _effect_reduce16(self, minis=None, skip=()):
    """Reduz para 16 cores as imagens usadas pelos mini-efeitos (ou todas), menos as de 'skip' [(cat, di, img)]."""
    before = len(self.to_bytes())
    sk = set((id(c), di, i) for c, di, i in skip)
    count = 0
    for c, di, imgs in _images_for(self, minis).values():
        only = set(i for i in imgs if (id(c), di, i) not in sk)
        if not only:
            continue
        nd, k = dbt_reduce_colors(c.dbts[di], only)
        if k:
            c.dbts[di] = nd
            count += k
    return count, before, len(self.to_bytes())


Effect.reduce16_check = _effect_reduce16_check
Effect.reduce16 = _effect_reduce16


# ---------------------------------------------------------------- partes 100% preto e branco
GRAY_SAT = 0.08


def _rows_gray(m):
    for row in m.color_rows():
        r, g, b, a = m.read_rgba(row)
        mx = max(r, g, b)
        if mx < MIN_COLOR:
            continue
        if (mx - min(r, g, b)) / float(mx) > GRAY_SAT:
            return False
    return True


def _texture_gray(d, imgs):
    for i, im in enumerate(dbt_info(d)):
        if (imgs is not None and i not in imgs) or not im['clut']:
            continue
        off, size = im['clut']
        for p in range(off, off + size - 3, 4):
            r, g, b, a = d[p], d[p + 1], d[p + 2], d[p + 3]
            mx = max(r, g, b)
            if a > 4 and mx > 12 and (mx - min(r, g, b)) / float(mx) > GRAY_SAT * 1.5:
                return False
    return True


def _effect_gray_minis(self, minis):
    """Mini-efeitos 100% preto e branco: cores (shader/V00/saída de luz) e textura sem nenhum tom."""
    out = []
    for m in minis:
        if m.type == 0x00 or not _rows_gray(m):
            continue
        c = self.cat_of(m)
        if c is not None and m.get('dbt') < len(c.dbts):
            if not _texture_gray(c.dbts[m.get('dbt')], m.textures(c)):
                continue
        out.append(m)
    return out


def _effect_recolor_dbts_of(self, minis, fn):
    """Aplica fn(dbt, imagens) só nas imagens usadas pelos mini-efeitos indicados. Devolve quantos DBTs mudaram."""
    n = 0
    for c, di, imgs in _images_for(self, minis).values():
        users = [m for m in c.minis if m.get('dbt') == di]
        allimg = set(range(len(dbt_info(c.dbts[di]))))
        nd = fn(c.dbts[di], None if imgs >= allimg else imgs)
        if nd != c.dbts[di]:
            c.dbts[di] = nd
            n += 1
    return n


Effect.gray_minis = _effect_gray_minis
Effect.recolor_dbts_of = _effect_recolor_dbts_of


# ---------------------------------------------------------------- efeito negro v3
def dbt_dark_chroma(d, images=None, strength=1.0, alpha_from_light=False):
    """Tira o 'branco' de cada cor da paleta: o miolo branco vira preto e as partes coloridas mantêm o tom
       e o brilho próximos do original (cor − componente branca). alpha_from_light: o alfa passa a seguir o
       brilho original (para mistura normal, em que o escuro deixaria de ser invisível)."""
    k = max(0.0, min(1.0, strength))
    buf = bytearray(d)
    for i, img in enumerate(dbt_info(d)):
        if (images is not None and i not in images) or not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        for p in range(off, off + size - 3, 4):
            r, g, b, a = buf[p], buf[p + 1], buf[p + 2], buf[p + 3]
            w = min(r, g, b)
            nr, ng, nb = r - w * k, g - w * k, b - w * k
            buf[p], buf[p + 1], buf[p + 2] = int(round(nr)), int(round(ng)), int(round(nb))
            if alpha_from_light:
                v = max(r, g, b) / 255.0
                buf[p + 3] = int(round(a * min(1.0, v * 1.4)))
    return bytes(buf)


def dbt_white_mask(d, images=None):
    """Só a parte branca de cada cor, em cinza (para a camada que SUBTRAI a cor e escurece)."""
    buf = bytearray(d)
    for i, img in enumerate(dbt_info(d)):
        if (images is not None and i not in images) or not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        for p in range(off, off + size - 3, 4):
            w = min(buf[p], buf[p + 1], buf[p + 2])
            buf[p] = buf[p + 1] = buf[p + 2] = w
    return bytes(buf)


SHADER_NEUTRAL = 128.0           # no PS2, 128 = 1,0 (a cor da textura passa sem ser tingida)


def _effect_make_dark3(self, minis, strength=1.0, keep_color=True):
    """EFEITO NEGRO (v1.7). Preto só aparece se o mini-efeito NÃO somar a luz:
       • Complementos/Acabamentos (05): forma +0x0A = 00 (mistura normal, a das fumaças); o shader fica neutro
         (128) para não tingir; a textura perde o branco (miolo preto) e o alfa passa a seguir o brilho original.
       • V00: vira duas camadas. A original continua somando luz só com a cor (sem o branco) e uma cópia passa a
         SUBTRAIR (byte +02 = 0) só a parte branca da textura, escurecendo o miolo.
       • Outras classes: ainda sem modo de mistura conhecido; só perdem o branco (ficam transparentes no miolo).
       Devolve (normais, v00_duplicados, sem_modo, texturas_copiadas)."""
    ms = [m for m in minis if m.type != 0x00]
    normal, layered, other = [], [], []
    copies = []
    for m in ms:
        if m.type == 0x0E and m.blend_points():
            cat = self.cat_of(m)
            if keep_color:
                dup = self.import_minis(self, [m])[0]
                dup.group = m.group
                # a cópia fica logo depois da original na lista
                cat.minis.remove(dup)
                cat.minis.insert(cat.minis.index(m) + 1, dup)
                copies.append(dup)
                layered.append((m, dup))
            else:
                layered.append((None, m))
        elif m.type == 0x05 and m.blend_points():
            normal.append(m)
        else:
            other.append(m)
    sub = [d for _, d in layered]
    keep = [o for o, _ in layered if o is not None]
    copied = self.isolate_dbt(normal + other + keep + sub)
    # 05: mistura normal + shader neutro + textura sem branco com alfa pelo brilho
    for m in normal:
        fi, o, _ = m.blend_points()[0]
        m.orig_blend = getattr(m, "orig_blend", None) or {o: m.files[fi][o]}
        m.files[fi][o] = 0
        for row in m.color_rows():
            r, g, b, a = m.read_rgba(row)
            if max(r, g, b) < MIN_COLOR and a < MIN_COLOR:
                continue
            m.write_rgba(row, [SHADER_NEUTRAL, SHADER_NEUTRAL, SHADER_NEUTRAL, a])
    self.recolor_dbts_of(normal, lambda d, im: dbt_dark_chroma(d, im, strength, alpha_from_light=True))
    # V00: camada de cor (sem branco) + camada que subtrai o branco
    self.recolor_dbts_of(keep, lambda d, im: dbt_dark_chroma(d, im, strength))
    self.recolor_dbts_of(sub, lambda d, im: dbt_white_mask(d, im))
    for m in sub:
        m.orig_blend = getattr(m, "orig_blend", None) or {o: m.files[fi][o] for fi, o, _ in m.blend_points()}
        for fi, o, _ in m.blend_points():
            m.files[fi][o] = BLEND_INVERSE
        for row in m.color_rows():
            r, g, b, a = m.read_rgba(row)
            v = 255 * max(0.0, min(1.0, strength))
            m.write_rgba(row, [v, v, v, a])
    # outras classes: só perdem o branco
    self.recolor_dbts_of(other, lambda d, im: dbt_dark_chroma(d, im, strength))
    return normal, layered, other, copied


Effect.make_dark3 = _effect_make_dark3


def _effect_dark_textures_only(self, cat, di, images, strength=1.0):
    """Para a janela de Texturas: aplica 'tirar o branco' numa imagem/DBT (o miolo branco vira preto)."""
    cat.dbts[di] = dbt_dark_chroma(cat.dbts[di], images, strength)


Effect.dark_texture = _effect_dark_textures_only


def _effect_recolor_contrast2(self, target_rgb, shift_deg=-35, force=0.0, textures=True, minis=None):
    """Colorir com contraste só nos mini-efeitos indicados (e nas texturas deles)."""
    ms = self.all_minis() if minis is None else minis
    th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
    alt_h = (th + shift_deg / 360.0) % 1.0
    ar, ag, ab = colorsys.hsv_to_rgb(alt_h, ts, tv)
    alt = (int(ar * 255), int(ag * 255), int(ab * 255))
    dom = self.dominant_color()
    dh = colorsys.rgb_to_hsv(*[c / 255.0 for c in dom])[0] if dom else None
    for m in ms:
        use_alt = m.type in (0x10, 0x12)
        if not use_alt and dh is not None:
            hs = []
            for row in m.color_rows():
                r, g, b, a = m.read_rgba(row)
                if max(r, g, b) >= MIN_COLOR:
                    h, s, v = colorsys.rgb_to_hsv(min(r, 255) / 255, min(g, 255) / 255, min(b, 255) / 255)
                    if s > 0.2:
                        hs.append(h)
            if hs:
                avg = sum(hs) / len(hs)
                diff = min(abs(avg - dh), 1 - abs(avg - dh))
                use_alt = diff > 20 / 360.0
        m.recolor(alt if use_alt else target_rgb, False, force)
    if textures:
        self.recolor_dbts_of(ms, lambda d, im: _recolor_imgs(d, im, target_rgb, False, force))
    return alt


def _recolor_imgs(d, images, target_rgb, keep_saturation=False, force=0.0):
    """recolor_dbt2 limitado a algumas imagens do DBT."""
    if images is None:
        return recolor_dbt2(d, target_rgb, keep_saturation, force)
    th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target_rgb])
    buf = bytearray(d)
    for i, img in enumerate(dbt_info(d)):
        if i not in images or not img['clut'] or not img['colors']:
            continue
        off, size = img['clut']
        for p in range(off, off + size - 3, 4):
            r, g, b = buf[p], buf[p + 1], buf[p + 2]
            if max(r, g, b) == 0:
                continue
            nr, ng, nb = _tint(r, g, b, th, ts, keep_saturation, force, tv)
            buf[p], buf[p + 1], buf[p + 2] = int(round(nr * 255)), int(round(ng * 255)), int(round(nb * 255))
    return bytes(buf)


Effect.recolor_contrast2 = _effect_recolor_contrast2
recolor_dbt_imgs = _recolor_imgs


# ================================================================ v1.9: texturas repetidas ao trocar formatos
# A v1.8 reaproveitava, já na importação, qualquer DBT com os mesmos pixels (mesmo com outra cor) e o jogo
# passou a travar ao trocar o comportamento. Agora a importação é igual à da v1.7; a limpeza opcional abaixo
# só junta, DEPOIS de tudo pintado, DBTs com pixels iguais E cores praticamente iguais.
def dbt_pixel_key(d):
    """Assinatura só dos PIXELS de um DBT (tamanho, formato e índices de cada imagem), sem a paleta."""
    out = []
    for im in dbt_info(d):
        po, ps = im['pixels'] if im['pixels'] else (0, 0)
        out.append((im['w'], im['h'], im['psm'], bytes(d[po:po + ps])))
    return tuple(out)


def _palettes_close(a, b, tol=8):
    ia, ib = dbt_info(a), dbt_info(b)
    if len(ia) != len(ib):
        return False
    for x, y in zip(ia, ib):
        if not x['clut'] or not y['clut'] or x['clut'][1] != y['clut'][1]:
            return False
        pa, pb = a[x['clut'][0]: x['clut'][0] + x['clut'][1]], b[y['clut'][0]: y['clut'][0] + y['clut'][1]]
        if any(abs(u - v) > tol for u, v in zip(pa, pb)):
            return False
    return True


def _effect_merge_new_dbts(self, new_ids, tol=8):
    """Para os DBTs usados SÓ por partes novas: se já existe outro DBT na mesma classe com os mesmos pixels e
       cores praticamente iguais, as partes novas passam a usar esse e a cópia sai. Devolve quantos saíram."""
    removed = 0
    for c in self.cats:
        for di in range(len(c.dbts)):
            users = [m for m in c.minis if m.get('dbt') == di]
            if not users or not all(id(m) in new_ids for m in users):
                continue
            k = dbt_pixel_key(c.dbts[di])
            for dj in range(len(c.dbts)):
                if dj == di:
                    continue
                others = [m for m in c.minis if m.get('dbt') == dj]
                if not others or any(id(m) in new_ids for m in others):
                    continue
                if dbt_pixel_key(c.dbts[dj]) == k and _palettes_close(c.dbts[di], c.dbts[dj], tol):
                    for m in users:
                        m.set('dbt', dj)
                    removed += 1
                    break
    if removed:
        self.prune_dbts()
    return removed


Effect.merge_new_dbts = _effect_merge_new_dbts


def _effect_is_dark(self):
    """O efeito já usa o efeito negro? (Complemento em mistura normal ou V00 com cor inversa)"""
    for m in self.all_minis():
        if m.type == 0x05 and m.blend_points():
            fi, o, _ = m.blend_points()[0]
            if m.files[fi][o] == 0 and any(abs(m.read_rgba(r)[0] - SHADER_NEUTRAL) < 1 for r in m.color_rows()):
                return True
        if m.type == 0x0E and any(m.files[fi][o] == BLEND_INVERSE for fi, o, _ in m.blend_points()):
            rows = [m.read_rgba(r) for r in m.color_rows()]
            if rows and all(r[0] == r[1] == r[2] and r[0] >= 150 for r in rows):   # camada criada pelo efeito negro
                return True
    return False


Effect.is_dark = _effect_is_dark
