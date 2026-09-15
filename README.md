# Tone Canvas Backend

This project is a Flask-based backend for handling tone-related audio files, processing pitch data, and managing user interactions. The backend provides APIs for handling `.wav` files, pitch processing, trace recording, and more. 

## Project Structure
```
.
├── backend-dev.yaml        # Docker Compose configuration for development
├── Dockerfile              # Dockerfile for containerized deployment
├── flask_app.py            # Main Flask application entry point
├── requirements.txt        # Python dependencies
├── [corpus]                # Directory for storing .wav and .Pitch files
├── [data_base]             # Directory for storing user-generated YAML files
├── [temp]                  # Temporary files directory
└── [utils]                 # Utility scripts for modular functionality
    ├── audio_utils.py      # Helper functions for pitch data interpolation
    ├── file_parsing.py     # Functions for parsing Praat pitch files
    ├── pitch_handling.py   # Functions for handling pitch-related APIs
    ├── pitch_processing.py # Core pitch processing logic
    └── trace_handling.py   # Functions for handling trace and button logs
```

## Setup Instructions

### Prerequisites
- Python 3.11 or higher
- Docker (optional for containerized deployment)

### Install Dependencies
1. Clone the repository.
2. Navigate to the project directory.
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .env
   source .env/bin/activate   # For Linux/macOS
   .env\\Scripts\\activate    # For Windows
   pip install -r requirements.txt
4. Need to intall apache2-dev
   ```

### Run Locally
Start the Flask application:
```bash
python flask_app.py
```

### Run with Docker
1. Build and start the Docker container:
   ```bash
   docker-compose -f backend-dev.yaml up --build
   ```
2. Access the API at `http://localhost:5000`.

---

## API Documentation

### 1. **GET /api/get-wav-file**
Returns the current `.wav` file from the `corpus` directory.

- **Response**:
  - Status `200`: Binary audio file.
  - Status `404`: `"No wav files found"`.

---

### 2. **POST /api/switch-wav-file**
Switches to the next `.wav` file in the `corpus` directory.

- **Response**:
  - Status `200`: `{ "currentIndex": <current_index> }`.

---

### 3. **GET /api/get-icon/<filename>**
Returns a static icon file from the `icons` directory.

- **Response**:
  - Status `200`: Binary image file.
  - Status `404`: `"File not found"`.

---

### 4. **GET /api/get-pitch-json**
Generates and returns interpolated pitch data in JSON format for the current `.wav` file.

- **Response**:
  - Status `200`: JSON file containing pitch data.
  - Status `404`: `"No wav files found"` or `"No pitch file found for the current wav file"`.

---

### 5. **GET /api/get-pitch-audio**
Generates and returns a `.wav` file containing a sine wave representation of pitch data.

- **Response**:
  - Status `200`: Binary `.wav` file.
  - Status `404`: `"No wav files found"` or `"No pitch file found for the current wav file"`.

---

### 6. **GET /api/get-file-name**
Returns the name of the current `.wav` file.

- **Response**:
  - Status `200`: `{ "fileName": "<file_name>" }`.
  - Status `404`: `"No wav files found"`.

---

### 7. **POST /api/send-user-id**
Registers a user ID and initializes a corresponding YAML file in the `data_base` directory.

- **Request Body**:
  ```json
  {
    "user_id": "<user_id>"
  }
  ```

- **Response**:
  - Status `201`: `{ "message": "Current data file set to: <file_path>" }`.
  - Status `400`: `"User ID is required"`.

---

### 8. **POST /api/send-trace**
Records trace data (start, body, and end) into the user's YAML file.

- **Request Body**:
  ```json
  {
    "trace": {
      "trace_start": "<timestamp>",
      "trace_body": [
        { "timestamp": "<timestamp>", "pitch": <float>, "x": <float>, "y": <float> },
        ...
      ],
      "trace_end": "<timestamp>"
    }
  }
  ```

- **Response**:
  - Status `201`: `{ "message": "Trace data appended to YAML file." }`.
  - Status `400`: `"Trace data is required"`.

---

### 9. **POST /api/send-button-log**
Records a button press event in the user's YAML file.

- **Request Body**:
  ```json
  {
    "button_name": "<button_name>"
  }
  ```

- **Response**:
  - Status `201`: `{ "message": "Button log appended to YAML file." }`.
  - Status `400`: `"Button name is required"`.

---

### 10. **GET /api/get-progress**
Returns the total number of `.wav` files and the current index.

- **Response**:
  ```json
  {
    "total_files": <int>,
    "current_index": <int>
  }
  ```

---

## Key Features
- Modularized code structure for maintainability (`utils` directory).
- Dockerized setup for easy deployment.
- APIs for audio file management, pitch processing, and trace logging.
- YAML-based trace and button log storage.

## Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a feature branch.
3. Submit a pull request with detailed explanation.

## License
This project is licensed under the Apache2.0 License. See the LICENSE file for details.
