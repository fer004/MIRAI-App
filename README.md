# FlaskProject - Mirai App Interface

This project provides an intuitive web interface for interacting with the Mirai deep learning model, designed to assist medical personnel in breast cancer risk prediction based on mammograms. The application facilitates informed decision-making by oncologists using risk data provided by the model. The app is oriented for use by medical personnel.

## Features

* **User Authentication:** Secure access for medical personnel, utilizing an integrated "database.db" for user registration and login. The site requires an access system. This access allows logging in as a doctor, but a separate patient access was not generated, only the architecture for future development.
* **DICOM File Upload:** Capacity to load DICOM files with drag-and-drop functionality.
* **PDF Documentation Upload:** Capability to attach supplementary PDF documents.
* **Metadata Extraction:** Extracts and displays patient and study information from DICOM files. Javascript grants the necessary data to PyDicom for the precise extraction of metadata.
* **DICOM Viewer:** Visualizes the planes of the imported DICOM images.
* **Mirai Model Integration:** Processes DICOMs with the Mirai model to provide risk predictions. The app relies on its communication with the port exposed by the Docker container.
* **Result Display:** Presents "High Risk" or "Low Risk" based on the 5-year risk criterion established by Avendano and associates (2024) for Mexican women. Results are generated as soon as Docker throws the model's decision.
* **PDF Report Generation:** Generates comprehensive PDF reports of the results using PyPDF and ReportLab libraries. Javascript initiates the generation process, providing PyPDF and ReportLab libraries with the data to generate the final results PDF.

## Requirements

* **Python 3.9+**
* **pip** (Python package installer)
* **Docker Desktop** (or a Docker environment running on Linux/WSL)
* **Ark:Mirai Docker Image**

## Getting Started

### 1. Clone the Repository

```bash
git clone [https://github.com/YourGitHubUsername/FlaskProject.git](https://github.com/YourGitHubUsername/FlaskProject.git)
cd FlaskProject
```

### 2. Set up the Python Virtual Environment
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```
### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Ark:Mirai Docker Container

IMPORTANT: For the Mirai App interface to function correctly, you must have the Ark:Mirai Docker image running and exposed on port 5000. This application specifically uses the Ark:Mirai version of the model, which was the criterion used in the validating study for Mexican women.
```bash
docker load -i ark_mirai.tar
docker run -p 5000:5000 --name mirai-ark-model ark-mirai-image-name # Replace 'ark-mirai-image-name' with the actual name of your Ark:Mirai image
```
### 5. Run the Flask Application
```bash
python app.py
```


