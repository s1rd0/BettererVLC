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
rem Keep the same Skins2 interface; these options affect only this VLC process.
rem DirectSound avoids the WASAPI full-buffer wait; seeking remains accurate.
start "" "%VLC_EXE%" --no-one-instance --ignore-config --config="%~dp0build\responsive-vlcrc" --no-media-library --intf=skins2 --skins2-last="%~dp0dist\VLC-Redesign.vlt" --skinned-video --skinned-playlist --file-caching=300 --aout=directsound --no-input-fast-seek %*
