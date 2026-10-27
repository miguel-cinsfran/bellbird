@echo off
REM ============================================================================
REM  YTChat TTS - Construye el ejecutable distribuible con PyInstaller (onedir)
REM
REM  Resultado: carpeta "YTChat TTS" en la raiz del proyecto, lista para
REM  comprimir (7-Zip / ZIP) y enviar. Quien la reciba solo descomprime y abre
REM  YTChatTTS.exe; no necesita Python ni nada instalado.
REM
REM  Modo onedir: el .exe queda junto a la carpeta _internal (dependencias) y a
REM  los archivos editables (sounds.ini, sounds/). Es mas fiable y
REM  arranca mas rapido que --onefile, y mantiene pocos elementos sueltos.
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 ( echo ERROR: uv no esta instalado. Ver README. & pause & exit /b 1 )

echo == Preparando entorno (uv) ==
REM La version de Python sale de .python-version, que uv lee solo. Reutiliza
REM el .venv si ya existe; si no, lo crea con esa version.
if not exist ".venv" (
  call uv venv
  if errorlevel 1 ( echo ERROR creando el entorno. & pause & exit /b 1 )
)
".venv\Scripts\python.exe" -c "import sys,pathlib; v=pathlib.Path('.python-version').read_text(encoding='utf-8').strip(); a=str(sys.version_info.major)+'.'+str(sys.version_info.minor); sys.exit(0 if a == v else 1)"
if errorlevel 1 ( echo ERROR: el .venv usa otra version de Python que .python-version. Ejecuta instalar.bat para rehacerlo. & pause & exit /b 1 )
call uv pip install -r requirements.txt
if errorlevel 1 ( echo ERROR instalando dependencias. & pause & exit /b 1 )
call uv pip install pyinstaller
if errorlevel 1 ( echo ERROR instalando PyInstaller. & pause & exit /b 1 )

echo == Generando los sonidos ==
call uv run python scripts\sound_gen.py >nul

echo == Localizando el discovery doc de YouTube (solo ese, no el cache entero) ==
for /f "delims=" %%i in ('uv run python -c "import googleapiclient,os;print(os.path.join(os.path.dirname(googleapiclient.__file__),'discovery_cache','documents','youtube.v3.json'))"') do set "YTDOC=%%i"
echo    %YTDOC%

echo == Localizando el modulo nativo de Prism (el .pyd que PyInstaller no ve solo) ==
for /f "delims=" %%i in ('uv run python -c "import prism,os;print(os.path.join(os.path.dirname(prism.__file__),'_native','_prism_cffi.pyd'))"') do set "PRISMCFFI=%%i"
echo    %PRISMCFFI%

echo == Localizando VLC (para empaquetar libVLC y que el amigo no instale nada) ==
set "VLCDIR="
if exist "C:\Program Files\VideoLAN\VLC\libvlc.dll" set "VLCDIR=C:\Program Files\VideoLAN\VLC"
if not defined VLCDIR if exist "C:\Program Files (x86)\VideoLAN\VLC\libvlc.dll" set "VLCDIR=C:\Program Files (x86)\VideoLAN\VLC"
if defined VLCDIR ( echo    %VLCDIR% ) else ( echo    AVISO: VLC no encontrado. El paquete saldra SIN reproductor. Instala VLC y reconstruye. )

REM Icono opcional: si dejas un app.ico en la raiz, se usa para el .exe.
REM Ruta absoluta: PyInstaller resuelve --icon relativo a --specpath (build).
set "ICONO="
if exist "app.ico" set "ICONO=--icon "%~dp0app.ico""

echo == Generando documentacion HTML (Manual) ==
REM No fatal: si pandoc no esta, se usan los HTML ya versionados en docs/.
call uv run python scripts\generar_docs.py || echo    AVISO: no se pudo regenerar; se usara la copia versionada en docs/.

echo == Empaquetando con PyInstaller ==
REM --noupx: NO comprimir con UPX. UPX dispara muchos falsos positivos de
REM antivirus; sin el, el .exe levanta menos sospechas en el PC del amigo.
REM El modulo da metadatos rapidos y el ejecutable mantiene flujos y descargas.
REM yt-dlp carga extractores al vuelo, por eso se recopila completo.
REM --exclude-module imageio_ffmpeg: su hook metia un segundo ffmpeg.exe en
REM _internal; la app empaquetada usa el que se copia a la raiz mas abajo
REM (ffmpeg_bin.ruta_ffmpeg lo busca primero), asi que el otro sobraba.
call uv run pyinstaller main.py ^
  --name YTChatTTS ^
  --onedir --windowed --noconfirm --clean --noupx ^
  --distpath dist --workpath build --specpath build ^
  %ICONO% ^
  --collect-all prism ^
  --add-binary "%PRISMCFFI%;prism\_native" ^
  --hidden-import _cffi_backend ^
  --collect-submodules googleapiclient ^
  --collect-submodules google_auth_oauthlib ^
  --collect-submodules pytchat ^
  --collect-all TikTokLive ^
  --collect-all yt_dlp ^
  --exclude-module imageio_ffmpeg ^
  --exclude-module numpy ^
  --hidden-import vlc ^
  --add-data "!YTDOC!;googleapiclient/discovery_cache/documents"
