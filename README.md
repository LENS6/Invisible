This script is a Blender add-on named Invisible, designed to provide batch object renaming and automatic material assignment. It is compatible with Blender 4.2.6 and above. The add‑on’s interface appears in the 3D View sidebar (press N), under the “Invisible” tab. Key features include:

1. Object Renamer
Flexible naming rules: Users can define multiple name parts (e.g., prefixes, keywords), with an option to insert a delimiter (default underscore _) after each part.

Numbering control: Supports auto‑detection of the highest existing number in the scene and increments it, or manual setting of start number and digit count (e.g., 01, 02).

Quick suffix buttons: “High” and “Low” buttons instantly add suffixes, with an option to include or omit the delimiter before the suffix.

Filtering & synchronization:

Option to rename only objects containing Chinese characters or special symbols.

Sync the corresponding data names (mesh, curve, camera, armature, etc.) with the new object name.

Sync material names of selected objects (rename materials to match the object name).

History: Automatically saves the settings of the last 20 rename operations, which can be reloaded at any time.

Templates: Save current naming rules as a template; supports loading, deleting, clearing all templates, and exporting/importing templates as JSON files for sharing across projects.

2. Material Assigner
Assigns materials to selected mesh objects, each using the object’s own name as the material name.

Random color generation: Three color modes:

Golden Ratio: Uses the golden ratio to generate a sequence of perceptually distinct hues.

HSV Distinct: Evenly distributes hues based on the number of objects.

RGB Random: Traditional random RGB with enhanced contrast.

Adjustable saturation and value (range 0.5–1.5).

Option to force new materials, even if a material with the same name already exists.

3. Multilingual Support
Built‑in bilingual dictionary (Chinese/English); the UI text automatically switches according to Blender’s interface language.

4. Additional Utilities
“Reset Defaults” button.

Automatically cleans .001 suffixes from bone names in armature objects (when data name synchronization is enabled).

The add‑on stores its configuration in custom property groups, supports Undo for all operations, and provides a user‑friendly workflow for 3D artists who need to quickly standardize object names and manage materials in a scene.