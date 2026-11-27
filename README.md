# Avid ScriptSync casero — v1.2

Desgrabaciones → Scripts de **Avid Media Composer** enlazados a los subclips. Windows y Mac.

## Qué hace

Son dos herramientas:

1. **Importar_Scripts**: convierte una carpeta entera de desgrabaciones (`.txt`) en Scripts de Avid (`<nombre> Script.avc`), de una sola vez. Es lo mismo que importar cada `.txt` a mano como script, pero por lote.
2. **ScriptSync_Avid**: por cada script del proyecto busca en **todos los bins** el subclip que se llama igual, lo enlaza al script y pone una **script mark por cada párrafo**, en el timecode que indica la desgrabación (`[HH:MM:SS]`). Después hacés clic en un párrafo del script y el subclip salta a ese momento en el monitor de origen.

Funciona con clips de cualquier frame rate (23.976, 24, 25, 29.97…), aunque estén mezclados en el mismo proyecto.

## Requisitos

- Python 3 y la librería `pyavb` (`pip install pyavb`).
- **Media Composer cerrado** mientras corre.
- Probado con Media Composer 2026.8.

## Cómo se usa

1. Con Avid cerrado, corré **Importar_Scripts** y arrastrá la carpeta del proyecto y la carpeta de los `.txt`.
2. Corré **ScriptSync_Avid** sobre la carpeta del proyecto.
   - `--simular`: muestra qué haría, sin modificar nada.
   - `--forzar`: rehace también los scripts que ya tienen un take enlazado.
3. Abrí el proyecto en Avid.

Hace backups en `CARPETA_PROYECTO/_Backup_ScriptSync/<fecha>/`.

- **Windows:** `Windows/Importar_Scripts.bat` y `Windows/ScriptSync_Avid.bat`.
- **Mac:** `Mac/Importar_Scripts.command` y `Mac/ScriptSync_Avid.command`.

El detalle completo (formato de las desgrabaciones, nombres, problemas frecuentes) está en `Mac/LEEME.txt`, que sirve para las dos plataformas.

## Contenido

| Carpeta | Para qué |
|---|---|
| `Windows/` | Scripts de Python + lanzadores `.bat` |
| `Mac/` | Los mismos scripts + lanzadores `.command` + `LEEME.txt` |

## Descargas

La app para Windows (`Avid_ScriptSync.exe`, no necesita Python) está en **Releases**.
