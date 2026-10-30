from models import CertificateExtraction
import os
import uuid
import hashlib
import re
import io
import pymupdf
import pytesseract
import cv2
import numpy as np
from PIL import Image

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    send_from_directory
)

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

from models import db, Certificate


pages = Blueprint("pages", __name__)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

MAX_FILE_SIZE = 10 * 1024 * 1024


def allowed_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def validate_file(file, extension):

    file.stream.seek(0)

    if extension == "pdf":

        signature = file.stream.read(5)

        file.stream.seek(0)

        return signature == b"%PDF-"

    if extension in {"jpg", "jpeg", "png"}:

        try:
            image = Image.open(file.stream)

            expected_format = {
                "jpg": "JPEG",
                "jpeg": "JPEG",
                "png": "PNG"
            }[extension]

            if image.format != expected_format:
                return False

            image.verify()

            file.stream.seek(0)

            return True

        except (UnidentifiedImageError, OSError, ValueError):
            return False

    return False


@pages.route("/upload", methods=["GET", "POST"])
@login_required
def upload():

    if request.method == "POST":

        uploaded_file = request.files.get("certificate")

        if not uploaded_file or not uploaded_file.filename:
            flash("Please select a certificate file.", "danger")
            return redirect(url_for("pages.upload"))

        original_filename = secure_filename(uploaded_file.filename)

        if not original_filename:
            flash("Invalid filename.", "danger")
            return redirect(url_for("pages.upload"))

        if not allowed_file(original_filename):
            flash("Only PDF, PNG, JPG and JPEG files are allowed.", "danger")
            return redirect(url_for("pages.upload"))

        uploaded_file.stream.seek(0, os.SEEK_END)
        file_size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0)

        if file_size == 0:
            flash("The selected file is empty.", "danger")
            return redirect(url_for("pages.upload"))

        if file_size > MAX_FILE_SIZE:
            flash("File size must not exceed 10 MB.", "danger")
            return redirect(url_for("pages.upload"))

        extension = original_filename.rsplit(".", 1)[1].lower()

        if not validate_file(uploaded_file, extension):
            flash("The file content does not match its extension or is invalid.", "danger")
            return redirect(url_for("pages.upload"))

        uploaded_file.stream.seek(0)

        file_content = uploaded_file.read()

        file_hash = hashlib.sha256(file_content).hexdigest()

        uploaded_file.stream.seek(0)

        stored_filename = f"{uuid.uuid4().hex}.{extension}"

        upload_folder = current_app.config["UPLOAD_FOLDER"]

        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(
            upload_folder,
            stored_filename
        )

        uploaded_file.save(file_path)

        certificate = Certificate(
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_type=extension,
            file_size=file_size,
            sha256_hash=file_hash,
            admin_id=current_user.id
        )

        try:
            db.session.add(certificate)
            db.session.commit()

        except Exception:
            db.session.rollback()

            if os.path.exists(file_path):
                os.remove(file_path)

            current_app.logger.exception("Certificate database save failed")
            flash("Could not save certificate. Please try again.", "danger")

            return redirect(url_for("pages.upload"))

        flash("Certificate uploaded successfully!", "success")

        return redirect(url_for("pages.upload"))

    certificates = Certificate.query.filter_by(
        admin_id=current_user.id
    ).order_by(
        Certificate.uploaded_at.desc()
    ).all()

    return render_template(
        "upload.html",
        certificates=certificates
    )


@pages.route("/certificate/preview/<int:certificate_id>")
@login_required
def preview_certificate(certificate_id):

    certificate = Certificate.query.filter_by(
        id=certificate_id,
        admin_id=current_user.id
    ).first_or_404()

    response = send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        certificate.stored_filename,
        as_attachment=False,
        download_name=certificate.original_filename
    )

    response.headers["X-Content-Type-Options"] = "nosniff"

    return response




# ==========================================
# CERTICHAIN OCR ENGINE
# ==========================================

def preprocess_certificate_image(image):
    """
    Improve certificate image quality before sending it to Tesseract.
    """
    image = np.array(image.convert("RGB"))

    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    height, width = image.shape[:2]

    # Enlarge the certificate to improve character recognition.
    image = cv2.resize(
        image,
        (width * 2, height * 2),
        interpolation=cv2.INTER_CUBIC
    )

    # Convert to grayscale.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Reduce image noise.
    denoised = cv2.fastNlMeansDenoising(
        gray, None, 10, 7, 21
    )

    # Improve contrast and separate text from background.
    processed = cv2.threshold(
        denoised,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]

    return processed


