# Material Manager

Browse, rename, assign, group, and clean up every material in the scene from a
single panel — instead of hunting through object slots one at a time.

- **Blender:** 4.2+
- **Location:** Properties → Material → Material Manager
- **Original author:** Victor Octavio
- **License:** GPL-3.0-or-later

## Install

This is a multi-file add-on. Zip the `material_manager` folder (the folder itself
must be the top-level entry in the zip), then *Edit → Preferences → Add-ons →
Install from Disk* and pick the zip.

It ships a `blender_manifest.toml`, so it also installs as a Blender 4.2+
extension.

## Features

**Material list** — every material in the scene in one list, with a toggle
between list view and **grid view** (preview thumbnails). Click a row to make it
the active material.

**Layers** — group materials into named layers to keep big scenes navigable:

| Action | What it does |
|---|---|
| New Layer | Create a layer, optionally moving the current selection into it |
| Rename / Remove Layer | Manage existing layers |
| Move to Layer | Send selected materials to a layer |
| No Layer | Clear the layer assignment from selected materials |
| Filter by Layer | Show only one layer's materials, or **All** |

**Selection and assignment**

- **Select objects** — select every object using the active material.
- **Assign to selected** — push the active material onto the selected objects.
- Range-select with the selection anchor, like a normal list.

**Cleanup**

- **New Material** — create one without going through an object slot.
- **Delete Material** — with a confirmation step.
- **Purge Unused Materials** — drop everything with no users.
- **Delete All Materials** — clear the scene.

The panel redraws on depsgraph updates, so the list stays current as the scene
changes.
