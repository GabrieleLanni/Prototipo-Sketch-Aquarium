# Prototipo Sketch Aquarium

This repository contains a Unity aquarium prototype and a small Python server
that receives a photo of a hand-drawn fish from a phone. The server detects the
four printed markers, straightens the sheet, extracts the fish silhouette, and
writes a transparent PNG that Unity displays in the scene.

## Requirements

- Unity `6000.3.18f1` (the version recorded by the project)
- Python 3.10 or newer
- A phone and the computer running the server on the same local network
- Git LFS if the repository is cloned with Git and you want the tracked sample
  images restored

  Run
  ```bash
  python -m pip install -r requirements.txt
  ```
  to install all the requirements in python

## Open the Unity project

1. Install Unity `6000.3.18f1` through Unity Hub. Include the platform module
   you intend to run.
2. Open this folder in Unity Hub:

   `Prototipo-Sketch-Aquarium/`

3. Open `Assets/Scenes/SampleScene.unity`.
4. Press Play. The `PhoneDrawingReceiver` object is already connected to the
   `DrawingPreview` SpriteRenderer and checks for new files every second.

The receiver expects processed files at:

`PhoneUploadServer/Processed/fish_*.png`

Keep that folder inside the Unity project root unless you change the
`processedFolder` field in the Inspector.

## Start the phone upload server

From the `PhoneUploadServer` directory, create and activate a virtual
environment, then install the dependencies:

### macOS / Linux

```bash
cd PhoneUploadServer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python server.py
```

### Windows PowerShell

```powershell
cd PhoneUploadServer
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python server.py
```

The server prints a LAN URL and regenerates `PhoneUploadServer/QR_Server.png`.
Open the URL on the phone, or scan the QR code, then upload a photo showing the
entire sheet and all four black markers. The processed fish is saved into
`PhoneUploadServer/Processed/` and should appear in Unity automatically.

Both devices must be on the same Wi-Fi network. If the phone cannot connect,
allow Python through the computer's firewall and make sure port `5000` is not
blocked.

## Run the image processor directly

With the virtual environment active:

```bash
cd PhoneUploadServer
python SheetRectifier.py --input Uploads/my-photo.jpg
```

If `--input` is omitted, the newest supported image in `Uploads/` is used.

## Git LFS sample files

The sample JPG/PNG files are tracked with Git LFS. After cloning:

```bash
git lfs install
git lfs pull
```

A GitHub source ZIP can contain small LFS pointer files instead of the actual
images. This does not prevent the prototype from working: upload a new photo
through the server, or clone the repository with Git LFS enabled.

## Troubleshooting

- **Unity says the project was created with another version:** select Unity
  `6000.3.18f1`; allow Unity Package Manager to resolve the packages listed in
  `Packages/manifest.json`.
- **The phone page works but Unity shows nothing:** confirm that the server is
  writing `fish_*.png` into `PhoneUploadServer/Processed/`, that Unity is in
  Play mode, and that `PhoneDrawingReceiver.targetRenderer` is assigned.
- **Marker detection fails:** photograph the whole sheet in good light without
  covering or cropping any of the four markers.
- **`ModuleNotFoundError` when starting the server:** activate the virtual
  environment and run `python -m pip install -r requirements.txt` again.
