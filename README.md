# AI News Studio Foundation

A professional Windows desktop application designed with CustomTkinter and clean, object-oriented, production-ready python architecture. This foundation provides the layout, managers, logging, configuration, and formal abstract interfaces to support future AI modules (voices, talking heads, cinematic B-roll, automated editing).

## Project Structure

```
AI-News-Studio/
├── app/                  # CustomTkinter GUI layout, themes, views, custom widgets
├── core/                 # Abstract engine interfaces and core application managers
├── config/               # Default system configurations (JSON/YAML)
├── models/               # Placeholder folder for future AI weights and model files
├── assets/               # Assets (icons, fonts, images)
├── projects/             # User workspace directory for video projects
├── output/               # Exported final videos
├── logs/                 # Rolling and crash log records
├── tests/                # Verification unit tests
├── main.py               # Main bootloader, configuration binder, global exception handling
├── requirements.txt      # Python library dependencies
└── README.md             # This document
```

## Getting Started

### Prerequisites

- Python 3.11+
- Windows OS (with Tkinter support)

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the application:
   ```bash
   python main.py
   ```

## Architecture Design

- **Separation of Concerns**: UI widgets and views (`app/`) communicate only with logic managers (`core/managers/`). Managers hold the business state.
- **Dependency Injection**: Managers are instantiated at bootstrap and passed to views, preventing global state.
- **Abstract Engines**: All heavy-lifting AI components conform to strict interfaces in `core/interfaces/` using python's `abc` module.
- **Global Error Handling**: Unhandled GUI and execution errors are logged to `logs/crash_<timestamp>.log` and display a clean dialog.
