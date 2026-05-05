#  Nefercode - AI-Powered Full-Stack Development Engine



##  Overview

**Nefercode Unified** is an AI-powered code generation engine that bridges the gap between natural language descriptions and fully functional web applications. Unlike traditional no-code tools, Nefercode generates clean, readable HTML/CSS/JavaScript code with real backend integration, making it suitable for both rapid prototyping and production deployment.

### Facilities

- **Real Database Persistence**: SQLite backend
- **AI-Generated Dummy Data**: Context-aware sample data for instant testing
- **Production-Grade UI**: Distinctive design systems, not generic templates
- **Iterative Development**: Chat-based refinement of existing applications
---

##  Key Features

###  AI-Powered Generation
- **Natural Language Interface**: Describe your app in plain English
- **Contextual Understanding**: Interprets domain-specific requirements (medical, e-commerce, etc.)
- **Smart Iteration**: Modify existing apps through conversational commands
- **Multi-Page Support**: Generates complex applications with routing and navigation

###  Real Backend Integration
- **SQLite Database**: Persistent data storage that survives restarts
- **Auto-Schema Generation**: Tables and columns created from your first data write
- **Generic CRUD API**: RESTful endpoints work for any table structure
- **AI-Powered Data Seeding**: Realistic dummy data generated for instant testing
---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  USER INTERFACE                     │
│              (Gradio Chat Interface)                │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │   AI ENGINE (Groq)  │
         │  - Code Generation  │
         │  - UI Design        │
         │  - Validation       │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │   Code Generator    │
         │   - HTML/CSS/JS     │
         │   - Design System   │
         │   - API Integration │
         └──────────┬──────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
┌─────────────┐            ┌──────────────────┐
│  FRONTEND   │            │  BACKEND API     │
│  (Browser)  │◄──────────►│  (Flask Server)  │
│             │   fetch()  │                  │
│ - Live UI   │            │ - CRUD Routes    │
│ - Preview   │            │ - SQLite DB      │
│ - User Code │            │ - AI Data Seed   │
└─────────────┘            └─────────┬────────┘
                                     │
                                     ▼
                           ┌──────────────────┐
                           │   SQLite File    │
                           │ nefercode_db.db  │
                           │  (Persistent)    │
                           └──────────────────┘
```



## 📦 Requirements

### API Keys
- **Groq API Key**: Free tier available at [console.groq.com](https://console.groq.com)
  - 4 keys included in code (can use your own)

---

## 🚀 Installation

### Step 1: Download Files

Download these 3 files to the same folder:
```
your-project/
├── app.py
├── local_backend.py
└── requirements.txt
```

### Step 2: Install Dependencies

Open terminal in the project folder and run:

**Windows:**
```powershell
pip install -r requirements.txt
```

**macOS/Linux:**
```bash
pip3 install -r requirements.txt
```

### Step 3: Verify Installation

```bash
python -c "import flask, gradio, requests; print('✅ All dependencies installed')"
```

---

## ⚡ Quick Start

### Two-Terminal Setup

**Terminal 1 - Start Backend:**
```bash
python local_backend.py
```

Wait for:
```
==================================================
 🗄️  Nefercode Local Backend
 🌐  http://127.0.0.1:5000
==================================================
```

**Terminal 2 - Start Main App:**
```bash
python app.py
```

Wait for:
```
============================================================
 🚀  NEFERCODE UNIFIED  v3
✅ Backend is already running!
 🌐  Gradio:  http://127.0.0.1:7866
============================================================
```

**Browser opens automatically** to `http://127.0.0.1:7866`

---
