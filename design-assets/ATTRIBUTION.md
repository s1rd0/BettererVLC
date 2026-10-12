# Design attribution

VLC Redesign by **Juxtopposed**:
https://www.figma.com/community/file/1691465999134370980/vlc-redesign

The Figma Community page identifies the design license as **CC BY 4.0**:
https://creativecommons.org/licenses/by/4.0/

This project adapts that design to VLC's Skins2 interface. Original icon assets
were exported from the Figma design using the Figma Plugin API's PNG export. The unmodified
exports and source node identifiers are in `exported/`. Button backgrounds,
hover and pressed states, and dynamic slider sprites implement the controls in
the native bitmap format. The sample movie imagery and fictional media entries
in the prototype are replaced by actual VLC video and playlist content.

The default window is adapted from 1920x1080 to a resizable 1280x720 layout.
The sidebar uses VLC's native playlist. Concept features such as thumbnail
libraries, custom preference dialogs, and per-file watched status are not
available in a standalone Skins2 theme.

Inter font is from the official Google Fonts repository and is covered by the
SIL Open Font License included in `OFL-Inter.txt`. The license is also included
with the packaged skin.
