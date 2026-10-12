## VLC Redesign v1.0.0

Initial release of the VLC Skins2 adaptation of Juxtopposed's VLC Redesign.

- Original exported icons, Inter typography and a resizable 1280×720 player.
- Native video playback, playlist controls and a fullscreen control bar.
- Independent seek and volume sliders in player, playlist and fullscreen layouts.
- A 257-state progress fill for smaller display steps.
- Windows launchers for accurate seeking, optional approximate fast seeking, and standard playback settings.
- Complete theme sources, original exports, build/validation scripts and component license notices.

Download **VLC-Redesign.vlt**, select it under **Tools → Preferences → Interface → Use custom skin**, then restart VLC. Python is not required for installation.

Tested with VLC 3.0.24 on Windows. Skins2 is also available on Linux, but this release has not been runtime-tested there. VLC for macOS does not support Skins2.

Fast seeking can land several seconds before the selected position. Live seek thumbnails, sliding functional sidebars, continuous progress interpolation and redesigned native VLC dialogs are outside this `.vlt` adaptation's capabilities. Audible volume-response improvements are not guaranteed.

The attached binary and the repository's `dist/VLC-Redesign.vlt` are the same build; its checksum is in `dist/SHA256SUMS`.
