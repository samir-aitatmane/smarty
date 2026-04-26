"""
routers/chat.py — Endpoint principal de conversation avec Smarty
Gère :
- Messages texte
- Upload de fichiers (CV, documents, images avec OCR)
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from services.llm import chat_with_smarty, extract_profile_from_cv
from services.knowledge import build_llm_context
import logging
import io

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Modèles ───────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str
    user_id: str = "anonymous"
    detected_country_code: str = ""
    detected_country_name: str = ""

class ChatResponse(BaseModel):
    reply: str
    session_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Endpoint principal de conversation."""
    try:
        context = ""
        if req.detected_country_code or req.detected_country_name:
            context = build_llm_context(
                req.detected_country_code or None,
                req.detected_country_name or None,
            )
        messages = [{"role": m.role, "content": m.content} for m in req.messages]
        reply = await chat_with_smarty(messages=messages, context=context)
        return ChatResponse(reply=reply, session_id=req.session_id)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur chat : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
):
    """
    Upload universel — documents ET images (OCR gratuit).
    Images → Tesseract OCR extrait le texte → LLaMA analyse
    Documents → extraction texte directe → LLaMA analyse
    """
    try:
        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 10 MB)")

        content_type = file.content_type or ""
        filename = file.filename or ""

        # ── IMAGE → OCR ────────────────────────────────────────────────────
        if content_type in ALLOWED_IMAGES or filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            logger.info(f"Image reçue : {filename} — lancement OCR")

            extracted_text = extract_text_from_image(content)

            if not extracted_text.strip():
                extracted_text = "Image reçue mais le texte n'a pas pu être extrait (image floue ou sans texte)."

            # Envoyer le texte extrait à LLaMA pour analyse
            prompt = f"""L'utilisateur a uploadé une image. Voici le texte extrait par OCR :

--- TEXTE EXTRAIT ---
{extracted_text}
--- FIN DU TEXTE ---

Analyse ce contenu et extrait les informations utiles pour le voyage :
- Si c'est un CV : nom, nationalité, compétences, expérience internationale, langues
- Si c'est un passeport : nom, nationalité, date d'expiration
- Si c'est une carte de vaccination : vaccins, dates
- Si c'est autre chose : décris ce que tu vois et les infos utiles

Réponds de façon structurée et propose de continuer la conversation pour aider l'utilisateur."""

            profile_data = await extract_profile_from_cv(extracted_text)

            return {
                "success": True,
                "type": "image",
                "session_id": session_id,
                "filename": filename,
                "extracted_text": extracted_text[:500],  # preview
                "profile_extracted": profile_data,
                "llm_prompt": prompt,
                "message": "Image analysée avec succès"
            }

        # ── DOCUMENT ───────────────────────────────────────────────────────
        elif content_type == "application/pdf" or filename.endswith(".pdf"):
            cv_text = await extract_text_from_pdf(content)
            if not cv_text.strip():
                raise HTTPException(status_code=400, detail="PDF vide ou illisible")
            profile_data = await extract_profile_from_cv(cv_text)
            return {
                "success": True,
                "type": "document",
                "session_id": session_id,
                "filename": filename,
                "profile_extracted": profile_data,
                "message": "Document analysé avec succès"
            }

        else:
            # TXT, DOC, DOCX
            cv_text = content.decode("utf-8", errors="ignore")
            if not cv_text.strip():
                raise HTTPException(status_code=400, detail="Fichier vide ou illisible")
            profile_data = await extract_profile_from_cv(cv_text)
            return {
                "success": True,
                "type": "document",
                "session_id": session_id,
                "filename": filename,
                "profile_extracted": profile_data,
                "message": "Document analysé avec succès"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur upload : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'analyse du fichier")


# Alias pour compatibilité
@router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...), session_id: str = Form(...)):
    return await upload_file(file=file, session_id=session_id)


# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def extract_text_from_image(content: bytes) -> str:
    """
    Extrait le texte d'une image avec Tesseract OCR.
    Gratuit, tourne en local et sur Azure Container Apps.
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(content))

        # Convertir en RGB si nécessaire
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # OCR multilingue — français + anglais + arabe
        text = pytesseract.image_to_string(
            image,
            lang="fra+eng+ara",
            config="--psm 3"  # mode auto-détection de mise en page
        )

        logger.info(f"OCR terminé — {len(text)} caractères extraits")
        return text.strip()

    except ImportError:
        logger.error("pytesseract non installé — pip install pytesseract Pillow")
        return ""
    except Exception as e:
        logger.error(f"Erreur OCR : {e}")
        return ""


async def extract_text_from_pdf(content: bytes) -> str:
    """Extrait le texte d'un PDF."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Erreur extraction PDF : {e}")
        return ""