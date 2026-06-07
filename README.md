# SH Masivo

Aplicación de escritorio en Python/Tkinter para ejecutar comandos `show` sobre múltiples equipos por SSH/Telnet, guardar resultados por hostname y comparar archivos TXT línea por línea.

## Contenido del repositorio

- `app/show_runner_gui.py`: aplicación principal.
- `requirements.txt`: dependencias necesarias.
- `build_exe.bat`: compilación rápida en Windows con PyInstaller.
- `version.json`: versión actual de la aplicación.
- `.github/workflows/release.yml`: flujo para generar artefacto en GitHub Actions.

## Requisitos locales

- Windows con Python 3.11 o superior.
- Acceso a red hacia los equipos a consultar.

## Ejecución local

```bash
pip install -r requirements.txt
python app/show_runner_gui.py
```

## Compilación local a EXE

En Windows, ejecutar `build_exe.bat`.

## Release automática

El workflow `release.yml` compila la aplicación en Windows y publica un artefacto descargable cuando creas un tag tipo `v1.0.0`.
