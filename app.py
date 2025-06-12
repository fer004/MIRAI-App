import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
import pydicom
from pydicom.pixel_data_handlers import apply_voi_lut
import matplotlib.pyplot as plt
from werkzeug.security import check_password_hash, generate_password_hash
import requests

# NEW IMPORTS FOR PDF MANIPULATION
from pypdf import PdfWriter, PdfReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter # Standard letter size for new page
from reportlab.lib.enums import TA_CENTER # For text alignment
from io import BytesIO # To handle PDF data in memory without saving temp files for ReportLab

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

UPLOAD_FOLDER = 'dicom_uploads'
PREVIEW_FOLDER = 'static/previews'
ARCHIVES_FOLDER = 'archives' # For uploaded PDFs
REPORTS_FOLDER = 'static/reports' # <--- NEW: Folder for generated reports
ALLOWED_EXTENSIONS = {'dcm', 'dicom'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PREVIEW_FOLDER'] = PREVIEW_FOLDER
app.config['ARCHIVES_FOLDER'] = ARCHIVES_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER # <--- NEW: Add to app config
app.config['MAX_CONTENT_LENGTH'] = 150 * 1024 * 1024  # 150MB

app.secret_key = 'clave_supersecreta' # Change this to a strong, random key in production!

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PREVIEW_FOLDER, exist_ok=True)
os.makedirs(ARCHIVES_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True) # <--- NEW: Create reports folder

# Ensure database exists and tables are created
if not os.path.exists('instance/database.db'):
    with app.app_context():
        db.create_all()
        print("Database created!")

class metadata(db.Model):
    __tablename__ = 'metadata'
    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Integer)
    gender = db.Column(db.Integer)
    medic = db.Column(db.String(20), nullable=False)
    hospital = db.Column(db.String(20), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.now)
    def __repr__(self):
        return '<Paciente %r>' % self.id

class PDFStudy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    study_name = db.Column(db.String(120))
    filename_1 = db.Column(db.String(120))
    filename_2 = db.Column(db.String(120))
    # NEW COLUMN: Add a timestamp for easy retrieval of the most recent study
    upload_date = db.Column(db.DateTime, default=datetime.now)

class medical(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)

class patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_preview(dcm_path, preview_path):
    """Generate a PNG preview from DICOM file"""
    try:
        ds = pydicom.dcmread(dcm_path)
        data = apply_voi_lut(ds.pixel_array, ds)
        data = (data - data.min()) / (data.max() - data.min()) * 255.0
        data = data.astype('uint8')

        plt.figure(figsize=(4, 4), dpi=100)
        plt.imshow(data, cmap=plt.cm.gray)
        plt.axis('off')
        plt.savefig(preview_path, bbox_inches='tight', pad_inches=0)
        plt.close()
        return True
    except Exception as e:
        print(f"Preview generation failed: {str(e)}")
        return False

def extract_dicom_metadata(dcm_path):
    metadata = {
        'PatientName': 'N/A',
        'PatientID': 'N/A',
        'StudyDate': 'N/A',
        'PatientAge': 'N/A',
        'PatientSex': 'N/A',
        'Modality': 'N/A',
        'BodyPartExamined': 'N/A',
        'FileSize': 'N/A'
    }
    try:
        ds = pydicom.dcmread(dcm_path)

        if 'PatientName' in ds and ds.PatientName:
            metadata['PatientName'] = str(ds.PatientName)

        for tag in ['PatientID', 'StudyDate', 'PatientAge', 'PatientSex', 'Modality', 'BodyPartExamined']:
            if tag in ds and ds[tag].value is not None:
                metadata[tag] = str(ds[tag].value)

    except Exception as e:
        print(f"Error extracting metadata from {dcm_path}: {e}")

    try:
        metadata['FileSize'] = f"{os.path.getsize(dcm_path) / (1024 * 1024):.2f} MB"
    except Exception as e:
        print(f"Error getting file size for {dcm_path}: {e}")
        metadata['FileSize'] = 'N/A'

    return metadata

# --- Routes ---

