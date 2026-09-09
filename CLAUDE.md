# visor-blender-tools

Blender add-ons, public on `visorooo/visor-blender-tools`, GPL-3.0-or-later.
Each add-on folder has its own README as user documentation; this file is the
working context for editing them.

## Layout and target versions

| Add-on | Shape | Blender | Registers into |
|---|---|---|---|
| `pin/pin.py` | single file | 3.0+ | Properties > Object |
| `material_manager/` | package (5 modules) | 4.2+ | Properties > Material |
| `blenderblendmtl/` | package (4 modules) | 4.0+ | Shader Editor > Add |
| `metal_bsdf_tailoff/metal_bsdf_tailoff.py` | single file | 4.2+ | Shader Editor > Add |
| `motion_manager/__init__.py` | single file (~45 KB) | 5.0+ | Graph Editor > N-panel |

The `blender` key in each `bl_info` is the minimum version and is load-bearing —
Blender refuses the add-on below it. `material_manager` additionally carries a
`blender_manifest.toml`, so it is installable as a 4.2+ *extension*; the others are
legacy add-ons.

Package add-ons follow a consistent pattern: each module exposes a `classes` tuple,
and `__init__.py` concatenates them and registers in order. Add a class → add it to
that module's `classes`, nothing else.

## Testing

No automated tests — `bpy` only exists inside Blender. Install from disk (single
`.py` files directly, packages zipped with the folder as the top-level entry) and
exercise the panel. Errors surface in Blender's system console, which on Windows
must be opened via *Window > Toggle System Console* before it shows anything.

Reloading an already-installed add-on rarely picks up structural changes cleanly.
Disable, restart Blender, re-enable.

## Gotchas worth knowing before editing

**`metal_bsdf_tailoff` versions its node group.** `TAILOFF_VERSION` (currently 7)
must be bumped whenever `_build_node_group()`'s structure changes, or groups already
present in a user's open file keep the old wiring instead of being rebuilt in place.
This is the single easiest thing to forget in that file.

**Socket lookup there is deliberately linear.** `_socket()` scans `.name` instead of
using `collection["Name"]` because Principled BSDF and Mix expose hidden duplicate-named
sockets that make key lookup unreliable. Don't "simplify" it back to a dict lookup.

**`pin` reads evaluated geometry** — `obj.evaluated_get(depsgraph).to_mesh()` — which
is the entire point of the add-on: it sticks through shape keys, armatures, cloth and
lattices. It runs from a `frame_change_post` handler plus a guarded
`depsgraph_update_post`; that guard is what stops the update from recursing.
Coordinate mapping is C4D's +Y surface normal onto Blender's local +Z (Z-up).

**`motion_manager` writes bezier handles onto existing keyframes**, not new ones —
applying a curve keeps the keyframe count identical, no baking. Preserve that.

## Licensing

GPL-3.0-or-later, and not by preference: add-ons link `bpy` and are derivative works
of Blender. Anything added here is GPL too.

Current state of the SPDX headers, which is not uniform:

- `motion_manager/__init__.py` — `GPL-3.0-or-later` in source ✓
- `pin/pin.py` — `MIT` in source, from its author; GPL-compatible, leave it
- `material_manager` — declares GPL only in `blender_manifest.toml`, **no source header**
- `blenderblendmtl`, `metal_bsdf_tailoff` — no SPDX header, covered by repo LICENSE

Adding the missing headers is safe and would make the tree match what the README
claims. Do not weaken any of them.

**Credits to preserve on refactor:** Victor Octavio (`material_manager`,
`blenderblendmtl`, `metal_bsdf_tailoff`), Vitor Oliani / Vipz (`motion_manager`).
`pin` is a port of a C4D tag plugin.
