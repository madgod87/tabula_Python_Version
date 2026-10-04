from flask import Flask, request, jsonify, send_from_directory, send_file
import pdfplumber
import fitz # PyMuPDF
import os
import uuid
import json
import time
import csv
import io
import shutil
import threading

app = Flask(__name__, static_folder='webapp')

UPLOAD_FOLDER = 'workspace'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DOCUMENTS = {}
JOBS = {}

@app.route('/')
@app.route('/about')
@app.route('/help')
@app.route('/mytemplates')
@app.route('/pdf/<file_id>')
def serve_index(file_id=None):
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if path.startswith(('js/', 'css/', 'img/', 'swf/', 'fonts/')):
        return send_from_directory('webapp/static', path)
    return send_from_directory('webapp', path)

@app.route('/pdfs/<path:path>')
def serve_pdfs(path):
    return send_from_directory(UPLOAD_FOLDER, path)

@app.route('/documents')
def list_documents():
    return jsonify(list(DOCUMENTS.values()))

def process_pdf_background(pdf_path, file_dir, job_batch, filename):
    try:
        doc = fitz.open(pdf_path)
        pages_meta = []
        
        total_pages = len(doc)
        
        for i in range(total_pages):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=150)
            img_path = os.path.join(file_dir, f"document_800_{i + 1}.png")
            pix.save(img_path)
            
            rect = page.rect
            pages_meta.append({
                "width": rect.width,
                "height": rect.height,
                "number": i + 1,
                "rotation": page.rotation,
                "deleted": False
            })
            
            JOBS[job_batch] = int(((i + 1) / total_pages) * 100)
            
        with open(os.path.join(file_dir, 'pages.json'), 'w') as f:
            json.dump(pages_meta, f)
            
        with open(os.path.join(file_dir, 'tables.json'), 'w') as f:
            json.dump([], f)
            
        file_id = os.path.basename(file_dir)
        DOCUMENTS[file_id] = {
            "id": file_id,
            "original_filename": filename,
            "size": os.path.getsize(pdf_path),
            "page_count": total_pages,
            "thumbnail_sizes": [800]
        }
        
    except Exception as e:
        print(f"Error processing PDF: {e}")
        JOBS[job_batch] = -1
    finally:
        if JOBS[job_batch] != -1:
            JOBS[job_batch] = 100

@app.route('/upload.json', methods=['POST'])
def upload_file():
    if 'file' not in request.files and 'files[]' not in request.files:
        return jsonify([{"success": False, "message": "No file uploaded"}]), 400
        
    file = request.files.get('file') or request.files.get('files[]')
    if not file or file.filename == '':
        return jsonify([{"success": False, "message": "No selected file"}]), 400
        
    if file:
        file_id = str(uuid.uuid4())
        job_batch = str(uuid.uuid4())
        
        file_dir = os.path.join(UPLOAD_FOLDER, file_id)
        os.makedirs(file_dir, exist_ok=True)
        pdf_path = os.path.join(file_dir, "document.pdf")
        file.save(pdf_path)
        
        JOBS[job_batch] = 0
        
        thread = threading.Thread(target=process_pdf_background, args=(pdf_path, file_dir, job_batch, file.filename))
        thread.daemon = True
        thread.start()
        
        response_data = json.dumps([{
            "success": True,
            "file_id": file_id,
            "upload_id": job_batch,
            "filename": file.filename
        }])
        return response_data, 200, {'Content-Type': 'text/plain'}

@app.route('/queue/<job_batch>/json', methods=['GET'])
def get_queue(job_batch):
    file_id = request.args.get('file_id')
    progress = JOBS.get(job_batch, 0)
    
    if progress == -1:
        return jsonify({
            "status": "error",
            "error_type": "unknown",
            "message": "Sorry, your file upload could not be processed.",
            "pct_complete": 99
        })
        
    return jsonify({
        "status": "completed" if progress == 100 else "working",
        "pct_complete": progress,
        "file_id": file_id,
        "upload_id": job_batch,
        "message": "complete" if progress == 100 else f"Generating page thumbnails... ({progress}%)",
        "messages": [],
        "warnings": []
    })

@app.route('/pdf/<file_id>/metadata.json')
def get_metadata(file_id):
    if file_id in DOCUMENTS:
        return jsonify(DOCUMENTS[file_id])
    return jsonify({"error": "not found"}), 404

@app.route('/pdf/<file_id>/data', methods=['POST'])
def extract_data(file_id):
    pdf_path = os.path.join(UPLOAD_FOLDER, file_id, "document.pdf")
    coords = json.loads(request.form.get('coords', '[]'))
    fmt = request.args.get('format')
    
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for spec in coords:
            page_num = spec.get('page')
            page = pdf.pages[page_num - 1]
            
            bbox = (spec['x1'], spec['y1'], spec['x2'], spec['y2'])
            cropped_page = page.within_bbox(bbox)
            
            custom_columns = spec.get('columns', [])
            
            table_settings = {
                "vertical_strategy": "explicit" if custom_columns else "lines",
                "explicit_vertical_lines": custom_columns if custom_columns else []
            }
            
            extracted = cropped_page.extract_table(table_settings)
            
            if not fmt or fmt == 'json':
                table_data = []
                if extracted:
                    for row in extracted:
                        row_data = []
                        for cell in row:
                            row_data.append({"text": str(cell) if cell is not None else ""})
                        table_data.append(row_data)
                        
                results.append({
                    "extraction_method": "spreadsheet" if custom_columns else "original",
                    "spec_index": len(results),
                    "data": table_data
                })
            else:
                if extracted:
                    results.append(extracted)

    if not fmt:
        return json.dumps(results), 200, {'Content-Type': 'application/json'}
    elif fmt == 'json':
        headers = {
            'Content-Type': 'application/json',
            'Content-Disposition': f'attachment; filename="tabula-{file_id}.json"'
        }
        return json.dumps(results), 200, headers
    elif fmt in ['csv', 'tsv']:
        output = io.StringIO()
        delimiter = '\t' if fmt == 'tsv' else ','
        writer = csv.writer(output, delimiter=delimiter)
        for table in results:
            for row in table:
                writer.writerow([cell if cell is not None else "" for cell in row])
                
        headers = {
            'Content-Type': 'text/csv' if fmt == 'csv' else 'text/tab-separated-values',
            'Content-Disposition': f'attachment; filename="tabula-{file_id}.{fmt}"'
        }
        return output.getvalue(), 200, headers
    else:
        return "Unsupported format", 400

@app.route('/pdfs/<file_id>/tables.json', methods=['GET'])
def auto_detect(file_id):
    return jsonify([])

@app.route('/<path:dummy>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def fallback(dummy):
    print(f"DEBUG - Frontend requested missing API route: {request.method} /{dummy}")
    return jsonify({"status": "error", "message": "Route not implemented in Python prototype"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8080)
