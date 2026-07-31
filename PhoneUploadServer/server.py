from datetime import datetime
from pathlib import Path
import os
import socket

from flask import Flask, render_template_string, request
from PIL import Image, ImageOps
import qrcode
from waitress import serve

from SheetRectifier import process_photo


app = Flask(__name__)

BASE_FOLDER = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_FOLDER / "Uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
PROCESSED_FOLDER = BASE_FOLDER / "Processed"

# Limite massimo per ogni fotografia: 25 MB.
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


PAGE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invia il tuo disegno</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: Arial, sans-serif;
            text-align: center;
            background: #dff6ff;
            padding: 24px 15px;
        }

        .panel {
            width: 100%;
            max-width: 420px;
            padding: 28px 24px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        }

        h1 {
            margin-top: 0;
            color: #126782;
        }

        input {
            display: block;
            width: 100%;
            margin: 25px 0;
        }

        button {
            width: 100%;
            padding: 16px;
            border: none;
            border-radius: 12px;
            background: #168aad;
            color: white;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
        }

        button:active {
            background: #126782;
        }

        .message {
            margin-top: 20px;
            color: #168a45;
            font-weight: bold;
        }

        .error {
            color: #b42318;
        }
    </style>
</head>

<body>
    <div class="panel">
        <h1>Prototipo</h1>
        <p>Fotografa il disegno e invialo al computer.</p>

        <form method="POST" enctype="multipart/form-data">
            <input
                type="file"
                name="photo"
                accept="image/*"
                capture="environment"
                required
            >

            <button type="submit">Invia il disegno</button>
        </form>

        {% if message %}
            <div class="message {% if is_error %}error{% endif %}">
                {{ message }}
            </div>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def upload_photo():
    message = ""
    is_error = False

    if request.method == "POST":
        photo = request.files.get("photo")

        if photo is None or photo.filename == "":
            message = "Nessuna fotografia selezionata."
            is_error = True
        else:
            try:
                image = Image.open(photo.stream)
                image = ImageOps.exif_transpose(image).convert("RGB")

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                file_name = f"drawing_{timestamp}.jpg"
                destination = UPLOAD_FOLDER / file_name

                image.save(destination, format="JPEG", quality=95)
                print(f"Fotografia ricevuta: {destination}")

                rectified_path, fish_path = process_photo(
                    destination,
                    PROCESSED_FOLDER,
                )

                message = "Disegno inviato ed elaborato correttamente!"
                print(f"Foglio raddrizzato: {rectified_path}")
                print(f"Pesce PNG trasparente: {fish_path}")

            except Exception as error:
                message = (
                    "Foto ricevuta, ma non riesco a riconoscere correttamente "
                    "i quattro marcatori. Fotografa l'intero foglio e riprova."
                )
                is_error = True
                print(f"Errore: {error}")

    return render_template_string(
        PAGE,
        message=message,
        is_error=is_error,
    )


def get_local_ip():
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        # La connessione UDP serve solo a individuare l'indirizzo della rete
        # locale: non vengono inviati dati a Internet.
        connection.connect(("8.8.8.8", 80))
        return connection.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        connection.close()


if __name__ == "__main__":
    local_ip = get_local_ip()
    server_url = f"http://{local_ip}:5000"

    qr_path = BASE_FOLDER / "QR_Server.png"
    qrcode.make(server_url).save(qr_path)

    print()
    print("SERVER AVVIATO")
    print(f"Indirizzo: {server_url}")
    print(f"QR code: {qr_path}")
    print("Non chiudere questa finestra.")
    print()

    try:
        os.startfile(qr_path)
    except (AttributeError, OSError):
        pass

    serve(app, host="0.0.0.0", port=5000)
