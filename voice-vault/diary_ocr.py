"""Read a diary page photo on this Mac with Apple's Vision framework.

Nothing leaves the Mac. Language correction is off, so Vision does not swap in
"likelier" words; what comes back is a first draft that Chris checks against his
own pen on the harvest page before any line is kept.
"""
from __future__ import annotations

from pathlib import Path


def ocr_lines(photo: Path) -> list[str]:
    try:
        import Vision  # type: ignore  (pyobjc-framework-Vision, installed by install.sh)
        from Foundation import NSURL  # type: ignore
    except ImportError as e:
        raise RuntimeError("Apple Vision reader not installed (run install.sh); the photo was not sent anywhere") from e
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    # The URL handler reads the photo's own orientation, so sideways phone shots read right.
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(photo)), None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision could not read {photo.name}: {err}")
    found = []
    for obs in req.results() or []:
        cands = obs.topCandidates_(1)
        if not cands:
            continue
        box = obs.boundingBox()  # 0..1, origin at bottom left
        top = 1 - (box.origin.y + box.size.height)
        found.append((round(top, 2), box.origin.x, str(cands[0].string())))
    found.sort()
    return [t for _, _, t in found if t.strip()]
