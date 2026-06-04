from flask import Blueprint, jsonify, request

from app.youtube import VALID_FORMATS, ConversionError, convert_url

bp = Blueprint("main", __name__)


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
        result = convert_url(url, fmt)
    except ConversionError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(
        {
            "ok": True,
            "video_id": result["video_id"],
            "title": result["title"],
            "format": result["format"],
            "filename": result["filename"],
            "path": result["path"],
        }
    )