@app.route('/')
def index():
    studies = PDFStudy.query.all()
    return render_template('login.html', studies=studies)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})

    files = request.files.getlist('file')
    uploaded_files = []
    errors = []
    previews = []
    all_metadata = []

    for file in files:
        if file.filename == '':
            errors.append('Empty file name')
            continue

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            dicom_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(dicom_path)

                metadata_for_file = extract_dicom_metadata(dicom_path)
                all_metadata.append(metadata_for_file)

                preview_id = str(uuid.uuid4())
                preview_filename = f"{preview_id}.png"
                preview_path = os.path.join(app.config['PREVIEW_FOLDER'], preview_filename)

                if generate_preview(dicom_path, preview_path):
                    previews.append(preview_filename)
                    uploaded_files.append(filename)
                else:
                    errors.append(f'Preview failed for {filename}')
                    previews.append(None)
            except Exception as e:
                errors.append(f'Failed to save or process {filename}: {str(e)}')
                previews.append(None)

        else:
            errors.append(f'Invalid file type: {file.filename}')

    if len(errors) > 0 and len(uploaded_files) == 0:
        return jsonify({'success': False, 'error': ', '.join(errors)})

    return jsonify({
        'success': True,
        'uploaded_files': uploaded_files,
        'previews': previews,
        'errors': errors,
        'metadata': all_metadata
    })

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    pdf1 = request.files.get('pdf1')
    pdf2 = request.files.get('pdf2')

    if not pdf1 or not pdf2:
        return jsonify({'success': False, 'error': 'Se requieren dos archivos PDF'})

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    study_id = uuid.uuid4().hex[:8]
    study_name = f"Estudio_{timestamp}_{study_id}"

    if pdf1.filename.lower().endswith('.pdf') and pdf2.filename.lower().endswith('.pdf'):
        # Using secure_filename for PDF filenames as well for consistency and security
        filename_1 = secure_filename(f"{study_name}_1.pdf")
        filename_2 = secure_filename(f"{study_name}_2.pdf")

        path_1 = os.path.join(app.config['ARCHIVES_FOLDER'], filename_1)
        path_2 = os.path.join(app.config['ARCHIVES_FOLDER'], filename_2)

        try:
            pdf1.save(path_1)
            pdf2.save(path_2)

            new_pdf = PDFStudy(
                study_name=study_name,
                filename_1=filename_1,
                filename_2=filename_2,
                upload_date=datetime.now() # NEW: Save upload date for easy retrieval
            )
            db.session.add(new_pdf)
            db.session.commit()

            return jsonify({'success': True, 'message': 'Archivos subidos correctamente', 'study_id': new_pdf.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Failed to save PDF files: {str(e)}'})
    else:
        return jsonify({'success': False, 'error': 'Ambos archivos deben ser PDF'})

@app.route('/process_recent_dicoms', methods=['POST'])
def process_recent_dicoms():
    dicom_files_in_folder = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename):
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(full_path):
                dicom_files_in_folder.append((full_path, os.path.getmtime(full_path)))

    dicom_files_in_folder.sort(key=lambda x: x[1], reverse=True)
    files_to_process_paths = [path for path, _ in dicom_files_in_folder[:4]]

    if not files_to_process_paths:
        return jsonify({'success': False, 'error': 'No DICOM files found in the upload folder to process.'})

    target_url = "http://localhost:5000/dicom/files"

    files_payload = []
    for filepath in files_to_process_paths:
        try:
            files_payload.append(('dicom', (os.path.basename(filepath), open(filepath, 'rb'), 'application/dicom')))
        except IOError as e:
            print(f"Error opening file {filepath}: {e}")
            return jsonify({'success': False, 'error': f'Failed to open file {os.path.basename(filepath)} for processing.'})

    try:
        response = requests.post(target_url, files=files_payload, data={'data': '{}'})
        response.raise_for_status()

        result_data = response.json()

        return jsonify({
            'success': True,
            'message': f'Successfully sent {len(files_to_process_paths)} DICOM files to Docker app.',
            'target_response': result_data
        })
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Failed to send files to Docker app or receive valid response: {str(e)}',
            'details': e.response.text if hasattr(e, 'response') else 'No detailed response'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'An unexpected error occurred during processing: {str(e)}'
        })
    finally:
        for _, (filename, file_obj, mime_type) in files_payload:
            if not file_obj.closed:
                file_obj.close()


