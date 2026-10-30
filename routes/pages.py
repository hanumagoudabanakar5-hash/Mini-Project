from flask import Blueprint, render_template
from flask_login import login_required

pages = Blueprint("pages", __name__)


@pages.route("/upload")
@login_required
def upload():
    return render_template(
        "module.html",
        page_title="Upload Certificate",
        page_subtitle="Upload and manage academic certificates.",
        page_icon="bi-cloud-upload",
        description="Upload PDF or image certificates for AI-powered analysis and blockchain verification.",
        status="Ready for implementation"
    )


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
