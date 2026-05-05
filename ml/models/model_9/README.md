## 🚀 How It Works (Step-by-Step)

### 1. Database Preparation (`encode_employees.py`)
*   **Purpose**: To "teach" the system what employees look like.
*   **Logic**: 
    - The script scans the `employee_photos` folder.
    - It generates a **Face Encoding** (128D vectors) for each person using `face_recognition`.
    - These encodings are saved into `employees.pkl`.

### 2. Live Access System (`access_system.py`)
*   **Purpose**: The main software that runs at the entrance.
*   **Layer 1: Local Face Recognition**:
    - Captures live video and compares faces against the local database using the `face_recognition` library.
*   **Layer 2: Local Anti-Spoofing (DeepFace)**:
    - If a face matches, it passes through **DeepFace Anti-Spoofing** logic.
    - This runs locally on your machine (using `tf-keras`) to detect if the face is a real human or a photo/screen.
*   **Layer 3: Local OCR Badge Check (EasyOCR)**:
    - The system scans the frame for text using **EasyOCR** (GPU accelerated).
    - It checks if the "Supermarket Name" (e.g., Carrefour) is visible on the person's uniform or badge.

## 🛠️ Technology Stack

*   **Python**: Core language.
*   **DeepFace**: For local anti-spoofing and face analysis.
*   **EasyOCR**: For local Optical Character Recognition (reads badges).
*   **PyTorch/TensorFlow**: Backend engines for the AI models.
*   **Face_recognition**: For local face comparison.

## 💡 Key Design Decisions (The "Smart" Parts)

### A. Bypassing Windows Installation Issues
Standard `dlib` (required for face recognition) is very difficult to install on Windows because it requires Visual Studio C++. We solved this by using a **pre-compiled binary wheel**, allowing the system to run on any machine with just `pip`.

### B. Handling API Quotas (Rate Limiting)
The "Free Tier" of Google Gemini only allows a certain number of requests per minute. To prevent the program from crashing, we implemented:
1.  **Caching**: The system remembers a person for **15 seconds** after verifying them once.
2.  **Cooldown**: It strictly limits API calls to avoid hitting the rate limit while the same person is standing in front of the camera.

### C. Graceful Fallback
If the Gemini API reaches its limit or the internet is slow, the script is designed NOT to crash. It displays a warning and falls back to Layer 1 (Face Recognition) to ensure the door still opens for valid employees.

## 📁 File Structure
- `encode_employees.py`: Script to generate the face data.
- `access_system.py`: The main live tracking application.
- `employees.pkl`: The generated database of face embeddings.
- `requirements.txt`: List of all libraries needed to run the project.
- `.env`: Contains the secret `GEMINI_API_KEY`.

## ⚙️ How to Run
1. Put photos of employees in the `employee_photos` folder (rename them to 'name.jpg').
2. Run `python encode_employees.py`.
3. Run `python access_system.py`.