@app.route('/generate_report_pdf', methods=['POST'])
def generate_report_pdf():
    data = request.get_json()
    if not data or 'percentage' not in data or 'riskMessage' not in data:
        return jsonify({'success': False, 'error': 'Missing percentage or riskMessage in request.'}), 400

    percentage = data['percentage']
    risk_message = data['riskMessage']

    try:
        # 1. Retrieve the most recent PDFStudy entry
        # This assumes the user processes DICOMs and then wants a report using the most recently uploaded PDFs.
        last_pdf_study = PDFStudy.query.order_by(PDFStudy.upload_date.desc()).first()
        if not last_pdf_study:
            return jsonify({'success': False, 'error': 'No PDF studies found to merge. Please upload PDFs first.'}), 404

        pdf1_path = os.path.join(app.config['ARCHIVES_FOLDER'], last_pdf_study.filename_1)
        pdf2_path = os.path.join(app.config['ARCHIVES_FOLDER'], last_pdf_study.filename_2)

        if not os.path.exists(pdf1_path):
            return jsonify({'success': False, 'error': f'Source PDF 1 not found: {last_pdf_study.filename_1}'}), 404
        if not os.path.exists(pdf2_path):
            return jsonify({'success': False, 'error': f'Source PDF 2 not found: {last_pdf_study.filename_2}'}), 404

        # 2. Initialize PDF Merger (pypdf)
        pdf_writer = PdfWriter()

        # 3. Add pages from PDF 1
        with open(pdf1_path, 'rb') as f1:
            pdf1_reader = PdfReader(f1)
            for page_num in range(len(pdf1_reader.pages)):
                pdf_writer.add_page(pdf1_reader.pages[page_num])

        # 4. Add pages from PDF 2
        with open(pdf2_path, 'rb') as f2:
            pdf2_reader = PdfReader(f2)
            for page_num in range(len(pdf2_reader.pages)):
                pdf_writer.add_page(pdf2_reader.pages[page_num])

        # 5. Generate the new page with ReportLab
        # Create an in-memory buffer to build the ReportLab PDF
        buffer = BytesIO()
        # Use letter size for the new page
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Add title
        title_style = styles['h1']
        title_style.alignment = TA_CENTER
        story.append(Paragraph("Reporte de Análisis DICOM", title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Add prediction result
        prediction_style = styles['Normal']
        prediction_style.fontSize = 18
        prediction_style.leading = 22 # Line height
        prediction_style.alignment = TA_CENTER
        story.append(Paragraph(f"Predicción: <font color='blue'><b>{percentage}%</b></font>", prediction_style))
        story.append(Spacer(1, 0.2 * inch))

        # Add risk message
        risk_style = styles['Normal']
        risk_style.fontSize = 24
        risk_style.leading = 30
        risk_style.alignment = TA_CENTER
        risk_color = 'red' if risk_message == 'ALTO RIESGO' else 'green'
        story.append(Paragraph(f"<font color='{risk_color}'><b>{risk_message}</b></font>", risk_style))
        story.append(Spacer(1, 0.5 * inch))

        # Add some explanatory text
        normal_style = styles['Normal']
        normal_style.alignment = TA_CENTER
        story.append(Paragraph("Este informe ha sido generado automáticamente basándose en los resultados del procesamiento de las imágenes DICOM.", normal_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Estudio original: {last_pdf_study.study_name}", normal_style))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Fecha de generación del reporte: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))

        doc.build(story) # Build the ReportLab PDF
        buffer.seek(0) # Rewind the buffer to the beginning

        # Add the ReportLab-generated PDF (from memory) to the main PDF writer
        reportlab_pdf_reader = PdfReader(buffer)
        for page_num in range(len(reportlab_pdf_reader.pages)):
            pdf_writer.add_page(reportlab_pdf_reader.pages[page_num])

        # 6. Save the final merged PDF
        report_filename = f"Reporte_{uuid.uuid4().hex}.pdf" # Unique filename for the report
        report_path = os.path.join(app.config['REPORTS_FOLDER'], report_filename)

        with open(report_path, 'wb') as output_pdf:
            pdf_writer.write(output_pdf)

        # 7. Return the URL to the generated PDF
        report_url = f"/static/reports/{report_filename}"
        return jsonify({'success': True, 'report_url': report_url})

    except Exception as e:
        print(f"Error generating report PDF: {str(e)}")
        return jsonify({'success': False, 'error': f'Error generating report PDF: {str(e)}'}), 500


@app.route('/dicom/files', methods=['POST'])
def receive_dicom_files_internal():
    # This endpoint is designed to simulate your Docker app's behavior if it's
    # also a Flask app. Keep this as is if your Docker app is not a Flask app,
    # as it's just for the client-side `requests.post` call to work.
    if 'dicom' not in request.files:
        return jsonify({'success': False, 'error': 'No dicom file part received by Flask app.'})

    files = request.files.getlist('dicom')
    received_filenames = [file.filename for file in files]

    print(f"Flask app's /dicom/files received {len(received_filenames)} files: {received_filenames}")

    processed_results = [f"Processed {f}" for f in received_filenames]

    return jsonify({
        'success': True,
        'message': f'Internal endpoint successfully received {len(received_filenames)} files.',
        'received_files': received_filenames,
        'processing_results': processed_results
    })


@app.route('/previews/<filename>')
def serve_preview(filename):
    return send_from_directory(app.config['PREVIEW_FOLDER'], filename)

@app.route('/uploads/<filename>')
def serve_dicom(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# NEW: Route to serve generated reports
@app.route('/static/reports/<filename>')
def serve_report(filename):
    return send_from_directory(app.config['REPORTS_FOLDER'], filename)


@app.route('/ver_estudios_pdf')
def ver_estudios_pdf():
    estudios = PDFStudy.query.all()
    return jsonify([
        {
            'id': e.id,
            'nombre_estudio': e.study_name,
            'archivo_1': e.filename_1,
            'archivo_2': e.filename_2,
            'fecha': e.upload_date.strftime("%Y-%m-%d %H:%M:%S") if hasattr(e, 'upload_date') else 'N/A'
        }
        for e in estudios
    ])

@app.route('/log', methods=['GET', 'POST'])
def log():
    if request.method == 'POST':
        nombre = request.form['nombre']
        password = request.form['password']
        rol = request.form['rol']

        conn = sqlite3.connect('instance/database.db')
        c = conn.cursor()

        if rol == 'medical':
            c.execute('SELECT name, password, role FROM medical WHERE name = ?', (nombre,))
        else:
            flash("Rol no válido", "danger")
            conn.close()
            return redirect('/')

        resultado = c.fetchone()
        conn.close()

        if resultado:
            db_name, password_hash, db_rol = resultado
            if check_password_hash(password_hash, password):
                session['role'] = db_rol
                if db_rol == 'medical':
                    return render_template('Mirai.html')

        flash("Usuario o contraseña incorrecta", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return render_template('login.html')

@app.route('/reg', methods=['GET', 'POST'])
def reg():
    if request.method == 'POST':
        nombre = request.form['nombre']
        password = request.form['password']
        rol = request.form['rol']

        hashed_password = generate_password_hash(password)
        conn = sqlite3.connect('instance/database.db')
        c = conn.cursor()

        try:
            if rol == 'patient':
                c.execute('INSERT INTO patient (name, password, role) VALUES (?, ?, ?)',
                          (nombre, hashed_password, rol))
                flash('Paciente registrado exitosamente', 'success')
                conn.commit()
            elif rol == 'medical':
                c.execute('INSERT INTO medical (name, password, role) VALUES (?, ?, ?)',
                          (nombre, hashed_password, rol))
                conn.commit()
                flash(f'Responsable registrado exitosamente.', 'info')
                return redirect('/log')
            else:
                flash('Rol no válido', 'danger')
                return redirect('/reg')
        except sqlite3.Error as e:
            flash(f"Error al registrar: {e}", "danger")
            conn.rollback()
        finally:
            conn.close()

    return render_template('reg.html')


if __name__ == '__main__':
    app.run(debug=True)