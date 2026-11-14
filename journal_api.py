"""Notebook backend for MindEase. Register with:
    app.register_blueprint(create_journal_blueprint(db))
Uses the existing `journals` collection; old entries keep working."""
import re
import secrets
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from pymongo.errors import PyMongoError

IMG_RE = re.compile(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$")
MAX_TEXT, MAX_TITLE, MAX_ITEMS, MAX_PHOTOS, MAX_PHOTO_CHARS = 20000, 120, 40, 4, 1_500_000
MOODS = {"", "happy", "calm", "sad", "stressed", "angry"}


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def _csrf_ok():
    return secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session.get("csrf", ""))


def _clean_item(d):
    if not isinstance(d, dict):
        return None
    t, v = d.get("type"), d.get("value")
    if t not in ("sticker", "note", "photo") or not isinstance(v, str):
        return None
    if t == "photo":
        if len(v) > MAX_PHOTO_CHARS or not IMG_RE.match(v):
            return None
    else:
        v = v[:300]

    def num(k, lo, hi, dflt):
        try:
            return max(lo, min(hi, float(d.get(k, dflt))))
        except (TypeError, ValueError):
            return dflt

    return {"type": t, "value": v, "page": "right" if d.get("page") == "right" else "left",
            "x": num("x", 0, 90, 10), "y": num("y", 0, 92, 10),
            "size": num("size", 0.5, 3, 1), "rot": num("rot", -180, 180, 0)}


def _serialize(doc):
    created = doc.get("created_at") or doc["_id"].generation_time.replace(tzinfo=None)
    return {"id": str(doc["_id"]),
            "title": doc.get("title", ""),
            "mood": doc.get("mood", ""),
            "leftText": doc.get("leftText", ""),
            "rightText": doc.get("rightText", ""),
            "decorations": doc.get("decorations", []),
            "date_label": doc.get("date") or created.strftime("%B %d, %Y"),
            "created_at": created.isoformat()}


def create_journal_blueprint(db):
    bp = Blueprint("notebook", __name__)
    col = db["journals"]
    try:
        col.create_index([("username", 1), ("_id", 1)])
    except PyMongoError:
        pass

    def need_login(api):
        if "user" in session:
            return None
        if api:
            return jsonify(error="Please log in again."), 401
        return redirect(url_for("login"))

    def oid(raw):
        try:
            return ObjectId(raw)
        except (InvalidId, TypeError):
            return None

    @bp.route("/journal")
    def journal():
        denied = need_login(False)
        if denied:
            return denied
        open_id = request.args.get("entry", "")
        return render_template("journal.html", csrf=csrf_token(),
                               open_id=open_id if oid(open_id) else "")

    @bp.route("/api/journal", methods=["GET"])
    def list_entries():
        denied = need_login(True)
        if denied:
            return denied
        try:
            docs = col.find({"username": session["user"]}).sort("_id", 1)
            return jsonify(entries=[_serialize(d) for d in docs])
        except PyMongoError:
            return jsonify(error="Could not load entries."), 500

    @bp.route("/api/journal", methods=["POST"])
    def save_entry():
        denied = need_login(True)
        if denied:
            return denied
        if not _csrf_ok():
            return jsonify(error="Session check failed. Refresh the page."), 400
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Invalid request."), 400

        title = str(data.get("title", ""))[:MAX_TITLE].strip()
        left = str(data.get("leftText", ""))
        right = str(data.get("rightText", ""))
        mood = data.get("mood", "")
        if len(left) > MAX_TEXT or len(right) > MAX_TEXT:
            return jsonify(error="That entry is too long."), 400
        if mood not in MOODS:
            mood = ""
        raw_items = data.get("decorations", [])
        if not isinstance(raw_items, list) or len(raw_items) > MAX_ITEMS:
            return jsonify(error="Too many decorations on this entry."), 400
        items = [i for i in map(_clean_item, raw_items) if i]
        if sum(i["type"] == "photo" for i in items) > MAX_PHOTOS:
            return jsonify(error=f"Up to {MAX_PHOTOS} photos per entry."), 400

        fields = {"title": title, "leftText": left, "rightText": right, "mood": mood,
                  "text": f"{left} | {right}", "decorations": items,
                  "updated_at": datetime.utcnow()}
        try:
            if data.get("id"):
                _id = oid(data["id"])
                if not _id:
                    return jsonify(error="Entry not found."), 404
                res = col.update_one({"_id": _id, "username": session["user"]}, {"$set": fields})
                if res.matched_count == 0:
                    return jsonify(error="Entry not found."), 404
            else:
                now = datetime.utcnow()
                fields.update(username=session["user"], created_at=now,
                              date=now.strftime("%B %d, %Y"))
                _id = col.insert_one(fields).inserted_id
            return jsonify(entry=_serialize(col.find_one({"_id": _id})))
        except PyMongoError:
            return jsonify(error="Could not save. Please try again."), 500

    @bp.route("/api/journal/<entry_id>", methods=["DELETE"])
    def delete_entry(entry_id):
        denied = need_login(True)
        if denied:
            return denied
        if not _csrf_ok():
            return jsonify(error="Session check failed. Refresh the page."), 400
        _id = oid(entry_id)
        if not _id:
            return jsonify(error="Entry not found."), 404
        try:
            res = col.delete_one({"_id": _id, "username": session["user"]})
        except PyMongoError:
            return jsonify(error="Could not delete."), 500
        if res.deleted_count == 0:
            return jsonify(error="Entry not found."), 404
        return jsonify(ok=True)

    return bp
