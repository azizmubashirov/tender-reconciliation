"""Uploaded files -> normalized documents (archives unpacked, everything readable by the model)."""

import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.storage import get_bytes, put_bytes
from app.models import Document, Package
from app.pipeline.convert import expand, normalize

log = logging.getLogger(__name__)


def storage_prefix(package: Package) -> str:
    return f"projects/{package.project_id}/packages/{package.id}"


def _normalize(package: Package, doc: Document, data: bytes) -> None:
    result = normalize(doc.filename, data)
    if result.pdf is not None:
        doc.pdf_key = f"{storage_prefix(package)}/normalized/{uuid.uuid4().hex}.pdf"
        put_bytes(doc.pdf_key, result.pdf)
    doc.text_content = result.text
    doc.page_texts = result.page_texts
    doc.page_count = result.page_count
    doc.status = "ready"
    doc.error = None


def normalize_documents(db: Session, package: Package) -> None:
    for doc in list(package.documents):
        if doc.status != "new":
            continue
        try:
            data = get_bytes(doc.storage_key)
            inner = expand(doc.filename, data)
            if len(inner) == 1 and inner[0][0] == doc.filename:
                _normalize(package, doc, data)
            else:
                # An archive becomes one document per file inside it.
                for name, content in inner:
                    child = Document(
                        package_id=package.id,
                        filename=name,
                        storage_key=f"{storage_prefix(package)}/original/"
                        f"{uuid.uuid4().hex}{Path(name).suffix.lower()}",
                    )
                    put_bytes(child.storage_key, content)
                    package.documents.append(child)
                    try:
                        _normalize(package, child, content)
                    except Exception as exc:
                        child.status, child.error = "failed", str(exc)
                db.delete(doc)
        except Exception as exc:
            log.exception("document %s failed", doc.id)
            doc.status, doc.error = "failed", str(exc)
        db.commit()
