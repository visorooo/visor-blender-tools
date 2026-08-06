# Motion Manager

A Cinema 4D "Motion Manager" style easing tool for Blender's Graph Editor —
easing presets with real curve thumbnails, ease copy/paste between segments, and
custom bezier curves.

- **Blender:** 5.0+
- **Location:** Graph Editor → N-Panel → **Motion Mgr** tab
- **Category:** Animation
- **Version:** 1.1.0
- **Original author:** Vitor Oliani (Vipz)
- **License:** GPL-3.0-or-later

## Install

*Edit → Preferences → Add-ons → Install from Disk*, select `__init__.py`
(or zip the `motion_manager` folder first), enable it.

## Use

Open the Graph Editor, press **N**, go to the **Motion Mgr** tab.

| Operator | What it does |
|---|---|
| **Apply Ease Preset** (`mm.apply_preset`) | Apply a Penner easing preset to the selected segment |
| **Get Ease** (`mm.get_ease`) | Copy the easing off the selected segment |
| **Set Ease** (`mm.set_ease`) | Paste it onto another segment |
| **Drag Handles** (`mm.edit_curve`) | Edit the custom curve directly |
| **Save / Load / Delete Ease** | Manage your own preset library |
| **Reset** (`mm.reset_curve`) | Back to default |

## v1.1 changes

- The custom curve is now a **single bezier segment** (2 keyframes + handles)
  rather than an arbitrary compositor curve. Applying it writes the 2 handles
  onto the selected segment's endpoints — **same keyframe count, no baking**.
- Live preview is drawn to look like the real F-curve (blue curve, orange
  handles, keyframe dots) instead of the compositor widget.
- The preset library shows real curve thumbnails.
