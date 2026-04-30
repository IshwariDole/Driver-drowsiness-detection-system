from flask import Blueprint, request, jsonify, session
from models import create_user, verify_user, find_user

routes = Blueprint("routes", __name__)

@routes.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if find_user(username):
        return jsonify({"error": "User already exists"}), 400

    create_user(username, password)
    return jsonify({"message": "User registered successfully"}), 201


@routes.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if verify_user(username, password):
        session["user"] = username
        return jsonify({"message": "Login successful"})
    else:
        return jsonify({"error": "Invalid credentials"}), 401


@routes.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"message": "Logged out successfully"})
