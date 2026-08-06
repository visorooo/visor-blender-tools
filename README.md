# VISOR Blender Tools

Blender add-ons built at [VISOR](https://github.com/visorooo) for 3D/CGI/VFX
production work — shading, material management, and animation.

| Add-on | What it does | Blender |
|---|---|---|
| [pin](pin/) | Constrains an object to a point, polygon, or surface of a **deforming** mesh. Reads evaluated geometry, so it sticks through shape keys, armatures, cloth, lattices, any deformer | 3.0+ |
| [material_manager](material_manager/) | Browse, rename, assign, group, and clean up every material in the scene from one panel | 4.2+ |
| [blenderblendmtl](blenderblendmtl/) | Layered Base + up to 9 Coat shader node with per-layer blend masks and Over/Additive modes | 4.0+ |
| [metal_bsdf_tailoff](metal_bsdf_tailoff/) | Principled BSDF variant streamlined for metals, with a collapsible Tailoff panel for blending extra roughness layers | 4.2+ |
| [motion_manager](motion_manager/) | C4D-style Motion Manager for the Graph Editor: easing presets, ease copy/paste, and custom bezier curves | 5.0+ |

Each folder has its own README.

## Install

**Single-file add-ons** (`metal_bsdf_tailoff`, `motion_manager`, `pin`) — in Blender,
*Edit → Preferences → Add-ons → Install from Disk*, pick the `.py` file, enable it.

**Multi-file add-ons** (`material_manager`, `blenderblendmtl`) — zip the add-on's
folder first, then install the zip the same way. The folder must be the top-level
entry inside the zip.

## Credits

- **material_manager**, **blenderblendmtl**, and **metal_bsdf_tailoff** were
  originally built by **Victor Octavio**.
- **motion_manager** was originally built by **Vitor Oliani** (Vipz).
- **pin** is a port of a Cinema 4D tag plugin to Blender.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).

Blender add-ons link against `bpy` and are derivative works of Blender, which is
GPL-licensed, so GPL is the required license for distribution.
`material_manager` and `motion_manager` already declare
`SPDX-License-Identifier: GPL-3.0-or-later` in their own source.

`pin/pin.py` carries an `SPDX-License-Identifier: MIT` header from its author.
MIT is GPL-compatible, so that header stands and the combined distribution is
GPL-3.0-or-later.
