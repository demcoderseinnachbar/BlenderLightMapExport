# Installation

## Voraussetzungen

- Blender **5.2.3 LTS** (getestet mit Build vom 22.10.2026, Windows 11). Ältere Versionen werden nicht unterstützt (Manifest `blender_version_min = "5.2.0"`).
- Windows 10/11 für die Batch-Datei. Das Python-Skript `scripts/batch_export.py` ist plattformunabhängig.
- Optional: NVIDIA-GPU (OptiX/CUDA), AMD (HIP) oder Intel (oneAPI) für GPU-Baking. Ohne GPU wird automatisch die CPU verwendet.
- Keine zusätzlichen Python-Pakete. Verwendet wird ausschließlich Blenders eingebautes Python (inklusive `numpy`).

## Extension installieren (Blender-Oberfläche)

1. ZIP erzeugen oder aus `build/` nehmen:
   ```bat
   "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python scripts\build_extension.py -- --verify
   ```
   Ergebnis: `build\blender_lightmap_export-0.1.0.zip`. Mit `--verify` wird die ZIP zusätzlich in Blender installiert, aktiviert, geprüft und wieder entfernt.
2. Blender öffnen: *Edit > Preferences > Get Extensions*, oben rechts das Dropdown-Menü, *Install from Disk…*, die ZIP auswählen.
3. Die Extension erscheint unter *Add-ons* als **Lightmap Exporter** und ist aktiviert.
4. Im 3D-Viewport die Sidebar mit `N` öffnen, Reiter **Lightmap Exporter**.

Einstellungen der Extension (*Preferences > Add-ons > Lightmap Exporter*):

| Einstellung | Bedeutung |
|---|---|
| Lightmaps beim glTF-Import automatisch zuweisen | Hook im Blender-glTF-Importer; Standard an |
| Bake im Hintergrund | Nutzt Blenders eigenen Bake-Job mit Fortschritt in der Statusleiste und Esc-Abbruch; bei Problemen abschalten, dann blockierender Bake mit Fortschrittsbalken |
| Standard-Ausgabeverzeichnis | Vorbelegung für neue Szenen |

## Entwicklungsinstallation ohne ZIP

Alternativ den Ordner `blender_lightmap_export` als Extension-Quelle nutzen: In den Preferences unter *Get Extensions > Repositories* ein lokales Repository anlegen, das auf den Repository-Ordner `C:\DEV\Blender\BlenderLightMapExport` zeigt (Option „Custom Directory“). Nach Änderungen am Code *Refresh Local* ausführen.

## Batch-Einrichtung

`start_export.bat` sucht Blender unter `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`. Bei abweichendem Pfad die Umgebungsvariable setzen:

```bat
set BLENDER_EXE=D:\Tools\Blender\blender.exe
start_export.bat C:\Models C:\Export
```

Für den Batch-Betrieb muss die Extension **nicht** in Blender installiert sein; das Skript lädt das Paket direkt aus dem Repository.

## Deinstallation

*Preferences > Get Extensions*, Lightmap Exporter aufklappen, *Uninstall*. Lightmap-Vorschau-Nodes in bereits gespeicherten Szenen bleiben erhalten; mit dem Operator *Originalmaterialien wiederherstellen* (vor der Deinstallation) oder manuell durch Entfernen der Nodes `BLME_*` lassen sie sich entfernen.
