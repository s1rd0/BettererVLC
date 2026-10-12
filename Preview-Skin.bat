@echo off
setlocal
set "VLC_EXE=%ProgramFiles%\VideoLAN\VLC\vlc.exe"
if not exist "%VLC_EXE%" set "VLC_EXE=%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe"
if not exist "%VLC_EXE%" (
  echo VLC was not found. Install VLC or open dist\VLC-Redesign.vlt in VLC.
  pause
  exit /b 1
)
if not exist "%~dp0build" mkdir "%~dp0build"
start "" "%VLC_EXE%" --no-one-instance --ignore-config --config="%~dp0build\preview-vlcrc" --no-media-library --intf=skins2 --skins2-last="%~dp0dist\VLC-Redesign.vlt" --skinned-video --skinned-playlist %*
