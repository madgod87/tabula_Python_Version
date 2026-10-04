# Tabula-Python-Web

A lightweight, Python-based port of the [Tabula](https://tabula.technology/) web interface. This project allows you to extract tabular data from PDF files using a completely Python-based stack, removing the need for a Java installation.

## Features
- **No Java Requirement**: Uses `pdfplumber` and `PyMuPDF` (`fitz`) to process and extract data from PDFs.
- **Classic UI**: Retains the powerful Backbone.js-based interface from the original Tabula project.
- **Format Support**: Export extracted tables to CSV, TSV, and JSON formats.

## Prerequisites
- Python 3.7+

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/tabula-python-web.git
cd tabula-python-web
```

2. Install the required Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://127.0.0.1:8080
```

3. Upload a PDF, select the bounding boxes for the tables you want to extract, and click **Preview & Export Extracted Data**.

## Architecture

- **Backend**: Flask (Python) handles API requests, file uploads, and background processing.
- **PDF Processing**: 
  - `PyMuPDF` (`fitz`) handles fast page rendering and thumbnail generation.
  - `pdfplumber` provides accurate table extraction logic (Lattice and Stream methods).
- **Frontend**: Backbone.js and jQuery power the single-page application, maintaining the original Tabula user experience.

## License

This project is a port of Tabula and retains its open-source spirit. See the original project for licensing details.