def extract_certificate_text(file_path, extension):

    extracted_pages = []

    if extension == "pdf":

        document = pymupdf.open(file_path)

        try:
            for page_number, page in enumerate(document):

                if page_number >= 10:
                    break

                text = page.get_text("text").strip()

                # Use OCR when the PDF page has little embedded text.
                if len(text) < 40:

                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(3, 3),
                        alpha=False
                    )

                    image = Image.open(
                        io.BytesIO(pixmap.tobytes("png"))
                    ).convert("RGB")

                    processed = preprocess_certificate_image(image)

                    text = pytesseract.image_to_string(
                        processed,
                        lang="eng",
                        config="--oem 3 --psm 6"
                    )

                extracted_pages.append(text)

        finally:
            document.close()

    elif extension in {"png", "jpg", "jpeg"}:

        image = Image.open(file_path).convert("RGB")

        processed = preprocess_certificate_image(image)

        text = pytesseract.image_to_string(
            processed,
            lang="eng",
            config="--oem 3 --psm 6"
        )

        extracted_pages.append(text)

    return "\\n".join(extracted_pages).strip()

def find_labeled_value(text, labels):

    for label in labels:

        pattern = (
            r"(?im)^\s*" + label +
            r"\s*[:\-]\s*(.+?)\s*$"
        )

        match = re.search(pattern, text)

        if match:
            return match.group(1).strip()

    return "Not detected"


def extract_certificate_fields(text):

    student_name = find_labeled_value(
        text,
        [
            r"Student\s*Name",
            r"Name\s*of\s*Student",
            r"Candidate\s*Name",
            r"Name\s*of\s*Candidate"
        ]
    )

    institution = find_labeled_value(
        text,
        [
            r"University\s*Name",
            r"College\s*Name",
            r"Institution\s*Name",
            r"Issuing\s*Institution"
        ]
    )

    certificate_number = find_labeled_value(
        text,
        [
            r"Certificate\s*(?:No\.?|Number|ID)",
            r"Registration\s*Number",
            r"Certificate\s*Code"
        ]
    )

    course = find_labeled_value(
        text,
        [
            r"Course\s*Name",
            r"Degree",
            r"Programme",
            r"Program"
        ]
    )

    year_match = re.search(
        r"\b(?:19|20)\d{2}\b",
        text
    )

    graduation_year = (
        year_match.group(0) if year_match else "Not detected"
    )

    date_match = re.search(
        r"(?i)(?:Date\s*of\s*Issue|Issue\s*Date|Date\s*of\s*Award|Issued\s*On)"
        r"\s*[:\-]\s*([^\n]+)",
        text
    )

    issue_date = (
        date_match.group(1).strip()
        if date_match else "Not detected"
    )

    return {
        "student_name": student_name,
        "institution": institution,
        "certificate_number": certificate_number,
        "course": course,
        "graduation_year": graduation_year,
        "issue_date": issue_date
    }


@pages.route("/certificate/extract/<int:certificate_id>")
@login_required
def extract_certificate(certificate_id):

    certificate = Certificate.query.filter_by(
        id=certificate_id,
        admin_id=current_user.id
    ).first_or_404()

    file_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        certificate.stored_filename
    )

    if not os.path.isfile(file_path):
        flash("Certificate file could not be found.", "danger")
        return redirect(url_for("pages.upload"))

    try:

        extracted_text = extract_certificate_text(
            file_path,
            certificate.file_type
        )

        if not extracted_text:
            flash("No readable text detected.", "warning")
            return redirect(url_for("pages.upload"))

        fields = extract_certificate_fields(extracted_text)

        result = CertificateExtraction.query.filter_by(
            certificate_id=certificate.id
        ).first()

        if result is None:
            result = CertificateExtraction(
                certificate_id=certificate.id
            )
            db.session.add(result)

        result.extracted_text = extracted_text
        result.student_name = fields["student_name"]
        result.institution = fields["institution"]
        result.certificate_number = fields["certificate_number"]
        result.course = fields["course"]
        result.graduation_year = fields["graduation_year"]
        result.issue_date = fields["issue_date"]

        db.session.commit()

        return render_template(
            "extraction.html",
            certificate=certificate,
            result=result
        )

    except Exception:

        db.session.rollback()

        current_app.logger.exception("OCR processing failed")

        flash("OCR processing failed. Check the application logs.", "danger")

        return redirect(url_for("pages.upload"))



@pages.route("/verification")
@login_required
def verification():
    return render_template(
        "module.html",
        page_title="Certificate Verification",
        page_subtitle="Verify the authenticity of academic certificates.",
        page_icon="bi-patch-check",
        description="Check certificate fingerprints and blockchain registration records.",
        status="Ready for implementation"
    )


@pages.route("/history")
@login_required
def history():
    return render_template(
        "module.html",
        page_title="Certificate History",
        page_subtitle="Review previously processed certificates.",
        page_icon="bi-clock-history",
        description="View certificate uploads, AI analysis results and verification activity.",
        status="Ready for implementation"
    )


@pages.route("/settings")
@login_required
def settings():
    return render_template(
        "module.html",
        page_title="Admin Settings",
        page_subtitle="Manage your administrator account.",
        page_icon="bi-gear",
        description="Account settings and security options will be available here.",
        status="Ready for implementation"
    )
