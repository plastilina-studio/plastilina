# plastilina

## Validate extensions
Blender ships a command line tool to validate extensions

Run the command inside the add-on root directory

Fedora (Flatpak):
flatpak run org.blender.Blender --command extension validate .

Fedora (dnf):
blender --command extension validate .

## Build zip folder

Run the command inside the add-on root directory

Fedora (flatpak):
flatpak run org.blender.Blender --command extension build --source-dir . --output-dir dist/

To validate the zip folder run the following command: 
Fedora (flatpak):
flatpak run org.blender.Blender --command extension validate dist/plastilina-x.y.z.zip

## Install the built zip to test
Open Blender then from the top menu:
Edit -> Preferences -> Get Extensions -> the dropdown arrow at the top right ->
Install from Disk... -> Pick the zip.