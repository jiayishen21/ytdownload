import shutil

from flask import Blueprint, after_this_request, jsonify, render_template, request, send_file

from app.validators import InvalidYouTubeURLError, validate_youtube_url
from app.youtube import VALID_FORMATS, ConversionError, convert_url

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/convert", methods=["POST"])
def convert():
    data = request.get_json(silent=True) or {}
    url = data.get("url") or request.form.get("url")
    fmt = (data.get("format") or request.form.get("format") or "mp3").lower()

    if not url:
        return jsonify({"error": "Missing required field: url"}), 400

    if fmt not in VALID_FORMATS:
        return jsonify(
            {"error": f"format must be one of: {', '.join(sorted(VALID_FORMATS))}"}
        ), 400

    try:
        url = validate_youtube_url(url)
    except InvalidYouTubeURLError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = convert_url(url, fmt)
    except ConversionError as exc:
        return jsonify({"error": str(exc)}), 500

    tmpdir = result["tmpdir"]
    file_path = result["path"]
    filename = result["filename"]
    mimetype = result["mimetype"]

    @after_this_request
    def _cleanup(response):
        shutil.rmtree(tmpdir, ignore_errors=True)
        return response

    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )