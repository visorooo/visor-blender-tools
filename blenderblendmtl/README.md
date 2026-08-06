# BlenderBlendMtl

A layered **Base + up to 9 Coat** shader node with per-layer blend amount masks
and Over/Additive blend modes. Works in both Cycles and EEVEE.

- **Blender:** 4.0+
- **Location:** Shader Editor → Add → BlenderBlendMtl
- **Category:** Node
- **Original author:** Victor Octavio
- **License:** GPL-3.0-or-later

## Install

This is a multi-file add-on. Zip the `blenderblendmtl` folder (the folder itself
must be the top-level entry in the zip), then *Edit → Preferences → Add-ons →
Install from Disk* and pick the zip.

## Use

1. In the Shader Editor, **Add → BlenderBlendMtl**.
2. Feed your base shader into the **Base** input.
3. Use **Add Coat Layer** (`node.blenderblendmtl_add_layer`) to stack coats — up
   to 9.
4. Each coat gets its own **Blend Amount** mask input and a blend mode of
   **Over** or **Additive**.
5. **Remove Coat Layer** (`node.blenderblendmtl_remove_layer`) pops the top layer.

The node registers as `ShaderNodeBlenderBlendMtl`.