if errorlevel 1 ( echo ERROR en PyInstaller. & pause & exit /b 1 )

echo == Ensamblando la carpeta distribuible ==
REM Version desde config.py (fuente unica): nombra la carpeta y el zip como
REM "YTChat TTS vX.Y.Z", asi el archivo que se manda y la carpeta al descomprimir
REM dejan clara la version.
for /f "delims=" %%v in ('uv run python -c "from ytchat.core import config;print(config.APP_VERSION)"') do set "VER=%%v"
if not defined VER ( echo ERROR: no se pudo leer la version de config.py. & pause & exit /b 1 )
set "OUT=YTChat TTS v%VER%"
REM Ojo: "^>" escapado; un ">" literal en echo redirige y crea un archivo basura.
echo    Version %VER%  -^>  "%OUT%"
REM Limpia builds previos de CUALQUIER version para no acumular carpetas/zips.
for /d %%d in ("YTChat TTS v*") do rmdir /s /q "%%d"
if exist "YTChat TTS" rmdir /s /q "YTChat TTS"
if exist "%OUT%" rmdir /s /q "%OUT%"

REM robocopy devuelve codigos ^>=1 incluso en exito; no encadenamos errorlevel.
robocopy "dist\YTChatTTS" "%OUT%" /E /NFL /NDL /NJH /NJS /NP >nul
robocopy "sounds" "%OUT%\sounds" /E /NFL /NDL /NJH /NJS /NP >nul
robocopy "docs"   "%OUT%\docs"   /E /NFL /NDL /NJH /NJS /NP >nul
robocopy "web"    "%OUT%\web"    /E /NFL /NDL /NJH /NJS /NP >nul
if not exist "catalogo_ia.json" ( echo ERROR: falta catalogo_ia.json en la raiz; hay que correr uv run python scripts/actualizar_catalogo_ia.py para generarlo. & pause & exit /b 1 )
copy /y "catalogo_ia.json" "%OUT%\" >nul

echo == Recortando el discovery cache de Google ==
REM El hook de PyInstaller trae los 604 documentos de discovery_cache, unos
REM 109 MB, y la app solo usa youtube.v3.json. Se borra todo lo demas.
set "GDOCS=%OUT%\_internal\googleapiclient\discovery_cache\documents"
if exist "%GDOCS%" (
  for %%f in ("%GDOCS%\*") do if /i not "%%~nxf"=="youtube.v3.json" del /q "%%f"
)
if defined VLCDIR (
  echo == Empaquetando libVLC junto al exe: plugins de audio y video ==
  robocopy "%VLCDIR%" "%OUT%\vlc" libvlc.dll libvlccore.dll /NFL /NDL /NJH /NJS /NP >nul
  REM Plugins necesarios para el reproductor embebido: red HTTP/TLS y demux.
  REM DASH/HLS, codecs y salida de audio y video. La imagen va con set_hwnd.
  REM Se deja fuera lo que no usamos -GUI/skins, visualizaciones- para reducir
  REM tamano y acelerar el arranque. OJO: sin parentesis en estos REM, romperian
  REM el bloque IF.
  for %%d in (access codec demux audio_output audio_filter audio_mixer packetizer stream_filter stream_extractor misc keystore logger video_output video_chroma video_filter d3d9 d3d11) do (
    robocopy "%VLCDIR%\plugins\%%d" "%OUT%\vlc\plugins\%%d" /E /NFL /NDL /NJH /NJS /NP >nul
  )
  REM Generar la cache de plugins del set recortado evita el escaneo en el
  REM primer arranque, que hacia que la app tardara en abrir.
  REM Ruta absoluta: con ruta relativa la cache salia vacia.
  if exist "%VLCDIR%\vlc-cache-gen.exe" "%VLCDIR%\vlc-cache-gen.exe" "%CD%\%OUT%\vlc\plugins" >nul 2>nul
  REM Solo aviso, no corta la construccion: si la cache sale vacia el
  REM reproductor tarda en arrancar pero la app igual funciona.
  if not exist "%OUT%\vlc\plugins\plugins.dat" echo    AVISO: la cache de plugins de VLC salio vacia y el reproductor tardara en arrancar.
  if exist "%OUT%\vlc\plugins\plugins.dat" for %%f in ("%OUT%\vlc\plugins\plugins.dat") do if %%~zf LSS 10000 echo    AVISO: la cache de plugins de VLC salio vacia y el reproductor tardara en arrancar.
)

