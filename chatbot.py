"""
MindEase AI chatbot blueprint.
Requires: openai, pymongo, flask
Register with: app.register_blueprint(create_chatbot_blueprint(db))
"""

import os
from datetime import datetime, timezone

from bson import ObjectId
from flask import Blueprint, jsonify, request, session
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


chatbot_bp = Blueprint("chatbot", __name__)

CHAT_COLLECTION = "chat_conversations"
MAX_MESSAGE_LENGTH = 4000
CONTEXT_MESSAGE_LIMIT = 12

SYSTEM_PROMPT = """
You are MindEase AI, a warm, calm, practical wellness companion for college
students. You are part of the MindEase student-wellness website.

Personality and response style:
- Be kind, non-judgmental, encouraging, conversational, and respectful.
- Use clear, natural language. Avoid sounding clinical, robotic, or preachy.
- Acknowledge the student's feelings before offering suggestions.
- Ask one useful follow-up question when it would help the conversation.
- Offer small, realistic next steps rather than overwhelming plans.
- Help with ordinary questions, college life, exam stress, procrastination,
  time management, motivation, relationships, and everyday concerns.
- Keep most answers concise, but give detail when the student asks for it.
- Do not claim to be human, a therapist, doctor, or emergency service.
- Do not diagnose mental-health conditions, prescribe medication, or promise
  confidentiality beyond the website's stated privacy practices.
- Do not shame, dismiss, or minimize a student's feelings.

MindEase features:
When relevant, suggest that the student can use the Mood Tracker, Journal,
Music Therapy, Breathing Exercise, Study Planner, Study & Reflect, or Stress
Buster tools available in the MindEase website. Do not claim to have accessed
or changed their data unless a tool actually provides that capability.

Safety:
- You are a supportive wellness assistant, not a replacement for professional
  care.
- If the student describes imminent danger, a suicide attempt, or immediate
  intent to harm themselves or someone else, respond calmly and directly.
  Encourage them to contact local emergency services now, reach a trusted
  person who can stay with them, and move away from anything they could use
  to hurt themselves or others. Encourage contacting a local crisis hotline.
- If they mention self-harm without immediate intent, respond empathetically,
  encourage support from a trusted person and a qualified mental-health
  professional, and ask whether they are safe right now.
- Never provide instructions, methods, or encouragement for self-harm.
"""


def _current_username():
    """Only authenticated users may use the chatbot."""
    return session.get("user")


def _json_error(message, status):
    response = jsonify({"error": message})
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _conversation_id(raw_id):
    try:
        return ObjectId(raw_id)
    except Exception:
        return None


@chatbot_bp.after_request
def prevent_chat_caching(response):
    if request.path.startswith("/api/chat"):
        response.headers["Cache-Control"] = "no-store"
    return response


@chatbot_bp.post("/api/chat")
def send_chat_message():
    username = _current_username()
    if not username:
        return _json_error("Please log in to use MindEase AI.", 401)

    if not request.is_json:
        return _json_error("Send your message as JSON.", 415)

    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    raw_conversation_id = payload.get("conversation_id")

    if not isinstance(message, str):
        return _json_error("Message must be text.", 400)

    message = message.strip()
    if not message:
        return _json_error("Please type a message first.", 400)
    if len(message) > MAX_MESSAGE_LENGTH:
        return _json_error(
            f"Please keep messages under {MAX_MESSAGE_LENGTH} characters.",
            400
        )

    conversations = chatbot_bp.db[CHAT_COLLECTION]
    conversation = None
    conversation_id = None

    if raw_conversation_id:
        conversation_id = _conversation_id(raw_conversation_id)
        if conversation_id is None:
            return _json_error("Invalid conversation.", 400)

        # Ownership is checked on every read and write.
        conversation = conversations.find_one({
            "_id": conversation_id,
            "username": username
        })
        if conversation is None:
            return _json_error("Conversation not found.", 404)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return _json_error(
            "MindEase AI is not configured. Please contact the site administrator.",
            500
        )

    
    try:
        client = Groq(api_key=api_key)

        model = os.environ.get(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile"
        )

        previous_messages = (
            conversation.get("messages", []) if conversation else []
        )

        context = previous_messages[-CONTEXT_MESSAGE_LIMIT:]

        input_messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        input_messages.extend([
            {"role": item["role"], "content": item["content"]}
            for item in context
            if item.get("role") in {"user", "assistant"}
            and isinstance(item.get("content"), str)
        ])

        input_messages.append({
            "role": "user",
            "content": message
        })

        ai_response = client.chat.completions.create(
            model=model,
            messages=input_messages,
            max_completion_tokens=600
        )

        answer = (
            ai_response.choices[0].message.content or ""
        ).strip()

        if not answer:
            return _json_error(
                "I couldn't form a response just now. Please try again.",
                502
            )

    except Exception:
        chatbot_bp.logger.exception("MindEase AI request failed")
        return _json_error(
            "MindEase AI is having trouble responding. Please try again in a moment.",
            502
        )


    now = datetime.now(timezone.utc)
    user_message = {
        "role": "user",
        "content": message,
        "created_at": now
    }
    assistant_message = {
        "role": "assistant",
        "content": answer,
        "created_at": now
    }

    if conversation is None:
        result = conversations.insert_one({
            "username": username,
            "title": message[:65],
            "messages": [user_message, assistant_message],
            "created_at": now,
            "updated_at": now
        })
        conversation_id = result.inserted_id
    else:
        conversations.update_one(
            {"_id": conversation_id, "username": username},
            {
                "$push": {
                    "messages": {
                        "$each": [user_message, assistant_message]
                    }
                },
                "$set": {"updated_at": now}
            }
        )

    return jsonify({
        "conversation_id": str(conversation_id),
        "reply": answer
    })


@chatbot_bp.get("/api/chat/history")
def chat_history_list():
    username = _current_username()
    if not username:
        return _json_error("Please log in to view chat history.", 401)

    conversations = chatbot_bp.db[CHAT_COLLECTION]
    cursor = (
        conversations.find(
            {"username": username},
            {"title": 1, "created_at": 1, "updated_at": 1}
        )
        .sort("updated_at", -1)
        .limit(30)
    )

    items = []
    for item in cursor:
        items.append({
            "id": str(item["_id"]),
            "title": item.get("title", "New conversation"),
            "updated_at": (
                item["updated_at"].isoformat()
                if item.get("updated_at") else None
            )
        })

    return jsonify({"conversations": items})


@chatbot_bp.get("/api/chat/history/<conversation_id>")
def get_chat_history(conversation_id):
    username = _current_username()
    if not username:
        return _json_error("Please log in to view chat history.", 401)

    object_id = _conversation_id(conversation_id)
    if object_id is None:
        return _json_error("Invalid conversation.", 400)

    conversation = chatbot_bp.db[CHAT_COLLECTION].find_one({
        "_id": object_id,
        "username": username
    })
    if conversation is None:
        return _json_error("Conversation not found.", 404)

    messages = []
    for item in conversation.get("messages", []):
        messages.append({
            "role": item.get("role", "assistant"),
            "content": item.get("content", ""),
            "created_at": (
                item["created_at"].isoformat()
                if item.get("created_at") else None
            )
        })

    return jsonify({
        "conversation_id": str(conversation["_id"]),
        "title": conversation.get("title", "Conversation"),
        "messages": messages
    })


def create_chatbot_blueprint(db):
    """Create and return the chatbot blueprint using the existing Mongo DB."""
    chatbot_bp.db = db
    chatbot_bp.logger = __import__("logging").getLogger("mindease.chatbot")
    return chatbot_bp
