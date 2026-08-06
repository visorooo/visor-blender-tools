# Pin

Constrains an object to follow a point, polygon, or surface location on another
mesh — and unlike a normal constraint, it reads the **evaluated (deformed)**
geometry. The pinned object sticks to point-level animation: shape keys,
armatures, cloth, soft body, lattice, any deformer in the stack.

A Blender port of a Cinema 4D tag plugin.

- **Blender:** 3.0+
- **Location:** Properties → Object → Pin
- **Category:** Object

## Install

*Edit → Preferences → Add-ons → Install from Disk*, select `pin.py`, enable it.

## Use

1. Select the object you want to pin.
2. Open **Properties → Object → Pin**.
3. Set the **target mesh**, pick the mode (point / polygon / surface), and set the
   index or UV coordinate.
4. Press **Pin**. The object now follows the target's deformed geometry every frame.

**Unpin** releases it and leaves the object where it is.

## How it works

| Cinema 4D | Blender equivalent used here |
|---|---|
| Tag (per object) | per-object `PropertyGroup` + Object Properties panel |
| Expression pass (each frame) | `frame_change_post` handler, plus a guarded `depsgraph_update_post` for live editing feedback |
| `GetDeformCache()` | `obj.evaluated_get(depsgraph).to_mesh()` |
| Pin / Unpin buttons | operators |
| Surface normal maps to **+Y** | mapped to the pinned object's local **+Z** (Blender is Z-up) |

## License

MIT (`SPDX-License-Identifier: MIT`, declared in `pin.py`). Distributed as part of
this GPL-3.0-or-later repository; MIT is GPL-compatible.
