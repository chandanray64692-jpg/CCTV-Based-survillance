# Bison Prahari - AI Command Center & VSaaS Platform

Bison Prahari is an advanced, enterprise-grade AI-powered CCTV surveillance and Video Surveillance as a Service (VSaaS) platform built using **Django** and **YOLOv8** for real-time monitoring, intruder alerts, and automated threat detection.

---

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Project Setup & Installation](#project-setup--installation)
3. [Virtual Environment Configuration](#virtual-environment-configuration)
4. [Installing Dependencies](#installing-dependencies)
5. [Model Weights Setup](#model-weights-setup)
6. [Database Migration](#database-migration)
7. [Running the Application](#running-the-application)
8. [Automated Desktop Shortcut (Windows)](#automated-desktop-shortcut-windows)

---

## 🛠️ Prerequisites
Before getting started, make sure your system has the following installed:
* **Python** (Recommended: Python 3.10 or 3.11)
* **Git**
* **Google Chrome** (Recommended for dashboard access)

---

## 🚀 Project Setup & Installation

### Step 1: Clone the Repository
Open your terminal (Command Prompt or PowerShell) and clone the project from GitHub:
```bash
git clone https://github.com/chandanray64692-jpg/CCTV-Based-survillance.git
cd CCTV-Based-survillance
```

### Step 2: Create and Activate a Virtual Environment
It is best practice to run the project inside an isolated virtual environment:

* **For Windows (PowerShell):**
  ```powershell
  python -m venv venv
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  .\venv\Scripts\Activate.ps1
  ```

* **For Windows (Command Prompt):**
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```

### Step 3: Install Dependencies
Install all required packages listed in the `requirements.txt` file:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Download AI Model Weights
To keep the GitHub repository lightweight, heavy AI model files are excluded from tracking. 
* Download the YOLOv8 weight file (**`yolov8n.pt`** or your custom model weights) and place it directly inside the root project directory (`cctv survillance system/`).

### Step 5: Apply Database Migrations
Initialize the local SQLite database and apply Django migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Run the Development Server
Start the Django development server locally:
```bash
python manage.py runserver 127.0.0.1:8000
```

### Step 7: Access the Dashboard
Open your web browser and navigate to:
👉 **`http://127.0.0.1:8000/`**

---

## ⚡ Automated Desktop Shortcut (Optional for Windows)
If you want to run the server and open Google Chrome with a single double-click, create a file named `Run_Bison_Prahari.bat` on your Desktop with the following script:

```bat
@echo off
TITLE Bison Prahari - AI Command Center & VSaaS Platform
COLOR 0A

cd /d "C:\Users\ADMIN\Desktop\cctv survillance system"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

start /min cmd /c "python manage.py runserver 127.0.0.1:8000"
timeout /t 3 /nobreak > nul
start chrome "http://127.0.0.1:8000/"

pause
```

---

## 🛡️ License & Contributions
Developed for high-security intelligent surveillance and monitoring operations. Feel free to fork, contribute, or open issues for enhancements!