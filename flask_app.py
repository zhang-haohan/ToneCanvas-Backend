from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
import yaml
import random
import re
from datetime import datetime
import ssl

from utils.pitch_processing import process_pitch_file, save_interpolated_data_to_json, generate_sine_wave
from utils.file_parsing import parse_praat_pitch_file
from utils.audio_utils import calculate_times, segment_nonzero_times_and_frequencies, interpolate_pitch_segments
from utils.pitch_handling import handle_get_pitch_json, handle_get_pitch_audio
from utils.trace_handling import handle_send_trace, handle_send_button_log
os.chdir(os.path.dirname(__file__))

app = Flask(__name__)

# Enable CORS with specific configuration
# Enable CORS with specific configuration
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://10.10.149.76:3000",
    "http://10.10.149.76:3001",
    "http://172.20.10.3:3000",
    "http://172.20.10.3:3001",
    "https://tone-canvas-frontend.vercel.app"
]}})

corpus_dir = os.path.join(os.path.dirname(__file__), 'corpus')
icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
data_base_dir = os.path.join(os.path.dirname(__file__), 'data_base')
sessions_dir = os.path.join(data_base_dir, 'sessions')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

if not os.path.exists(data_base_dir):
    os.makedirs(data_base_dir)

if not os.path.exists(sessions_dir):
    os.makedirs(sessions_dir)

# The first two corpus items stay fixed; the remaining items are randomized once
# per user session and then consumed sequentially without repeats.
all_files = sorted([f for f in os.listdir(corpus_dir) if f.endswith('.wav')])
fixed_files = sorted([f for f in all_files if f.startswith("AA")])[:2]
randomizable_files = [f for f in all_files if f not in fixed_files]
files = fixed_files + randomizable_files

active_user_id = None

def build_file_order():
    random_part = randomizable_files.copy()
    random.shuffle(random_part)
    return fixed_files + random_part

def get_json_body():
    return request.get_json(silent=True) or {}

def get_request_user_id():
    body = get_json_body()
    return (
        request.args.get("user_id")
        or body.get("user_id")
        or request.form.get("user_id")
        or active_user_id
        or "__default__"
    )

def create_data_file_for_user(session_user_id):
    current_time = datetime.now().strftime("%Y%m%d_%H%M")
    new_file_name = f"{session_user_id}_{current_time}.yaml"
    data_file = os.path.join(data_base_dir, new_file_name)

    with open(data_file, 'w') as yaml_file:
        yaml.dump({
            "user_id": session_user_id,
            "created_at": current_time,
        }, yaml_file)

    return data_file

def safe_session_file_name(session_user_id):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", session_user_id)
    return safe_name or "__default__"

def get_session_path(session_user_id):
    return os.path.join(sessions_dir, f"{safe_session_file_name(session_user_id)}.yaml")

def normalize_session(session_user_id, session):
    session = session or {}
    session.setdefault("files", build_file_order())
    session.setdefault("current_index", 0)
    session.setdefault("current_data_file", None)
    session["user_id"] = None if session_user_id == "__default__" else session_user_id

    if not isinstance(session["files"], list) or not session["files"]:
        session["files"] = build_file_order()

    if not isinstance(session["current_index"], int):
        session["current_index"] = 0

    session["current_index"] = max(0, min(session["current_index"], len(session["files"])))
    return session

def load_session(session_user_id):
    session_path = get_session_path(session_user_id)
    if not os.path.exists(session_path):
        return None

    with open(session_path, 'r') as yaml_file:
        return normalize_session(session_user_id, yaml.safe_load(yaml_file))

def save_session(session_user_id, session):
    session_path = get_session_path(session_user_id)
    temp_session_path = f"{session_path}.{os.getpid()}.tmp"

    with open(temp_session_path, 'w') as yaml_file:
        yaml.safe_dump(session, yaml_file)

    os.replace(temp_session_path, session_path)

def create_session(session_user_id, reset=False):
    session = None if reset else load_session(session_user_id)

    if session is None:
        session = {
            "files": build_file_order(),
            "current_index": 0,
            "current_data_file": None,
            "user_id": None if session_user_id == "__default__" else session_user_id,
        }
        save_session(session_user_id, session)

    return normalize_session(session_user_id, session)

def get_session():
    session_user_id = get_request_user_id()
    return create_session(session_user_id)

def get_requested_index(session):
    requested_file = os.path.basename(request.args.get("file_name", ""))
    if requested_file and requested_file in session["files"]:
        return session["files"].index(requested_file)

    requested_index = request.args.get("index")
    if requested_index is not None:
        try:
            parsed_index = int(requested_index)
            if 0 <= parsed_index < len(session["files"]):
                return parsed_index
        except ValueError:
            pass

    return min(session["current_index"], len(session["files"]) - 1)

def get_requested_file(session):
    if not session["files"] or session["current_index"] >= len(session["files"]):
        return None
    return session["files"][get_requested_index(session)]

