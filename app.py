"""FastAPI web app for D&D Character Generator with HTMX frontend."""

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from dnd_generator import (
    SPECIES,
    CLASSES,
    BACKGROUNDS,
    generate_character,
    generate_text_sheet,
    generate_pdf_bytes,
)

app = FastAPI(title="D&D 5e Character Generator")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main character generator form."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "species": SPECIES,
            "classes": CLASSES,
            "backgrounds": BACKGROUNDS,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    name: str = Form(""),
    species: str = Form(...),
    char_class: str = Form(...),
    background: str = Form(...),
):
    """Generate a character and return the result as HTML partial."""
    import random

    if not name:
        name = random.choice(
            ["Aldric", "Brynn", "Caelum", "Dara", "Eldrin", "Fira", "Galen", "Hira", "Ivar", "Jaya"]
        )

    char = generate_character(species, char_class, background, name)
    text_sheet = generate_text_sheet(char)
    safe_name = char.name.lower().replace(" ", "_")

    return templates.TemplateResponse(
        "partials/character_result.html",
        {
            "request": request,
            "char": char,
            "species": species,
            "char_class": char_class,
            "background": background,
            "safe_name": safe_name,
        },
    )


@app.get("/download/pdf/{species}/{char_class}/{background}/{name}")
async def download_pdf(species: str, char_class: str, background: str, name: str):
    """Generate and download a PDF character sheet."""
    char = generate_character(species, char_class, background, name.replace("_", " ").title())
    pdf_bytes = generate_pdf_bytes(char)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}_character.pdf"'},
    )


@app.get("/download/txt/{species}/{char_class}/{background}/{name}")
async def download_txt(species: str, char_class: str, background: str, name: str):
    """Generate and download a text character sheet."""
    char = generate_character(species, char_class, background, name.replace("_", " ").title())
    text_sheet = generate_text_sheet(char)

    return Response(
        content=text_sheet.encode("utf-8"),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{name}_character.txt"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)