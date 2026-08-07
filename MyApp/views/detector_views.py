from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import os
import tempfile

from MyApp.utils import detector

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.txt'}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

def _allowed_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

@login_required
@require_POST
def detect_file(request):
    if not request.user.is_staff:
        return HttpResponseForbidden('Only teachers can use this endpoint.')
    uploaded = request.FILES.get('file')
    if not uploaded:
        return HttpResponseBadRequest('No file uploaded.')
    if uploaded.size > MAX_UPLOAD_SIZE:
        return HttpResponseBadRequest('File exceeds maximum size of 50 MB.')
    if not _allowed_file(uploaded.name):
        return HttpResponseBadRequest('Unsupported file type.')
    # Save to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded.name)[1]) as tmp:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        result = detector.predict(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return JsonResponse(result)
