# Paso a paso para subir SH Masivo a GitHub

## 1. Crear repositorio

1. Ingresa a GitHub.
2. Haz clic en **New repository**.
3. Asigna un nombre, por ejemplo `sh-masivo`.
4. Déjalo como público o privado según prefieras.
5. Crea el repositorio sin agregar README, `.gitignore` ni licencia, porque ya van incluidos en este paquete.

## 2. Descargar y descomprimir este paquete

1. Descarga el ZIP entregado por ChatGPT/Perplexity.
2. Descomprímelo en una carpeta local, por ejemplo `C:\Proyectos\sh-masivo`.

## 3. Subir archivos a GitHub desde la web

### Opción simple

1. Entra al repositorio recién creado.
2. Haz clic en **uploading an existing file**.
3. Arrastra todos los archivos y carpetas del paquete descomprimido.
4. Presiona **Commit changes**.

## 4. Subir archivos usando Git en Windows

Abre PowerShell dentro de la carpeta del proyecto y ejecuta:

```powershell
git init
git add .
git commit -m "Primer commit SH Masivo"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/sh-masivo.git
git push -u origin main
```

Reemplaza `TU-USUARIO` por tu usuario real de GitHub.

## 5. Generar el EXE con GitHub Actions

1. En GitHub, ve a la pestaña **Actions** y verifica que el workflow esté visible.
2. Para disparar compilación automática por versión, crea un tag desde tu PC:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

3. GitHub Actions compilará el ejecutable en Windows.
4. Cuando termine, entra al workflow ejecutado.
5. Descarga el artefacto `sh-masivo-windows`.

## 6. Generar el EXE en tu PC si prefieres

En Windows, haz doble clic en `build_exe.bat`.

Esto hará lo siguiente:
- Creará un entorno virtual.
- Instalará dependencias.
- Generará `dist\sh-masivo.exe`.

## 7. Crear una release manual en GitHub

1. Ve a **Releases** en tu repositorio.
2. Haz clic en **Draft a new release**.
3. Usa el tag `v1.0.0` o crea uno nuevo.
4. Sube el archivo `sh-masivo.exe` o un ZIP con el EXE.
5. Publica la release.

## 8. Recomendación de orden

1. Subir repositorio.
2. Confirmar que el código aparece en GitHub.
3. Ejecutar workflow o compilar localmente.
4. Descargar/probar el EXE.
5. Crear release.
