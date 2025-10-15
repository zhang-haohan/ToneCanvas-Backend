from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
import yaml
import random
from datetime import datetime

from utils.pitch_processing import process_pitch_file, save_interpolated_data_to_json, generate_sine_wave
from utils.file_parsing import parse_praat_pitch_file
from utils.audio_utils import calculate_times, segment_nonzero_times_and_frequencies, interpolate_pitch_segments
from utils.pitch_handling import handle_get_pitch_json, handle_get_pitch_audio
from utils.trace_handling import handle_send_trace, handle_send_button_log

app = Flask(__name__)

# Enable CORS with specific configuration
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:3000",
    "https://740d-88-173-177-226.ngrok-free.app",
    "https://f650-2a01-e0e-1002-7bbe-e97-f8eb-b354-d8c6.ngrok-free.app",
    "https://tone-canvasv2.vercel.app"
]}})

corpus_dir = os.path.join(os.path.dirname(__file__), 'corpus')
icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
data_base_dir = os.path.join(os.path.dirname(__file__), 'data_base')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

if not os.path.exists(data_base_dir):
    os.makedirs(data_base_dir)

# 🧠 文件排序逻辑修改区域
all_files = [f for f in os.listdir(corpus_dir) if f.endswith('.wav')]
aa_files = sorted([f for f in all_files if f.startswith("AA")])
other_files = [f for f in all_files if not f.startswith("AA")]

if len(other_files) > 2:
    fixed_part = other_files[:2]  # 保留前两个不变
    random_part = other_files[2:]  # 后面的打乱
    random.shuffle(random_part)
    other_files = fixed_part + random_part
else:
    random.shuffle(other_files)

files = aa_files + other_files

# 其余状态初始化
current_index = 0
user_id = None
current_data_file = None

@app.route('/api/get-wav-file', methods=['GET'])
def get_wav_file():
    global current_index
    if not files:
        return "No wav files found", 404

    file_to_play = files[current_index]
    return send_from_directory(corpus_dir, file_to_play)
# ✅ 接收前端发送的用户 ID 并记录
@app.route('/api/send-user-id', methods=['POST'])
def receive_user_id():
    global user_id
    data = request.get_json()

    if not data or "user_id" not in data:
        return {"status": "error", "message": "user_id missing"}, 400

    user_id = data["user_id"]

    # ✅ 打印日志，确认交互
    print(f"[INFO] ✅ Received user ID: {user_id}")

    # ✅ 保存到本地日志文件（用于你之后验证是否记录成功）
    with open("user_log.txt", "a") as f:
        f.write(f"New session started: user_id={user_id}\n")

    return {"status": "ok", "user_id": user_id}, 200
@app.route('/api/switch-wav-file', methods=['POST'])
def switch_wav_file():
    global current_index
    current_index = (current_index + 1) % len(files)
    return jsonify(currentIndex=current_index)

@app.route('/api/get-icon/<filename>', methods=['GET'])
def get_icon(filename):
    return send_from_directory(icons_dir, filename)

@app.route('/api/get-pitch-json', methods=['GET'])
def get_pitch_json():
    global current_index
    return handle_get_pitch_json(files, current_index, temp_dir, corpus_dir)

@app.route('/api/get-pitch-audio', methods=['GET'])
def get_pitch_audio():
    global current_index
    return handle_get_pitch_audio(files, current_index, temp_dir, corpus_dir)

@app.route('/api/get-file-name', methods=['GET'])
def get_file_name():
    global current_index
    if not files:
        return jsonify(error="No wav files found"), 404

    file_name = files[current_index]
    return jsonify(fileName=file_name)