@app.route('/api/get-wav-file', methods=['GET'])
def get_wav_file():
    session = get_session()
    file_to_play = get_requested_file(session)
    if not file_to_play:
        return "No wav files found", 404

    return send_from_directory(corpus_dir, file_to_play)

@app.route('/api/switch-wav-file', methods=['POST'])
def switch_wav_file():
    session_user_id = get_request_user_id()
    session = create_session(session_user_id)
    if not session["files"]:
        return jsonify(error="No wav files found"), 404

    if session["current_index"] < len(session["files"]):
        session["current_index"] += 1

    save_session(session_user_id, session)

    is_finished = session["current_index"] >= len(session["files"])
    current_file_name = None if is_finished else session["files"][session["current_index"]]

    return jsonify(
        currentIndex=session["current_index"],
        fileName=current_file_name,
        totalFiles=len(session["files"]),
        isFinished=is_finished,
    )

@app.route('/api/get-icon/<filename>', methods=['GET'])
def get_icon(filename):
    return send_from_directory(icons_dir, filename)

@app.route('/api/get-pitch-json', methods=['GET'])
def get_pitch_json():
    session = get_session()
    return handle_get_pitch_json(
        session["files"],
        get_requested_index(session),
        temp_dir,
        corpus_dir,
    )

@app.route('/api/get-pitch-audio', methods=['GET'])
def get_pitch_audio():
    session = get_session()
    return handle_get_pitch_audio(
        session["files"],
        get_requested_index(session),
        temp_dir,
        corpus_dir,
    )

@app.route('/api/get-file-name', methods=['GET'])
def get_file_name():
    session = get_session()
    if not session["files"]:
        return jsonify(error="No wav files found"), 404

    if session["current_index"] >= len(session["files"]):
        return jsonify(fileName=None, isFinished=True)

    file_name = session["files"][session["current_index"]]
    return jsonify(fileName=file_name)

@app.route('/api/send-user-id', methods=['POST'])
def send_user_id():
    global active_user_id

    user_id = get_json_body().get('user_id')
    if not user_id:
        return jsonify(error="User ID is required"), 400

    active_user_id = user_id
    session = create_session(user_id, reset=True)
    session["current_data_file"] = create_data_file_for_user(user_id)
    save_session(user_id, session)

    return jsonify(
        message=f"Current data file set to: {session['current_data_file']}",
        fileOrder=session["files"],
        currentIndex=session["current_index"],
        fileName=session["files"][session["current_index"]] if session["files"] else None,
    ), 201

@app.route('/api/send-trace', methods=['POST'])
def send_trace():
    session = get_session()
    trace = get_json_body().get('trace')
    return handle_send_trace(
        trace,
        get_requested_index(session),
        session["files"],
        session["current_data_file"],
    )

@app.route('/api/send-button-log', methods=['POST'])
def send_button_log():
    session = get_session()
    button_name = get_json_body().get('button_name')
    return handle_send_button_log(button_name, session["current_data_file"])

@app.route('/api/get-progress', methods=['GET'])
def get_progress():
    session = get_session()
    total_files = len(session["files"])

    return jsonify({
        "total_files": total_files,
        "current_index": min(session["current_index"], max(total_files - 1, 0)),
        "is_finished": total_files > 0 and session["current_index"] >= total_files,
    }), 200

@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    session = get_session()
    session_user_id = session["user_id"]

    if "audio" not in request.files:
        return jsonify(error="No audio file provided"), 400
    
    if not session_user_id or not session["current_data_file"]:
        return jsonify(error="User ID and data file are required before uploading"), 400

    file = request.files["audio"]
    if file.filename == '':
        return jsonify(error="Empty filename"), 400
    
    # 确定用户目录
    user_upload_dir = os.path.join(UPLOAD_FOLDER, session_user_id)
    os.makedirs(user_upload_dir, exist_ok=True)

    # 计算音频序号
    existing_files = [f for f in os.listdir(user_upload_dir) if f.endswith(".wav") or f.endswith(".mp3")]
    file_index = len(existing_files) + 1  # 递增序号

    # 生成文件名
    base_filename = f"{session_user_id}_{os.path.basename(session['current_data_file']).replace('.yaml', '')}_{file_index}"
    wav_filename = f"{base_filename}.wav"
    mp3_filename = f"{base_filename}.mp3"

    # 保存 WAV 文件
    wav_path = os.path.join(user_upload_dir, wav_filename)
    file.save(wav_path)

    return jsonify({
        "message": "Upload successful",
        "wav_file": wav_filename,
    }), 201

if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='fullchain.pem', keyfile='privkey.pem')
    import logging
    logging.basicConfig(filename='flaskerror.log',level=logging.DEBUG)
    app.run(debug=True,ssl_context=context, host= '0.0.0.0', port=5000)
