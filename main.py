import os
from flask import Flask, request, render_template, send_file
from utils import process_documents

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    uploaded_files = request.files.getlist("files")
    filepaths = []

    for file in uploaded_files:
        path = os.path.join("uploads", file.filename)
        os.makedirs("uploads", exist_ok=True)
        file.save(path)
        filepaths.append(path)

    output_path = process_documents(filepaths)
    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
