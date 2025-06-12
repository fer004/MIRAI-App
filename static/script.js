document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const uploadStatus = document.getElementById('uploadStatus');
    const processRecentDicomButton = document.getElementById('processRecentDicomButton');
    const dockerResultsDisplay = document.getElementById('dockerResults');

    // References for metadata display spans
    const metaPatientName = document.getElementById('metaPatientName');
    const metaPatientID = document.getElementById('metaPatientID');
    const metaStudyDate = document.getElementById('metaStudyDate');
    const metaPatientAge = document.getElementById('metaPatientAge');
    const metaPatientSex = document.getElementById('metaPatientSex');
    const metaModality = document.getElementById('metaModality');
    const metaBodyPart = document.getElementById('metaBodyPart');
    const metaFileSize = document.getElementById('metaFileSize');

    // PDF Upload Form Handling ---
    const pdfUploadForm = document.getElementById('pdfUploadForm');
    const pdfUploadStatus = document.getElementById('pdfUploadStatus');
    const pdf1Input = document.getElementById('pdf1Input'); // Get reference to PDF 1 input
    const pdf2Input = document.getElementById('pdf2Input'); // Get reference to PDF 2 input

    if (pdfUploadForm) {
        pdfUploadForm.addEventListener('submit', async (event) => {
            event.preventDefault(); // <--- THIS IS THE KEY: Prevents the default form submission (page reload)

            pdfUploadStatus.textContent = 'Subiendo PDFs...';
            pdfUploadStatus.style.color = '#366699'; // Indicating processing

            const formData = new FormData(pdfUploadForm); // Automatically collects all form fields, including files

            try {
                const response = await fetch('/upload_pdf', {
                    method: 'POST',
                    body: formData // FormData automatically sets the correct Content-Type header
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`Server responded with status ${response.status}: ${errorText}`);
                }

                const data = await response.json(); // Parse the JSON response from your Flask backend

                if (data.success) {
                    pdfUploadStatus.textContent = data.message;
                    pdfUploadStatus.style.color = 'green';
                    // Clear the file inputs after successful upload for a cleaner UI
                    if (pdf1Input) pdf1Input.value = '';
                    if (pdf2Input) pdf2Input.value = '';
                } else {
                    pdfUploadStatus.textContent = `Error: ${data.error || 'Error desconocido al subir PDFs'}`;
                    pdfUploadStatus.style.color = 'red';
                }
            } catch (error) {
                pdfUploadStatus.textContent = `Error de red o servidor: ${error.message}`;
                pdfUploadStatus.style.color = 'red';
                console.error('PDF upload fetch error:', error);
            }
        });
    }

    // --- Drag and Drop Event Listeners for file upload ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    dropZone.addEventListener('drop', handleDrop, false);
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => handleFiles(e.target.files));

    // --- Event Listener for the "Process DICOMs" button ---
    if (processRecentDicomButton) {
        processRecentDicomButton.addEventListener('click', handleProcessRecentDicoms);
    }

    // --- Helper Functions for Drag and Drop ---
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropZone.classList.add('drop-zone--over');
    }

    function unhighlight() {
        dropZone.classList.remove('drop-zone--over');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        handleFiles(dt.files);
    }

    // Update metadata display (no changes here from previous step)
    function updateMetadataDisplay(metadata) {
        metaPatientName.textContent = 'N/A';
        metaPatientID.textContent = 'N/A';
        metaStudyDate.textContent = 'N/A';
        metaPatientAge.textContent = 'N/A';
        metaPatientSex.textContent = 'N/A';
        metaModality.textContent = 'N/A';
        metaBodyPart.textContent = 'N/A';
        metaFileSize.textContent = 'N/A';

        if (metadata) {
            metaPatientName.textContent = metadata.PatientName || 'N/A';
            metaPatientID.textContent = metadata.PatientID || 'N/A';
            metaStudyDate.textContent = metadata.StudyDate || 'N/A';
            metaPatientAge.textContent = metadata.PatientAge || 'N/A';
            metaPatientSex.textContent = metadata.PatientSex || 'N/A';
            metaModality.textContent = metadata.Modality || 'N/A';
            metaBodyPart.textContent = metadata.BodyPartExamined || 'N/A';
            metaFileSize.textContent = metadata.FileSize || 'N/A';
        }
    }

    // --- Core Function for File Upload (no changes here from previous step) ---
    function handleFiles(files) {
        const formData = new FormData();
        for (const file of files) {
            formData.append('file', file);
        }

        uploadStatus.textContent = 'Uploading...';
        uploadStatus.style.color = '#366699';
        dockerResultsDisplay.innerHTML = '';
        updateMetadataDisplay(null);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => { throw new Error(text) });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                uploadStatus.textContent = `Uploaded ${data.uploaded_files.length} file(s)`;
                uploadStatus.style.color = 'green';
                displayPreviews(data.previews, data.uploaded_files);

                if (data.metadata && data.metadata.length > 0) {
                    updateMetadataDisplay(data.metadata[0]);
                } else {
                    updateMetadataDisplay(null);
                }

            } else {
                uploadStatus.textContent = `Error: ${data.error || 'Unknown upload error'}`;
                uploadStatus.style.color = 'red';
                updateMetadataDisplay(null);
            }
        })
        .catch(error => {
            uploadStatus.textContent = `Network Error or invalid response: ${error.message}`;
            uploadStatus.style.color = 'red';
            console.error('Upload fetch error:', error);
            updateMetadataDisplay(null);
        });
    }

    // --- Core Function for Displaying Previews (no changes here) ---
    function displayPreviews(previews, filenames) {
        const planes = document.querySelectorAll('.planes .plane');
        if (!planes.length) {
            console.warn("No .plane elements found in DOM");
            return;
        }

        planes.forEach(p => p.innerHTML = '');

        previews.forEach((preview, index) => {
            if (index >= planes.length) return;

            if (preview) {
                const img = document.createElement('img');
                img.src = `/previews/${preview}`;
                img.className = 'preview-image';
                planes[index].appendChild(img);
            } else {
                const errorMsg = document.createElement('div');
                errorMsg.textContent = 'Preview unavailable';
                errorMsg.style.color = 'red';
                planes[index].appendChild(errorMsg);
            }
        });
    }

    // --- Separate Function for Processing Recent DICOMs ---
    async function handleProcessRecentDicoms() {
        uploadStatus.textContent = 'Processing recent DICOMs...';
        uploadStatus.style.color = '#366699';
        dockerResultsDisplay.innerHTML = '';

        let percentage = null; // Store percentage to pass to PDF generation
        let riskMessage = null; // Store risk message to pass to PDF generation

        try {
            const response = await fetch('/process_recent_dicoms', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server responded with status ${response.status}: ${errorText}`);
            }

            const data = await response.json();

            if (data.success && data.target_response && data.target_response.data && data.target_response.data.predictions) {
                uploadStatus.textContent = `Processing successful!`;
                uploadStatus.style.color = 'green';

                const predictions = data.target_response.data.predictions;

                if (predictions.length >= 5) {
                    const fifthPrediction = predictions[4];
                    percentage = (fifthPrediction * 100).toFixed(2); // Assign to outer variable

                    if (parseFloat(percentage) >= 2.9) {
                        riskMessage = 'ALTO RIESGO'; // Assign to outer variable
                    } else {
                        riskMessage = 'BAJO RIESGO'; // Assign to outer variable
                    }

                    const resultHtml = `
                        <p style="font-size: 1.2em; font-weight: bold; margin-bottom: 5px;">
                            Predicción: ${percentage}%
                        </p>
                        <p style="font-size: 1.5em; font-weight: bold; color: ${riskMessage === 'ALTO RIESGO' ? 'red' : 'green'};">
                            ${riskMessage}
                        </p>
                        <p style="font-size: 0.9em; color: #666; margin-top: 10px;">
                            (Raw value: ${fifthPrediction})
                        </p>
                    `;
                    dockerResultsDisplay.innerHTML = resultHtml;

                    // NEW: Trigger PDF generation after successful DICOM processing and display
                    await generateReportPDF(percentage, riskMessage);

                } else {
                    dockerResultsDisplay.innerHTML = `<p style="color: orange;">Not enough predictions returned to display the fifth value.</p>`;
                    console.warn("API response did not contain enough predictions:", data.target_response);
                }

            } else {
                uploadStatus.textContent = `Error: ${data.error || data.message || 'Unknown processing error'}`;
                uploadStatus.style.color = 'red';
                const pre = document.createElement('pre');
                pre.textContent = JSON.stringify(data, null, 2);
                dockerResultsDisplay.appendChild(pre);
            }
        } catch (error) {
            uploadStatus.textContent = `Network Error or processing failure: ${error.message}`;
            uploadStatus.style.color = 'red';
            const pre = document.createElement('pre');
            pre.textContent = `Failed to connect or process: ${error.message}`;
            dockerResultsDisplay.appendChild(pre);
            console.error('Process recent DICOMs fetch error:', error);
        }
    }

    // NEW FUNCTION: Client-side logic to trigger PDF generation
    async function generateReportPDF(percentage, riskMessage) {
        if (percentage === null || riskMessage === null) {
            console.error("Cannot generate PDF: percentage or riskMessage is missing.");
            return;
        }

        try {
            uploadStatus.textContent = 'Generating PDF report...';
            uploadStatus.style.color = '#366699';

            const response = await fetch('/generate_report_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ percentage: percentage, riskMessage: riskMessage })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server responded with status ${response.status}: ${errorText}`);
            }

            const data = await response.json();

            if (data.success && data.report_url) {
                uploadStatus.textContent = 'PDF report generated successfully!';
                uploadStatus.style.color = 'green';
                window.open(data.report_url, '_blank'); // Open PDF in a new tab
            } else {
                uploadStatus.textContent = `PDF generation error: ${data.error || 'Unknown error'}`;
                uploadStatus.style.color = 'red';
            }

        } catch (error) {
            uploadStatus.textContent = `Error generating PDF: ${error.message}`;
            uploadStatus.style.color = 'red';
            console.error('PDF generation fetch error:', error);
        }
    }
});