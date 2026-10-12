# Skins2 format and validation references

The bundled `skin.dtd` is Skins2 DTD 2.0 from VLC 3.0.24, copied without changes.
The validator prefers the installed Windows VLC DTD when available, otherwise
uses this bundled copy. `--dtd` overrides that choice; `--strict` rejects warnings.

- [Upstream DTD](https://github.com/videolan/vlc/blob/3.0.24/share/skins2/skin.dtd)
- [VLC license](https://github.com/videolan/vlc/blob/3.0.24/COPYING)
- [Action interpreter](https://github.com/videolan/vlc/blob/3.0.24/modules/gui/skins2/parser/interpreter.cpp)
- [Skin parser](https://github.com/videolan/vlc/blob/3.0.24/modules/gui/skins2/parser/skin_parser.cpp)
- [XML wrapper](https://github.com/videolan/vlc/blob/3.0.24/modules/gui/skins2/parser/xmlparser.cpp)
- [Slider control](https://github.com/videolan/vlc/blob/3.0.24/modules/gui/skins2/controls/ctrl_slider.cpp)
- [VLC/skin variables](https://github.com/videolan/vlc/blob/3.0.24/modules/gui/skins2/src/vlcproc.cpp)

## Independent sliders

VLC 3.0's XML wrapper does not synthesize end callbacks for self-closing nodes.
A self-closing `Playtree` leaves the parser in its tree context and overrides
later sliders to `playtree.slider`. The generator therefore writes explicit
closing tags, and the validator rejects this unsafe `Playtree`/`Playlist` form.

`tools/check_native_slider_bindings.py` uses the installed Windows VLC XML reader
and replays the relevant skin-parser state transitions. It checks both source and
archive, plus a negative example restoring the old self-closing form. This is a
binding regression check, not a desktop mouse-interaction test.

## Playback tests and their limits

Use a separate VLC configuration and `--no-media-library` for diagnostics.
Skins2 saves skin/window state when it exits; isolated launchers keep this under
`build/` rather than updating the main VLC configuration.

Position/volume readback only confirms control state. LibVLC's memory-video display
callback measures clock-driven output in memory and disables native hardware
output. It cannot establish physical display or audible volume latency.

- [Public LibVLC player APIs](https://github.com/videolan/vlc/blob/3.0.24/include/vlc/libvlc_media_player.h)
- [Memory callback implementation](https://github.com/videolan/vlc/blob/3.0.24/lib/media_player.c)
- [Memory video output](https://github.com/videolan/vlc/blob/3.0.24/modules/video_output/vmem.c)
- [Native D3D11 output](https://github.com/videolan/vlc/blob/3.0.24/modules/video_output/win32/direct3d11.c)
- [Logging APIs](https://github.com/videolan/vlc/blob/3.0.24/include/vlc/libvlc.h)

Native D3D11VA seek diagnostics used synchronous LibVLC logging to compare the
same `Decoder wait done` checkpoint. Accurate seeks in three positions of a local
4K/60 VP9 sample took approximately 840–1223 ms; fast seeks took 14–28 ms but moved
the effective Matroska destination 3.483–5.444 seconds earlier. The input clock
can initially report the requested time despite that earlier demux destination.
These single trials are pipeline observations, not latency percentiles or guarantees.

File-logger tail timing was discarded because Windows buffering withheld lines
until shutdown. `Received first picture` was also insufficient: it can appear
before target preroll finishes and identify a stale pending picture.

- [Seek control](https://github.com/videolan/vlc/blob/3.0.24/src/input/input.c)
- [Matroska seek handling](https://github.com/videolan/vlc/blob/3.0.24/modules/demux/mkv/demux.cpp)

## Audio alternatives

WASAPI buffer capacity is not a measurement of audible delay. Volume requests
can wait for the output lock; amplification above 100% applies to new samples,
while queued samples retain their existing software gain. DirectSound is a
reversible alternative, not a guaranteed fix. Skins2 exposes a 0–200% volume
slider without an XML setting to cap it at 100%.

- [MMDevice output](https://github.com/videolan/vlc/blob/3.0.24/modules/audio_output/mmdevice.c)
- [WASAPI output](https://github.com/videolan/vlc/blob/3.0.24/modules/audio_output/wasapi.c)
- [DirectSound output](https://github.com/videolan/vlc/blob/3.0.24/modules/audio_output/directsound.c)
- [Audio-output core](https://github.com/videolan/vlc/blob/3.0.24/src/audio_output/output.c)

Private media and local runtime logs are not included in this repository.
