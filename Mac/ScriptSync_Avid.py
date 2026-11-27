#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ScriptSync_Avid — enlaza cada script de Avid ("NOMBRE Script.avc") con el subclip
que se llama NOMBRE (lo busca en todos los bins del proyecto) y escribe una
script mark por cada bloque [HH:MM:SS] de la desgrabacion.

Uso:  python ScriptSync_Avid.py [CARPETA_PROYECTO] [--simular] [--forzar]
(sin carpeta, la pregunta)
Media Composer tiene que estar CERRADO.
--forzar : tambien rehace scripts que ya tienen un take enlazado.
--simular: muestra que haria, sin modificar nada.
Backups en CARPETA_PROYECTO/_Backup_ScriptSync/<fecha>/
"""
import os, sys, re, io, struct, shutil, datetime, time, random, shlex
try:
    import avb
    from avb import core, utils
except ImportError:
    sys.exit("Falta pyavb. Instalalo con:  pip install pyavb")

def u32(v): return struct.pack('<I', v & 0xFFFFFFFF)

# ----------------------------------------------------------- lectura cruda .avc
def leer_avc(path):
    d = open(path, 'rb').read()
    i = 8 + 4; l = struct.unpack_from('<H', d, i)[0]; i += 2 + l + 1
    l = struct.unpack_from('<H', d, i)[0]; i += 2 + l
    cnt, root = struct.unpack_from('<II', d, i); i += 8 + 20
    l = struct.unpack_from('<H', d, i)[0]; i += 2 + l + 16
    o = []
    for _ in range(cnt):
        c = d[i:i+4]; s = struct.unpack_from('<I', d, i+4)[0]; o.append((c, d[i+8:i+8+s])); i += 8 + s
    return o

# ----------------------------------------------------------- plantillas (de MC 2026.8)
GEOMETRIA = bytes.fromhex('01000c00000001004500a4011a04e70500000000000000000600')
RESTO_SCPT = bytes.fromhex('00000000010001280000000101420001024200010347000200000104420101054201420042014201010'
                           '64c0800') + b'Segoe UI' + b'\x03'
STKE_X = 664; SSLT_X1, SSLT_X2 = 591, 737
STKE_COLA = bytes.fromhex('02' + '00' * 13 + '02' + '00' * 13)
STKE_FIN = bytes.fromhex('0102450200470000000047000000004700000000') + b'\x03'

# ----------------------------------------------------------- clases propias para pyavb
def _clase(cid, nombre, props):
    cls = type(nombre, (core.AVBObject,), {'class_id': cid, 'propertydefs_dict': {},
              'propertydefs': [core.AVBPropertyDef(p, p, 'x') for p in props], '__slots__': ()})
    return utils.register_class(cls)

def _w_ref(obj, f, v): obj.root.octx.write_object_ref(obj.root, f, v)

ScriptTexto = _clase(b'BTXT', 'ScriptTexto', ['raw'])
ScriptTexto.write = lambda self, f: f.write(self.raw)
ScriptTake = _clase(b'STke', 'ScriptTake', ['raw'])
ScriptTake.write = lambda self, f: f.write(self.raw)
ScriptSlate = _clase(b'SSlt', 'ScriptSlate', ['take', 'primera', 'ultima'])
def _w_slate(self, f):
    f.write(b'\x02\x01' + u32(SSLT_X1) + u32(SSLT_X2) + u32(self.primera) + u32(self.ultima)
            + b'\x02\x01' + u32(SSLT_X1) + u32(6) + struct.pack('<H', 1))
    _w_ref(self, f, self.take); f.write(b'\x03')
ScriptSlate.write = _w_slate
Script = _clase(b'Scpt', 'Script', ['texto', 'slates', 'mobs'])
def _w_script(self, f):
    f.write(b'\x02\x03'); _w_ref(self, f, self.texto); f.write(GEOMETRIA)
    f.write(u32(len(self.slates)))
    for s in self.slates: _w_ref(self, f, s)
    f.write(u32(int(time.time())) + u32(random.getrandbits(32)))
    f.write(u32(len(self.mobs)))
    for m in self.mobs: _w_ref(self, f, m)
    f.write(RESTO_SCPT)
Script.write = _w_script

# ----------------------------------------------------------- utilidades
def mob_id_bytes(mob_id):
    b = io.BytesIO(); ctx = avb.ioctx.AVBIOContext('little'); ctx.write_mob_id(b, mob_id)
    ser = b.getvalue()
    m = mob_id.material
    pref = struct.pack('<IHH', m.time_low, m.time_mid, m.time_hi_version)
    return pref, ser

RE_TC = re.compile(r'^\s*\[?\s*(\d{1,2})[:;.](\d{2})[:;.](\d{2})(?:([:;.])(\d{2}))?(?:[.,](\d+))?\s*\]?')
RE_HABLANTE = re.compile(r'^\s*(speaker|hablante|orador|interlocutor|entrevistad[oa]r?|persona)\s*\d*\s*:?\s*$', re.I)

def _tc_a_frames(h, m, s, f, base, drop):
    n = ((h * 60 + m) * 60 + s) * base + f
    if drop:
        d = 2 * base // 30
        tm = h * 60 + m
        n -= d * (tm - tm // 10)
    return n

def inicio_tc(mob):
    """TC de inicio del clip en frames (base del timecode), o None."""
    def bajar(m, offset, prof):
        if prof > 6 or m is None: return None
        for t in m.tracks:
            c = t.component
            for x in (c.components if hasattr(c, 'components') else [c]):
                if type(x).__name__ == 'Timecode':
                    return x.start + offset, x.fps, bool(x.flags & 1) if hasattr(x, 'flags') else False
        for t in m.tracks:
            c = t.component
            for x in (c.components if hasattr(c, 'components') else [c]):
                if type(x).__name__ == 'SourceClip' and getattr(x, 'mob_id', None):
                    try: sub = x.mob
                    except Exception: sub = None
                    r = bajar(sub, offset + (x.start_time or 0), prof + 1)
                    if r: return r
        return None
    try:
        return bajar(mob, 0, 0)
    except Exception:
        return None

def lineas_y_marcas(btxt, fps, tc_ini=None, largo=None):
    """Acepta '[HH:MM:SS] Hablante' (relativo al clip) y 'HH:MM:SS:FF - HH:MM:SS:FF'
    (TC de origen). Devuelve (lineas, marcas, modo)."""
    n = struct.unpack_from('<I', btxt, 2)[0]
    lineas = btxt[6:6+n].decode('utf-8', 'replace').split('\r')
    bloques = []
    for i, l in enumerate(lineas):
        m = RE_TC.match(l)
        if not m: continue
        h, mi, se = int(m[1]), int(m[2]), int(m[3])
        if mi > 59 or se > 59: continue
        # linea donde va la marca: la siguiente no vacia, salteando "Speaker N"
        k = i + 1
        resto = l[m.end():].strip(' -\t')
        if resto and not RE_TC.match(resto) and not RE_HABLANTE.match(resto):
            pass
        while k < len(lineas) and not lineas[k].strip(): k += 1
        if k < len(lineas) and RE_HABLANTE.match(lineas[k]):
            k2 = k + 1
            while k2 < len(lineas) and not lineas[k2].strip(): k2 += 1
            if k2 < len(lineas) and not RE_TC.match(lineas[k2]): k = k2
        if k >= len(lineas) or RE_TC.match(lineas[k]): continue
        bloques.append((k, h, mi, se, m[5], m[4], m[6]))
    if not bloques:
        return lineas, [], None
    con_frames = any(b[4] is not None for b in bloques)
    modo = 'relativo'
    marcas = []
    if con_frames and tc_ini:
        ini, base, drop_clip = tc_ini
        drop = drop_clip or any(b[5] == ';' for b in bloques)
        abs_ = [_tc_a_frames(b[1], b[2], b[3], int(b[4] or 0), base, drop) for b in bloques]
        if abs_[0] >= ini and (largo is None or abs_[0] - ini < largo + base):
            modo = 'TC de origen'
            marcas = [(b[0], a - ini) for b, a in zip(bloques, abs_)]
    if not marcas:
        for b in bloques:
            seg = b[1] * 3600 + b[2] * 60 + b[3] + (float('0.' + b[6]) if b[6] else 0)
            fr = int(round(seg * fps))
            if b[4] is not None:
                fr = int(round((b[1] * 3600 + b[2] * 60 + b[3]) * fps)) + int(b[4])
            marcas.append((b[0], fr))
    vistos, limpias = set(), []
    for l, fr in marcas:
        if l in vistos or fr < 0: continue
        vistos.add(l); limpias.append((l, fr))
    return lineas, limpias, modo

def take_raw(primera, ultima, marcas, mob_id):
    pref, ser = mob_id_bytes(mob_id)
    return (b'\x02\x01' + u32(0) + u32(primera) + u32(ultima) + u32(STKE_X) + b'\x01'
            + u32(len(marcas)) + b''.join(u32(l) + u32(fr) for l, fr in marcas)
            + STKE_COLA + pref + b'\x01\x01' + ser + STKE_FIN)

def fps_de(mob):
    for t in mob.tracks:
        try:
            er = t.component.edit_rate
            if er: return float(er), t.component.length
        except Exception: pass
    return 24000 / 1001, None

# ----------------------------------------------------------- buscar subclips
def indexar_clips(proyecto, log=print):
    clips = {}
    for raiz, dirs, files in os.walk(proyecto):
        dirs[:] = [d for d in dirs if d.lower() not in ('trash', '_backup_scriptsync')]
        for fn in files:
            if not fn.lower().endswith('.avb') or fn.startswith('._'): continue
            p = os.path.join(raiz, fn)
            try:
                f = avb.open(p)
                for m in f.content.mobs:
                    if m.mob_type in ('CompositionMob', 'MasterMob') and (m.mob_type == 'MasterMob' or m.usage == 'subclip'):
                        clips.setdefault(m.name, []).append((p, m.mob_id, m.mob_type))
            except Exception as e:
                log('  (no pude leer el bin %s: %s)' % (fn, e))
    return clips

def construir(avc_path, bin_path, mob_id):
    o = leer_avc(avc_path)
    btxt = [b for c, b in o if c == b'TXTB'][0]
    src = avb.open(bin_path)
    mob = [m for m in src.content.mobs if m.mob_id == mob_id][0]
    fps, largo = fps_de(mob)
    aviso = ''
    try:
        c = list(mob.tracks)[0].component
        sc = [x for x in (c.components if hasattr(c, 'components') else [c]) if type(x).__name__ == 'SourceClip']
        if sc and sc[0].start_time:
            aviso = '  AVISO: el subclip empieza en el frame %d de su master; verificar marcas' % sc[0].start_time
    except Exception:
        pass
    lineas, marcas, modo = lineas_y_marcas(btxt, fps, inicio_tc(mob), largo)
    if largo: marcas = [(l, min(fr, largo - 1)) for l, fr in marcas]
    if not marcas: raise ValueError('no encontre timecodes en el texto ([HH:MM:SS] o HH:MM:SS:FF)')
    if modo == 'TC de origen':
        aviso = (aviso + '  ' if aviso else '  ') + '[TC de origen]'

    out = avb.file.AVBFile()
    out.creator_version = 'Media Composer 26.8'.ljust(30)
    mobs = [mob.copy(out)] + [d.copy(out) for d in mob.dependant_mobs()]
    texto = out.create.from_name('ScriptTexto'); texto.raw = btxt
    primera = max(marcas[0][0] - 1, 0)
    ultima = max(i for i, l in enumerate(lineas) if l.strip())
    take = out.create.from_name('ScriptTake'); take.raw = take_raw(primera, ultima, marcas, mob.mob_id)
    slate = out.create.from_name('ScriptSlate'); slate.take = take
    slate.primera = max(primera - 1, 0); slate.ultima = ultima + 1
    scr = out.create.from_name('Script'); scr.texto = texto; scr.slates = [slate]; scr.mobs = mobs
    out.content = scr
    tmp = avc_path + '.tmp'
    out.write(tmp)
    d = open(tmp, 'rb').read()
    k = d.index(b'boTAevTA'); d = d[:k] + b'csTA' + d[k+4:]
    open(tmp, 'wb').write(d)
    return tmp, len(marcas), fps, aviso

def ya_enlazado(avc_path):
    return any(c == b'ekTS' for c, _ in leer_avc(avc_path))

# ----------------------------------------------------------- main
class ErrorProyecto(Exception):
    pass

def procesar(proyecto, simular=False, forzar=False, log=print):
    """Enlaza todos los scripts del proyecto. Devuelve (enlazados, total)."""
    if not os.path.isdir(proyecto):
        raise ErrorProyecto('No existe la carpeta %s' % proyecto)
    if not any(f.lower().endswith('.avp') for f in os.listdir(proyecto)):
        raise ErrorProyecto('No encuentro un .avp en %s: no es la carpeta de un proyecto de Avid' % proyecto)
    scripts = []
    for raiz, dirs, files in os.walk(proyecto):
        dirs[:] = [d for d in dirs if d.lower() not in ('trash', '_backup_scriptsync')]
        scripts += [os.path.join(raiz, f) for f in files if f.lower().endswith(' script.avc') and not f.startswith('._')]
    scripts.sort(key=lambda x: os.path.basename(x).lower())
    log('Proyecto: %s\nScripts: %d\nBuscando subclips en los bins...' % (proyecto, len(scripts)))
    clips = indexar_clips(proyecto, log)
    bk = os.path.join(proyecto, '_Backup_ScriptSync', datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    ok = 0
    for path in scripts:
        fn = os.path.basename(path)
        nombre = fn[:-len(' Script.avc')]
        try:
            enlazado = ya_enlazado(path)
        except Exception as e:
            log('  !  %-40s no pude leer el script: %s' % (nombre, e)); continue
        if enlazado and not forzar:
            log('  -  %-40s ya tiene subclip enlazado (no se toca)' % nombre); continue
        cands = clips.get(nombre, [])
        subs = [c for c in cands if c[2] == 'CompositionMob'] or cands
        if not cands:
            log('  !  %-40s no hay ningun clip con ese nombre' % nombre); continue
        if len({c[1] for c in subs}) > 1:
            log('  !  %-40s hay %d clips distintos con ese nombre, no enlazo:' % (nombre, len({c[1] for c in subs})))
            for c in subs: log('        ' + os.path.relpath(c[0], proyecto))
            continue
        bin_path, mob_id, tipo = subs[0]
        tmp = None
        try:
            tmp, n, fps, aviso = construir(path, bin_path, mob_id)
            if simular:
                os.remove(tmp)
            else:
                os.makedirs(bk, exist_ok=True)
                shutil.copy2(path, os.path.join(bk, fn))
                os.replace(tmp, path)
        except Exception as e:
            if tmp and os.path.exists(tmp): os.remove(tmp)
            log('  !  %-40s ERROR: %s' % (nombre, e)); continue
        ok += 1
        log('  OK %-40s %3d marcas  (%s, %s)%s' % (nombre, n, os.path.basename(bin_path), round(fps, 3), aviso))
    if simular:
        log('\nSIMULACION: %d de %d scripts se podrian enlazar. No se modifico nada.' % (ok, len(scripts)))
    else:
        log('\n%d de %d scripts enlazados.%s' % (ok, len(scripts), (' Backups en ' + bk) if ok else ''))
    return ok, len(scripts)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    forzar = '--forzar' in sys.argv
    simular = '--simular' in sys.argv
    if not args:
        s = input('Arrastra aca la CARPETA DEL PROYECTO de Avid (la que tiene el .avp) y apreta Enter:\n').strip()
        try: partes = shlex.split(s, posix=(os.name != 'nt'))
        except ValueError: partes = [s]
        args = [partes[0] if partes else '']
        r = input('\nEnter = ENLAZAR   |   S + Enter = solo SIMULAR (no modifica nada): ').strip().lower()
        simular = simular or r.startswith('s')
    try:
        procesar(args[0].strip().strip('"').strip("'"), simular, forzar)
    except ErrorProyecto as e:
        sys.exit('ERROR: %s' % e)

if __name__ == '__main__':
    main()