echo == Empaquetando ffmpeg (mux audio+video de yt-dlp en el gestor de descargas) ==
REM imageio-ffmpeg trae un ffmpeg.exe portable en site-packages. Lo copiamos
REM junto al .exe para que el gestor de descargas (yt-dlp + FFmpegExtractAudio)
REM pueda muxear sin que el usuario instale nada. Sin parentesis en estos REM,
REM romperian el bloque IF.
set "FFEXE="
for /f "delims=" %%f in ('uv run python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"') do set "FFEXE=%%f"
if defined FFEXE (
  echo    %FFEXE%
  copy /y "%FFEXE%" "%OUT%\ffmpeg.exe" >nul
  if not exist "%OUT%\ffmpeg.exe" echo    AVISO: no se pudo copiar ffmpeg; el paquete saldra SIN ffmpeg.
) else (
  echo    AVISO: imageio-ffmpeg no encontrado. El paquete saldra SIN ffmpeg; las descargas de audio fallaran.
)
echo == Empaquetando yt-dlp independiente ==
echo    La primera vez descarga yt-dlp desde GitHub y puede tardar.
call uv run python -c "import shutil; from ytchat.downloads import ytdlp_bin; from pathlib import Path; r=ytdlp_bin.asegurar_ytdlp(); p=ytdlp_bin.ruta_ytdlp(); d=Path(r'%OUT%') / 'yt-dlp.exe'; shutil.copy2(p,d) if r.correcta and p else None; print('   ' + ('resultado: ' if r.correcta else 'AVISO: ') + r.motivo)"
REM El lanzador del entorno pesa unos 45 KB; el ejecutable oficial observado
REM el 21/08/2026 pesa unos 17 MB. Un MiB deja margen y descarta el lanzador.
set "YTDLP_MIN_BYTES=1048576"
if not exist "%OUT%\yt-dlp.exe" (
  echo    AVISO: no se obtuvo yt-dlp.exe de verdad; el paquete saldra sin el programa independiente.
) else (
  for %%f in ("%OUT%\yt-dlp.exe") do if %%~zf LSS %YTDLP_MIN_BYTES% (
    echo    AVISO: yt-dlp.exe pesa %%~zf bytes y no es el programa independiente; se elimina.
    del /q "%OUT%\yt-dlp.exe"
  ) else (
    echo    OK: yt-dlp.exe independiente copiado, %%~zf bytes.
  )
)
REM El paquete no trae config.ini: pisaria el del usuario al descomprimir
REM encima, y la aplicacion lo crea sola en data al arrancar.
REM sounds.ini sigue con el tratamiento previo: intentar git, si no local.
git show HEAD:sounds.ini > "%OUT%\sounds.ini" 2>nul
if errorlevel 1 ( echo    AVISO: sin git; sounds.ini local ^(puede llevar ajustes personales^). & copy /y "sounds.ini" "%OUT%\" >nul )
copy /y "LICENSE"    "%OUT%\" >nul
REM Documentacion de cara al usuario en HTML (se abre con doble clic; el amigo
REM no tiene por que saber abrir un Markdown). Se genera con scripts\generar_docs.py y
REM viaja tambien dentro de docs/. La dejamos ademas en la raiz, a la vista. El
REM historial de versiones (CHANGELOG) va como docs/CHANGELOG.html, enlazado
REM desde el propio Manual ("que hay de nuevo").
copy /y "docs\MANUAL.html" "%OUT%\Manual.html" >nul
REM Solo en la raiz: sus enlaces (docs/...) se calculan desde ahi y dentro de docs/ quedaban rotos.
del /q "%OUT%\docs\MANUAL.html" >nul 2>&1

REM Cliente de Google de la app: si esta en la raiz, viaja junto al exe
REM para que quien no tenga credenciales propias igual pueda iniciar sesion.
REM Si no esta, el paquete sale sin cliente y cada persona necesitara el suyo.
if exist "cliente_app.json" (
  copy /y "cliente_app.json" "%OUT%\" >nul
) else (
  echo    AVISO: sin cliente_app.json; el paquete saldra sin cliente de Google y cada persona necesitara credenciales propias.
)

REM Por higiene: nada de log ni credenciales en el paquete que se envia.
del /q "%OUT%\ytchat.log" 2>nul
del /q "%OUT%\credenciales.json" 2>nul
REM La carpeta de datos no viaja: se crea sola al primer arranque.
rmdir /s /q "%OUT%\data" 2>nul

echo == Comprobando el modulo yt-dlp ==
dir /b /s "%OUT%\_internal\yt_dlp\*" >nul 2>nul
if errorlevel 1 (
  echo    AVISO: yt_dlp no viaja en el paquete; al conectar saldra lento porque falta el modulo.
)
if exist "%OUT%\config.ini" ( echo ERROR: config.ini quedo en el paquete y pisaria el del usuario. & pause & exit /b 1 )
if not exist "%OUT%\_internal\googleapiclient\discovery_cache\documents\youtube.v3.json" ( echo ERROR: falta youtube.v3.json en el discovery cache; la app no podria hablar con la API. & pause & exit /b 1 )
if not exist "%OUT%\_internal\prism\_native\_prism_cffi.pyd" ( echo ERROR: falta _prism_cffi.pyd en prism\_native; sin Prism la app arrancaria sin voz ni lector de pantalla. & pause & exit /b 1 )
echo == Comprobando que el paquete carga lo critico ==
del /q "%TEMP%\ytchat-autocomprobacion.txt" 2>nul
start "" /wait "%OUT%\YTChatTTS.exe" --autocomprobar "%TEMP%\ytchat-autocomprobacion.txt"
set "AUTOCOMP=%errorlevel%"
type "%TEMP%\ytchat-autocomprobacion.txt" 2>nul
if not "%AUTOCOMP%"=="0" ( echo ERROR: el paquete no carga todo lo critico, ver las lineas FALLA de arriba. & pause & exit /b 1 )
rmdir /s /q "%OUT%\data" 2>nul
set "OTROS_DOCS="
for %%f in ("%OUT%\_internal\googleapiclient\discovery_cache\documents\*") do if /i not "%%~nxf"=="youtube.v3.json" set "OTROS_DOCS=1"
if defined OTROS_DOCS echo    AVISO: quedaron documentos de API de Google ademas de youtube.v3.json en el paquete.
if exist "%OUT%\_internal\numpy" echo    AVISO: numpy sigue en el paquete y deberia estar excluido.

echo == Escribiendo el manifiesto del paquete ==
REM Lo lee el instalador para saber que version trae el zip y cual es su exe.
call uv run python -c "import json;json.dump({'version':'%VER%','ejecutable':'YTChatTTS.exe'},open(r'%OUT%\paquete.json','w'))"
if not exist "%OUT%\paquete.json" ( echo ERROR: no se pudo escribir paquete.json. & pause & exit /b 1 )

echo == Escribiendo el manifiesto de sonidos ==
REM Huellas SHA-256 de cada archivo de sounds/themes, con ruta relativa a
REM sounds/ y / como separador. Lo lee el instalador para conservar los
REM sonidos que el usuario cambio o agrego al actualizar.
call uv run python -c "import hashlib,json,pathlib;base=pathlib.Path('sounds');tema=base/'themes';archivos=sorted(tema.rglob('*')) if tema.is_dir() else [];datos={a.relative_to(base).as_posix():hashlib.sha256(a.read_bytes()).hexdigest().lower() for a in archivos if a.is_file()};open(r'%OUT%\sonidos.json','w').write(json.dumps(datos,sort_keys=True))"
if not exist "%OUT%\sonidos.json" ( echo ERROR: no se pudo escribir sonidos.json. & pause & exit /b 1 )

echo == Comprimiendo a "%OUT%.zip" ==
REM Borra zips de cualquier version anterior (incluido el viejo sin version).
del /q "YTChat TTS.zip" 2>nul
del /q "YTChat TTS v*.zip" 2>nul
del /q "YTChat TTS.zip.sha256" 2>nul
del /q "YTChat TTS v*.zip.sha256" 2>nul
powershell -NoProfile -Command "Compress-Archive -Path '%OUT%' -DestinationPath '%OUT%.zip' -Force"

echo == Firmando el zip ==
REM SHA-256 en minusculas, dos espacios y el nombre del zip. El actualizador
REM lo usa para verificar la descarga antes de instalar. Se calcula con
REM Python y hashlib, igual que paquete.json: el powershell viejo heredaba
REM PSModulePath de PowerShell 7 y no encontraba su modulo de huella.
call uv run python -c "import hashlib;h=hashlib.sha256(open(r'%OUT%.zip','rb').read()).hexdigest().lower();open(r'%OUT%.zip.sha256','w').write(h+'  %OUT%.zip')"
if not exist "%OUT%.zip.sha256" ( echo ERROR: no se pudo firmar el zip. & pause & exit /b 1 )

echo.
echo ============================================================================
echo  Listo.
echo    Carpeta: "%OUT%"        (para probar: "%OUT%\YTChatTTS.exe")
echo    ZIP    : "%OUT%.zip"    (esto es lo que mandas al amigo)
echo    FIRMA  : "%OUT%.zip.sha256"    (subelo junto al zip a la release)
echo  El amigo solo descomprime y abre YTChatTTS.exe; no necesita nada mas.
echo ============================================================================
pause