@app.route('/api/send-user-id', methods=['POST'])
def send_user_id():
    global user_id, current_data_file

    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify(error="User ID is required"), 400

    current_time = datetime.now().strftime("%Y%m%d_%H%M")
    user_file_path = os.path.join(data_base_dir, f"{user_id}.yaml")

    if os.path.exists(user_file_path):
        current_data_file = user_file_path
    else:
        new_file_name = f"{user_id}_{current_time}.yaml"
        current_data_file = os.path.join(data_base_dir, new_file_name)
        with open(current_data_file, 'w') as yaml_file:
            yaml.dump({"user_id": user_id, "created_at": current_time}, yaml_file)

    return jsonify(message=f"Current data file set to: {current_data_file}"), 201

from flask import jsonify  # ✅ 确保顶部有

@app.route('/api/send-trace', methods=['POST'])
def send_trace():
    """
    ✅ Fix applied:
    - Standardize response to JSON always
    - Avoid throwing 400/500 that cause frontend red error
    - Help future cloud deployment check logs more cleanly
    """
    global current_index, current_data_file, user_id  # ✅ 包含 user_id 方便日志追踪

    # ✅ 1. 数据解析和基础校验（不直接抛 400，让返回结构统一）
    data = request.get_json(silent=True) or {}
    trace = data.get('trace')

    if not user_id:
        return jsonify({"status": "error", "message": "User ID not initialized"}), 400

    if trace is None:
        # ✅ 不抛异常，给前端 JSON 提示
        return jsonify({"status": "error", "message": "No trace data received"}), 200

    # ✅ 2. 调用原本处理逻辑，并保护异常
    try:
        handle_send_trace(trace, current_index, files, current_data_file)
    except Exception as e:
        # ✅ 捕获异常避免500，并标准 JSON 返回
        return jsonify({
            "status": "error",
            "message": f"Trace saving failed: {str(e)}"
        }), 200  # ✅ 不报500，避免前端中断任务

    # ✅ 3. 返回标准成功响应 —— 和 send-button-log 风格统一
    return jsonify({
        "status": "ok",
        "message": f"Trace logged (index={current_index})"
    }), 200

@app.route('/api/send-button-log', methods=['POST'])
def send_button_log():
    global current_data_file
    button_name = request.json.get('button_name')
    # original treat logic
    result = handle_send_button_log(button_name, current_data_file)
    
    # ✅ 统一成功返回格式，确保前端 response.ok = true
    return jsonify({"status": "ok", "message": f"Button '{button_name}' logged"}), 200

@app.route('/api/get-progress', methods=['GET'])
def get_progress():
    global current_index

    total_files = len(files)

    return jsonify({
        "total_files": total_files,
        "current_index": current_index
    }), 200

@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    """
    ✅ Fix applied:
    - current_data_file is NO LONGER REQUIRED for upload
    - Only user_id is needed → more user-friendly
    - Always return JSON {status:"ok"/"error"} to avoid frontend exceptions
    """
    global user_id  

    # ✅ 只检查 user_id — 不再阻塞上传流程
    if not user_id:
        return jsonify({"status": "error", "message": "User ID missing"}), 400

    # ✅ 检查音频数据是否存在
    if "audio" not in request.files:
        return jsonify({"status": "error", "message": "No audio file provided"}), 400

    file = request.files["audio"]
    if file.filename == '':
        return jsonify({"status": "error", "message": "Empty filename"}), 400

    # ✅ 上传目录始终按 user_id 归档，不需要 YAML 命名依赖
    user_upload_dir = os.path.join(UPLOAD_FOLDER, user_id)
    os.makedirs(user_upload_dir, exist_ok=True)

    # ✅ 自动生成文件名（不依赖 current_data_file）
    existing_files = [f for f in os.listdir(user_upload_dir) if f.endswith(".wav") or f.endswith(".mp3")]
    file_index = len(existing_files) + 1
    current_time = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{user_id}_recording_{file_index}.wav"

    file_path = os.path.join(user_upload_dir, filename)
    file.save(file_path)

    # ✅ 前端完全兼容 JSON + 200 OK —— 不会报 Upload failed
    return jsonify({
        "status": "ok",
        "message": "Upload successful",
        "file": filename,
        "path": file_path
    }), 200
