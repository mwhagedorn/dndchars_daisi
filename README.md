# D&D 5e Character Generator

A character generator for Dungeons & Dragons 5th Edition (2024 rules) that creates complete level 1 characters with filled PDF character sheets.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

- **2024 PHB Rules**: Updated species, classes, backgrounds, and origin feats
- **10 Species**: Aasimar, Dragonborn, Dwarf, Elf, Gnome, Goliath, Halfling, Human, Orc, Tiefling
- **12 Classes**: All core classes with proper ability score assignments
- **16 Backgrounds**: Each with ability bonuses and origin feats
- **PDF Generation**: Fills the official D&D 5e character sheet PDF
- **Web Interface**: HTMX-powered UI with a dark fantasy theme
- **CLI Support**: Run from the command line for quick character generation

## Quick Start

### Web App

```bash
# Clone and setup
cd dndchars
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run
uvicorn app:app --reload
```

Visit http://localhost:8000

### Command Line

```bash
python dnd_generator.py
```

Follow the prompts to select species, class, and background. Character sheets are saved to the `characters/` directory.

## Project Structure

```
dndchars/
├── app.py                 # FastAPI web application
├── dnd_generator.py       # Core character generation logic
├── requirements.txt       # Python dependencies
├── Procfile              # Heroku deployment config
├── templates/
│   ├── base.html         # Base layout with Tailwind CSS
│   ├── index.html        # Character creation form
│   └── partials/
│       └── character_result.html  # HTMX partial for results
├── templates/            # PDF template directory
│   └── character_sheet.pdf
└── characters/           # Generated character output
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Character creation form |
| POST | `/generate` | Generate character (HTMX partial) |
| GET | `/download/pdf/{species}/{class}/{bg}/{name}` | Download PDF sheet |
| GET | `/download/txt/{species}/{class}/{bg}/{name}` | Download text sheet |

## Dependencies

- **fastapi** - Web framework
- **uvicorn** - ASGI server
- **pypdf** - PDF manipulation
- **python-multipart** - Form handling
- **jinja2** - HTML templating

## Deployment (Heroku)

```bash
heroku create your-app-name
git push heroku main
```

The included `Procfile` configures the web dyno automatically.

## Usage Examples

### Programmatic Usage

```python
from dnd_generator import generate_character, generate_text_sheet, generate_pdf_bytes

# Generate a character
char = generate_character(
    species_key="elf",
    class_key="wizard",
    bg_key="sage",
    name="Elara"
)

# Get text representation
text = generate_text_sheet(char)
print(text)

# Get PDF as bytes (for web responses)
pdf_bytes = generate_pdf_bytes(char)

# Or write PDF to file
from dnd_generator import fill_pdf
fill_pdf(char, "elara_character.pdf")
```

### Character Object

The `Character` dataclass contains:

- `name`, `species`, `char_class`, `background`
- `abilities` - Dict of STR, DEX, CON, INT, WIS, CHA
- `skill_profs`, `saving_throw_profs` - Sets of proficiencies
- `hp`, `ac`, `equipment`
- `personality_trait`, `ideal`, `bond`, `flaw`
- `origin_feat` - From 2024 background rules

## PDF Template

Place the official D&D 5e fillable character sheet PDF at `templates/character_sheet.pdf`. The generator fills all standard fields including:

- Basic info (name, class, level, background, species)
- Ability scores and modifiers
- Saving throws with proficiency checkboxes
- Skills with proficiency checkboxes
- Combat stats (AC, HP, speed, initiative)
- Equipment, features, and personality

## License

MIT
