#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importar_Scripts — crea scripts de Avid Media Composer (.avc) a partir de .txt,
como si se hubieran importado a mano. Uno por .txt: "<nombre> Script.avc".

Uso: python Importar_Scripts.py [--proyecto CARPETA_PROYECTO] [TXT_o_CARPETA ...]
Si falta algo, lo pregunta (se pueden arrastrar carpetas a la ventana).
Con Media Composer CERRADO. Despues abris el proyecto y aparecen los scripts.
"""
import os, sys, struct, time, random, datetime, shlex

VERSION = "Media Composer 26.8"

def u32(v): return struct.pack('<I', v)

def leer_txt(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try: s = raw.decode(enc); break
        except UnicodeDecodeError: pass
    s = s.replace('\r\n', '\r').replace('\n', '\r')
    return s.encode('utf-8')

def obj_btxt(txt):
    inicios = [0] + [i + 1 for i, b in enumerate(txt) if b == 13]
    return (b'\x02\x01' + u32(len(txt)) + txt + u32(len(inicios) - 1)
            + b''.join(u32(x) for x in inicios) + b'\x01\x01\x47\x03\x00\x00\x00\x03')

# Ventana y tipografia, copiadas de un script creado por Avid (MC 2026.8)
GEOMETRIA = bytes.fromhex('01000c00000001004500a4011a04e70500000000000000000600')
RESTO_SCPT = bytes.fromhex('0000000001000128000000010142000102420001034700020000010442010105'
                           '42014200420142010106' '4c0800') + b'Segoe UI' + b'\x03'

def obj_scpt(ref_btxt):
    return (b'\x02\x03' + u32(ref_btxt) + GEOMETRIA
            + u32(0)                                        # slates (takes): ninguno
            + u32(int(time.time())) + u32(random.getrandbits(32))
            + u32(0)                                        # mobs: ninguno
            + RESTO_SCPT)

def archivo_avc(objetos):
    fecha = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S').encode()
    n = len(objetos)
    head = (b'\x06\x00' + b'Domain' + b'DJBO' + struct.pack('<H', 7) + b'AObjDoc' + b'\x04'
            + struct.pack('<H', len(fecha)) + fecha + u32(n) + u32(n) + b'IIII'
            + u32(int(time.time())) + u32(random.getrandbits(32)) + b'csTA' + b'evTA'
            + struct.pack('<H', 30) + VERSION.encode().ljust(30, b' ') + b'\x00' * 16)
    cuerpo = b''.join(c + u32(len(d)) + d for c, d in objetos)
    return head + cuerpo

def crear(txt_path, destino):
    txt = leer_txt(txt_path)
    data = archivo_avc([(b'TXTB', obj_btxt(txt)), (b'tpcS', obj_scpt(1))])
    nombre = os.path.splitext(os.path.basename(txt_path))[0] + ' Script.avc'
    salida = os.path.join(destino, nombre)
    if os.path.exists(salida):
        return None, nombre
    open(salida, 'wb').write(data)
    return salida, nombre

def pedir_rutas(texto):
    s = input(texto).strip()
    try:
        partes = shlex.split(s, posix=(os.name != 'nt'))
    except ValueError:
        partes = [s]
    return [p.strip().strip('"').strip("'") for p in partes if p.strip()]

class ErrorProyecto(Exception):
    pass

def importar(entradas, proyecto, log=print):
    """Crea un script por cada .txt. Devuelve (creados, total)."""
    if not os.path.isdir(proyecto) or not any(f.lower().endswith('.avp') for f in os.listdir(proyecto)):
        raise ErrorProyecto('%s no parece una carpeta de proyecto de Avid (no hay .avp)' % proyecto)
    txts = []
    for p in entradas:
        if os.path.isdir(p):
            txts += [os.path.join(p, f) for f in sorted(os.listdir(p))
                     if f.lower().endswith('.txt') and not f.startswith('._')
                     and not f.lower().endswith(('_markers.txt', '_locators.txt'))]
        elif p.lower().endswith('.txt'):
            txts.append(p)
    log('Proyecto: %s\n%d desgrabaciones\n' % (proyecto, len(txts)))
    existentes = set()
    for raiz, dirs, files in os.walk(proyecto):
        existentes |= {f.lower() for f in files if f.lower().endswith('.avc')}
    creados = 0
    for t in txts:
        nombre = os.path.splitext(os.path.basename(t))[0] + ' Script.avc'
        if nombre.lower() in existentes:
            log('  -  ya existe, no lo toco: ' + nombre); continue
        try:
            salida, nombre = crear(t, proyecto)
        except Exception as e:
            log('  !  ERROR con %s: %s' % (os.path.basename(t), e)); continue
        if salida:
            creados += 1; log('  OK ' + nombre)
        else:
            log('  -  ya existe, no lo toco: ' + nombre)
    log('\n%d scripts creados de %d desgrabaciones.' % (creados, len(txts)))
    return creados, len(txts)

def main():
    args = sys.argv[1:]
    proyecto = None
    if '--proyecto' in args:
        i = args.index('--proyecto'); proyecto = args[i+1]; del args[i:i+2]
    entradas = args or pedir_rutas('Arrastra aca la CARPETA de desgrabaciones .txt (o los .txt) y apreta Enter:\n')
    if not proyecto:
        r = pedir_rutas('Arrastra aca la CARPETA DEL PROYECTO de Avid (la que tiene el .avp) y apreta Enter:\n')
        proyecto = r[0] if r else ''
    try:
        importar(entradas, proyecto)
    except ErrorProyecto as e:
        sys.exit('ERROR: ' + str(e))
    print('Listo. Abri el proyecto en Media Composer.')

if __name__ == '__main__':
    main()
