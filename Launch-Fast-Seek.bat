@echo off
setlocal
set "VLC_EXE=%ProgramFiles%\VideoLAN\VLC\vlc.exe"
if not exist "%VLC_EXE%" set "VLC_EXE=%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe"
if not exist "%VLC_EXE%" (
  echo VLC was not found. Install VLC to launch this skin.
  pause
  exit /b 1
)
if not exist "%~dp0dist\VLC-Redesign.vlt" (
  echo Missing dist\VLC-Redesign.vlt.
  pause
  exit /b 1
)
if not exist "%~dp0build" mkdir "%~dp0build"
rem Fast seeking is approximate: this can jump several seconds before the target.
rem Launch-Skin.bat keeps accurate seeking with the same skin and audio output.
echo Fast seeking may land several seconds before the selected position.
echo Accurate seeking: Launch-Skin.bat
start "" "%VLC_EXE%" --no-one-instance --ignore-config --config="%~dp0build\fast-seek-vlcrc" --no-media-library --intf=skins2 --skins2-last="%~dp0dist\VLC-Redesign.vlt" --skinned-video --skinned-playlist --file-caching=300 --aout=directsound --input-fast-seek %*
