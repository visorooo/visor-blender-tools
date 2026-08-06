# Metal BSDF (Tailoff)

A Principled BSDF variant streamlined for metal surfaces: the inputs that never
matter for metal are stripped out, and a collapsible **Tailoff** panel lets you
blend extra roughness layers on top.

- **Blender:** 4.2+
- **Location:** Shader Editor → Add → Metal BSDF (Tailoff)
- **Category:** Node
- **Original author:** Victor Octavio
- **License:** GPL-3.0-or-later

## Install

*Edit → Preferences → Add-ons → Install from Disk*, select
`metal_bsdf_tailoff.py`, enable it.

## What's exposed

**Top level** — Base Color, Metallic, Roughness, then IOR, Alpha, Normal.

**Grouped panels** — Specular (Specular IOR Level, Specular Tint, Anisotropic,
Anisotropic Rotation, Tangent), Coat (Weight, Roughness, IOR, Tint, Normal), and
Thin Film (Thickness, IOR).

**Hidden** — Diffuse, Subsurface, Transmission, Sheen, and Emission inputs are
excluded, since they do nothing useful on a metal.

**Tailoff** — 2 extra roughness layers by default (`TAILOFF_LAYER_COUNT`).

## Note on versioning

`TAILOFF_VERSION` in the source is bumped whenever the node group's internal
structure changes. On bump, existing groups in already-open `.blend` files get
rebuilt in place rather than only affecting newly added nodes — so old files pick
up the new structure instead of silently keeping a stale one.
