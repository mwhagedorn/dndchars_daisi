"""FastAPI web app for D&D Character Generator with HTMX frontend."""

import logging
import re
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Form, Request

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dndchars")
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dnd_generator import (
    SPECIES,
    CLASSES,
    BACKGROUNDS,
    generate_character,
    generate_text_sheet,
    generate_pdf_bytes,
    Character,
    render_dnd_character_prompt,
    Background,
)


def serialize_character(char: Character) -> dict:
    """Serialize a Character to a dict for session storage."""
    return {
        "name": char.name,
        "species_key": next(
            k for k, v in SPECIES.items() if v.name == char.species.name
        ),
        "class_key": next(
            k for k, v in CLASSES.items() if v.name == char.char_class.name
        ),
        "background_key": next(
            k for k, v in BACKGROUNDS.items() if v.name == char.background.name
        ),
        "level": char.level,
        "abilities": char.abilities,
        "skill_profs": list(char.skill_profs),
        "saving_throw_profs": list(char.saving_throw_profs),
        "hp": char.hp,
        "ac": char.ac,
        "equipment": char.equipment,
        "personality_trait": char.personality_trait,
        "ideal": char.ideal,
        "bond": char.bond,
        "flaw": char.flaw,
        "origin_feat": char.origin_feat,
        "appearance": char.appearance,
        "backstory": char.background.story,
        "allies_and_organizations": char.allies_and_organizations,
        "commonly_says": char.commonly_says,
    }


def deserialize_character(data: dict) -> Character:
    """Deserialize a dict back into a Character."""
    from copy import deepcopy

    species = SPECIES[data["species_key"]]
    char_class = CLASSES[data["class_key"]]
    background = deepcopy(BACKGROUNDS[data["background_key"]])
    background.story = data.get("backstory", "")

    return Character(
        name=data["name"],
        species=species,
        char_class=char_class,
        background=background,
        level=data["level"],
        abilities=data["abilities"],
        skill_profs=set(data["skill_profs"]),
        saving_throw_profs=set(data["saving_throw_profs"]),
        hp=data["hp"],
        ac=data["ac"],
        equipment=data["equipment"],
        personality_trait=data["personality_trait"],
        ideal=data["ideal"],
        bond=data["bond"],
        flaw=data["flaw"],
        origin_feat=data["origin_feat"],
        appearance=data.get("appearance", ""),
        allies_and_organizations=data.get("allies_and_organizations", ""),
        commonly_says=data.get("commonly_says", ""),
    )


import asyncio
import time
from contextlib import asynccontextmanager
from config import get_settings
from daisi import DaisiClient
from daisi.clients.auth import AuthClient
from daisi.config import DaisiConfig
from daisi.exceptions import DaisiError
from protos.v1.models.InferenceModels_pb2 import InferenceResponseTypes, ThinkBasic

_cleanup_task: asyncio.Task | None = None


async def _periodic_daisi_cleanup():
    """Background task that sweeps expired DAISI sessions every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        try:
            _sweep_expired_daisi_sessions()
        except Exception as e:
            logger.error(f"Error in periodic DAISI cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown lifecycle."""
    global _cleanup_task
    logger.info("Starting DAISI cleanup background task...")
    _cleanup_task = asyncio.create_task(_periodic_daisi_cleanup())
    yield
    # Shutdown: cancel task and cleanup all sessions
    logger.info("Shutting down DAISI cleanup task...")
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    # Cleanup any remaining sessions
    for sid in list(_daisi_sessions.keys()):
        _cleanup_daisi_entry(sid)
    logger.info("All DAISI sessions cleaned up")


app = FastAPI(title="D&D 5e Character Generator", lifespan=lifespan)

# Server-side character cache keyed by session-scoped tokens
import secrets
from datetime import datetime, timedelta

_character_cache: dict[str, dict] = {}
CACHE_TTL_MINUTES = 15


def generate_char_token() -> str:
    """Generate a unique token for character storage."""
    return secrets.token_urlsafe(16)


def get_session_id(request) -> str:
    """Get or create a persistent session identifier."""
    # Use existing session cookie value as identifier
    # This is set on previous requests, so SSE will have it
    if "_session_id" not in request.session:
        request.session["_session_id"] = secrets.token_urlsafe(16)
    return request.session["_session_id"]


def make_cache_key(session_id: str, token: str) -> str:
    """Create a cache key scoped to session."""
    return f"{session_id}:{token}"


settings = get_settings()
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=15 * 60,  # 15 minutes
)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main character generator form."""
    # Ensure session ID exists on first page load
    # This way the cookie is set before /generate is called
    get_session_id(request)

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
    """Generate basic character and return HTML with SSE connection for LLM data."""
    import random

    logger.info(
        f"POST /generate - species={species}, class={char_class}, background={background}, name={name or '(random)'}"
    )

    if not name:
        name = random.choice(
            [
                "Aldric",
                "Brynn",
                "Caelum",
                "Dara",
                "Eldrin",
                "Fira",
                "Galen",
                "Hira",
                "Ivar",
                "Jaya",
                "Philgo",
                "Tassit",
                "Wilberd the Silent",
                "Krago",
                "Sho-Rembo",
                "Feggener",
                "Drebb",
            ]
        )
        logger.debug(f"Random name selected: {name}")

    char = generate_character(species, char_class, background, name)
    logger.info(f"Character generated: {char.name}")

    safe_name = char.name.lower().replace(" ", "_")
    char_token = generate_char_token()
    session_id = get_session_id(request)
    cache_key = make_cache_key(session_id, char_token)
    logger.info(f"safe_name: {safe_name}, token: {char_token}, session: {session_id}")

    # Store basic character data in server-side cache scoped to session
    char_cache_data = serialize_character(char)
    char_cache_data["_species"] = species
    char_cache_data["_char_class"] = char_class
    char_cache_data["_background"] = background
    char_cache_data["_safe_name"] = safe_name
    _character_cache[cache_key] = char_cache_data
    logger.info(f"Stored character in cache with key: {cache_key}")

    return templates.TemplateResponse(
        "partials/character_result.html",
        {
            "request": request,
            "char": char,
            "species": species,
            "char_class": char_class,
            "background": background,
            "safe_name": safe_name,
            "char_token": char_token,
            "show_thinking": True,
        },
    )


@app.get("/stream-supplemental/{token}")
async def stream_supplemental(request: Request, token: str):
    """SSE endpoint that streams LLM progress and returns personality HTML when complete."""
    import queue

    session_id = get_session_id(request)
    cache_key = make_cache_key(session_id, token)

    async def event_generator():
        logger.info(
            f"SSE stream started for token: {token}, session: {session_id}, cache_key: {cache_key}"
        )

        # Get stored character data from server-side cache (scoped to session)
        char_data = _character_cache.get(cache_key)
        if not char_data:
            logger.error(f"No character data found for cache_key: {cache_key}")
            yield f"event: personality\ndata: <div>Error: Character not found</div>\n\n"
            return

        char = deserialize_character(char_data)

        try:
            # Queue for retry status updates from worker thread
            retry_queue: queue.Queue = queue.Queue()

            # Start LLM processing in background
            loop = asyncio.get_event_loop()

            # Process supplemental data (this is the slow LLM call)
            def do_llm_work():
                process_supplemental_data(request, char, retry_callback=retry_queue.put)
                return char

            # Run LLM in thread pool to not block
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = loop.run_in_executor(pool, do_llm_work)

                # Map attempt number to d20 value (countdown from 20)
                def attempt_to_d20(attempt: int) -> int:
                    return max(1, 21 - attempt)

                # Send pings and retry updates while waiting
                while not future.done():
                    # Check for retry updates
                    try:
                        while True:
                            attempt, _ = retry_queue.get_nowait()
                            d20_val = attempt_to_d20(attempt)
                            yield f"event: retry\ndata: {d20_val}\n\n"
                            logger.debug(f"SSE: Sent retry update {attempt} -> d20={d20_val}")
                    except queue.Empty:
                        pass

                    yield ": ping\n\n"
                    await asyncio.sleep(1)

                # Drain any remaining retry updates after completion
                try:
                    while True:
                        attempt, _ = retry_queue.get_nowait()
                        d20_val = attempt_to_d20(attempt)
                        yield f"event: retry\ndata: {d20_val}\n\n"
                        logger.debug(f"SSE: Sent final retry update {attempt} -> d20={d20_val}")
                except queue.Empty:
                    pass

                # Get result
                char = await future

            # Update cache with LLM-augmented character
            updated_data = serialize_character(char)
            updated_data["_species"] = char_data.get("_species")
            updated_data["_char_class"] = char_data.get("_char_class")
            updated_data["_background"] = char_data.get("_background")
            updated_data["_safe_name"] = char_data.get("_safe_name")
            updated_data["_token"] = token
            _character_cache[cache_key] = updated_data
            logger.info(
                f"SSE: Character augmented with LLM data, cache_key: {cache_key}"
            )

            # Render final personality HTML
            personality_html = templates.get_template(
                "partials/personality_complete.html"
            ).render(
                char=char,
                request=request,
            )

            # Render download buttons
            download_html = templates.get_template(
                "partials/download_buttons_ready.html"
            ).render(
                char_token=token,
            )

            # Send events with HTML (escape newlines for SSE)
            # Downloads first, then personality (which replaces the SSE container)
            escaped_personality = personality_html.replace("\n", "")
            escaped_download = download_html.replace("\n", "")
            yield f"event: downloads\ndata: {escaped_download}\n\n"
            yield f"event: personality\ndata: {escaped_personality}\n\n"
            logger.info(f"SSE stream complete for token: {token}")

        except Exception as e:
            logger.error(f"SSE error for token {token}: {e}", exc_info=True)
            # Render download buttons for error state
            error_download_html = templates.get_template(
                "partials/download_buttons_ready.html"
            ).render(char_token=token).replace("\n", "")
            # Send downloads event FIRST (before personality replaces the SSE container)
            yield f"event: downloads\ndata: {error_download_html}\n\n"
            # Small delay to ensure downloads event is processed
            await asyncio.sleep(0.1)
            yield f'event: personality\ndata: <div class="text-red-500">Error loading personality data</div>\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/download/pdf/{token}")
async def download_pdf(request: Request, token: str):
    """Download a PDF character sheet from cache."""
    session_id = get_session_id(request)
    cache_key = make_cache_key(session_id, token)
    logger.debug(f"Download PDF: looking for {cache_key}, cache has {len(_character_cache)} entries: {list(_character_cache.keys())}")
    char_data = _character_cache.get(cache_key)

    # Fallback: try token-only lookup if session-scoped key not found
    # (handles race conditions with session cookies)
    if not char_data:
        for key, data in list(_character_cache.items()):
            if key.endswith(f":{token}"):
                char_data = data
                logger.warning(f"Download PDF: session mismatch, found via token fallback")
                break

    if not char_data:
        logger.error(f"No character data in cache for key: {cache_key}, cache keys: {list(_character_cache.keys())}")
        return Response(content="Character not found", status_code=404)

    char = deserialize_character(char_data)
    safe_name = char_data.get("_safe_name", "character")
    pdf_bytes = generate_pdf_bytes(char)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_character.pdf"'
        },
    )


@app.get("/download/txt/{token}")
async def download_txt(request: Request, token: str):
    """Download a text character sheet from cache."""
    session_id = get_session_id(request)
    cache_key = make_cache_key(session_id, token)
    char_data = _character_cache.get(cache_key)

    # Fallback: try token-only lookup if session-scoped key not found
    # (handles race conditions with session cookies)
    if not char_data:
        for key, data in list(_character_cache.items()):
            if key.endswith(f":{token}"):
                char_data = data
                logger.warning(f"Download TXT: session mismatch, found via token fallback")
                break

    if not char_data:
        logger.error(f"No character data in cache for key: {cache_key}")
        return Response(content="Character not found", status_code=404)

    char = deserialize_character(char_data)
    safe_name = char_data.get("_safe_name", "character")
    text_sheet = generate_text_sheet(char)

    return Response(
        content=text_sheet.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_character.txt"'
        },
    )


_cached_client_key: str | None = None
_client_key_timestamp: float | None = None
CLIENT_KEY_TTL_SECONDS: int = 300  # 5 minutes

# Server-side DAISI session tracking for proper cleanup
# Structure: { http_session_id: { "client": DaisiClient, "daisi_session_id": str,
#              "inference_id": str|None, "created_at": float, "in_use": bool } }
_daisi_sessions: dict[str, dict] = {}
DAISI_SESSION_TTL_SECONDS: int = 300  # 5 minutes


def _cleanup_daisi_entry(http_session_id: str) -> None:
    """Close and remove a DAISI session entry."""
    entry = _daisi_sessions.pop(http_session_id, None)
    if not entry:
        return

    logger.info(f"Cleaning up DAISI session for http_session: {http_session_id}")
    try:
        client: DaisiClient = entry.get("client")
        if client and entry.get("inference_id"):
            client.inference.close_inference(
                session_id=entry.get("daisi_session_id"),
                inference_id=entry.get("inference_id"),
            )
            logger.debug(f"Closed inference: {entry.get('inference_id')}")
        if client:
            client.close()
            logger.debug("Closed DaisiClient")
    except Exception as e:
        logger.warning(f"Error during DAISI cleanup: {e}")


def _sweep_expired_daisi_sessions() -> int:
    """Close expired DAISI sessions that are not in use. Returns count cleaned."""
    now = time.time()
    expired = [
        sid
        for sid, entry in _daisi_sessions.items()
        if not entry.get("in_use")
        and (now - entry.get("created_at", 0)) > DAISI_SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _cleanup_daisi_entry(sid)
    if expired:
        logger.info(f"Swept {len(expired)} expired DAISI sessions")
    return len(expired)


def get_client_key(force_refresh: bool = False) -> str:
    """Exchange secret key for client key, caching with TTL."""
    global _cached_client_key, _client_key_timestamp

    now = time.time()
    key_expired = (
        _client_key_timestamp is not None
        and (now - _client_key_timestamp) > CLIENT_KEY_TTL_SECONDS
    )

    if force_refresh or _cached_client_key is None or key_expired:
        if key_expired:
            logger.info("Client key expired, refreshing...")
        else:
            logger.info("Exchanging secret key for client key...")

        config = DaisiConfig()
        logger.debug(
            f"DaisiConfig: orc_address={config.orc_address}, orc_port={config.orc_port}"
        )
        auth_client = AuthClient(config)
        try:
            client_key, owner_id = auth_client.create_client_key(
                secret_key=settings.DAISI_SECRET_KEY
            )
            _cached_client_key = client_key
            _client_key_timestamp = now
            logger.info(f"Auth successful. Owner ID: {owner_id}")
        finally:
            auth_client.close()
    return _cached_client_key


def get_daisi_client(force_refresh: bool = False) -> DaisiClient:
    logger.debug("Creating DaisiClient...")
    return DaisiClient(client_key=get_client_key(force_refresh=force_refresh))


def get_or_create_daisi_session(
    request: Request, force_refresh: bool = False
) -> tuple[str, DaisiClient]:
    """Get existing Daisi session from server-side cache or create a new one.

    Returns tuple of (daisi_session_id, client).
    """
    http_session_id = get_session_id(request)

    # Check for existing cached session
    if http_session_id in _daisi_sessions and not force_refresh:
        entry = _daisi_sessions[http_session_id]
        age = time.time() - entry.get("created_at", 0)

        if age <= DAISI_SESSION_TTL_SECONDS:
            logger.debug(f"Reusing cached DAISI session: {entry['daisi_session_id']}")
            return entry["daisi_session_id"], entry["client"]
        else:
            # Expired but not swept yet - clean it up now
            logger.info(f"DAISI session expired (age={age:.0f}s), cleaning up...")
            _cleanup_daisi_entry(http_session_id)

    # Create new session
    daisi = get_daisi_client(force_refresh=force_refresh)

    logger.info("Creating new Daisi session...")
    try:
        session_id, host, move_to_orc = daisi.session.create()
    except DaisiError as e:
        logger.error(f"Daisi session create failed: {e}", exc_info=True)
        if "401" in str(e) and not force_refresh:
            logger.warning("Got 401 on session create, refreshing client key...")
            daisi.close()
            return get_or_create_daisi_session(request, force_refresh=True)
        daisi.close()
        raise
    logger.info(f"Session created: {session_id}")
    if host:
        logger.debug(f"Host: {host.Name} ({host.Region})")

    # Connect with retry logic
    for attempt in range(3):
        try:
            logger.debug(f"Connecting to session (attempt {attempt + 1})...")
            connected_id, has_capacity, _ = daisi.session.connect(session_id)
            logger.info(f"Connected: {connected_id}, capacity: {has_capacity}")
            break
        except DaisiError as e:
            logger.warning(f"Connect attempt {attempt + 1} failed: {e}", exc_info=True)
            if attempt < 2:
                time.sleep(0.5)
            else:
                daisi.close()
                raise

    # Store in server-side cache
    _daisi_sessions[http_session_id] = {
        "client": daisi,
        "daisi_session_id": session_id,
        "inference_id": None,
        "created_at": time.time(),
        "in_use": False,
    }

    return session_id, daisi


def create_inference(
    request: Request, daisi: DaisiClient, session_id: str
) -> str:
    """Create a fresh inference for each request. Returns inference_id."""
    http_session_id = get_session_id(request)
    entry = _daisi_sessions.get(http_session_id)

    # Always create new inference (reusing causes empty responses)
    logger.info("Creating new inference...")
    daisi.inference.session_id = session_id

    # Create inference with retry logic
    for attempt in range(3):
        try:
            logger.debug(f"Creating inference (attempt {attempt + 1})...")
            _, inference_id = daisi.inference.create(
                initialization_prompt="You are a helpful assistant that generates D&D character details. Always respond with valid JSON.",
                think_level=ThinkBasic,
            )
            logger.info(f"Inference created: {inference_id}")
            # Store in cache for cleanup tracking
            if entry:
                entry["inference_id"] = inference_id
            return inference_id
        except DaisiError as e:
            logger.warning(
                f"Inference create attempt {attempt + 1} failed: {e}", exc_info=True
            )
            if attempt < 2:
                time.sleep(0.5)
            else:
                raise
    return ""  # unreachable but satisfies type checker


def clear_daisi_session(request: Request):
    """Clear and cleanup DAISI session for this HTTP session."""
    http_session_id = get_session_id(request)
    logger.info(f"Clearing DAISI session for http_session: {http_session_id}")
    _cleanup_daisi_entry(http_session_id)


def call_llm_agent(request: Request, prompt_text: str) -> str:
    """Call the LLM agent and return the collected response text."""
    logger.info("call_llm_agent invoked")
    logger.debug(f"Prompt length: {len(prompt_text)} chars")
    try:
        return _send_inference_request(request, prompt_text)
    except DaisiError as e:
        # Session or inference may be stale, clear and retry once
        logger.warning(f"First attempt failed ({e}), clearing session and retrying...")
        clear_daisi_session(request)
        return _send_inference_request(request, prompt_text)


def _send_inference_request(request: Request, prompt_text: str) -> str:
    """Internal: send inference request without retry logic."""
    http_session_id = get_session_id(request)
    session_id, daisi = get_or_create_daisi_session(request)
    create_inference(request, daisi, session_id)

    # Mark session as in use to prevent cleanup during inference
    entry = _daisi_sessions.get(http_session_id)
    if entry:
        entry["in_use"] = True

    logger.info("Sending inference request...")
    logger.debug(f"Prompt: {prompt_text[:200]}...")
    response_text = ""
    try:
        for response in daisi.inference.send(
            text=prompt_text,
            temperature=0.7,
            max_tokens=4000,
        ):
            if response.Type == InferenceResponseTypes.InferenceText:
                response_text += response.Content
                logger.debug(f"Received chunk: {len(response.Content)} chars")
            elif response.Type == InferenceResponseTypes.InferenceError:
                logger.error(f"Inference error: {response.Content}")
                raise DaisiError(f"Inference error: {response.Content}")
    finally:
        # Clear in_use flag when done (success or failure)
        if entry:
            entry["in_use"] = False

    logger.info(f"Inference complete. Response length: {len(response_text)} chars")
    logger.debug(f"Response: {response_text[:500]}...")
    return response_text


from typing import Callable, Optional


def process_supplemental_data(
    request: Request,
    char: Character,
    max_retries: int = 3,
    retry_callback: Optional[Callable] = None,
):
    """Process LLM supplemental data with retries.

    Args:
        retry_callback: Optional callback called with (attempt, max_retries) on each attempt.
    """
    logger.info(f"Processing supplemental data for {char.name}...")
    prompt_text = render_dnd_character_prompt(
        name=char.name,
        char_class=char.char_class.name,
        background=char.background.name,
        race=char.species.name,
        abilities=char.abilities,
    )

    for attempt in range(max_retries):
        attempt_num = attempt + 1
        logger.debug(f"Calling LLM agent (attempt {attempt_num}/{max_retries})...")

        # Notify caller of current attempt
        if retry_callback:
            retry_callback((attempt_num, max_retries))

        # Clear session to force fresh connection on retry
        if attempt > 0:
            clear_daisi_session(request)

        json_new_values = call_llm_agent(request, prompt_text)
        logger.debug(
            f"LLM response: {json_new_values[:800] if json_new_values else '(empty)'}..."
        )

        supplemental_data = parse_prompt_return_values(json_new_values)
        logger.debug(f"Parsed supplemental data keys: {list(supplemental_data.keys())}")

        # Check if we got valid data (at least background_story)
        if supplemental_data.get("background_story"):
            enhance_character(char, supplemental_data)
            logger.info(f"Character enhanced with supplemental data")
            return

        logger.warning(
            f"LLM response truncated or invalid (attempt {attempt_num}/{max_retries})"
        )

    # All retries failed, enhance with whatever we have
    logger.error(f"All {max_retries} LLM attempts failed, using partial data")
    enhance_character(char, supplemental_data)
    # char.background.story
    # char.personality_trait
    # char.ideal
    # char.bond
    # char.flaw

    return (
        char.abilities,
        char.skill_profs,
        char.saving_throw_profs,
        char.background.story,
        char.personality_trait,
        char.ideal,
        char.bond,
        char.flaw,
    )


def extract_json_from_response(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code fences."""
    import re

    # Strip <response>...</response> wrapper if present
    text = re.sub(r"^<response>\s*", "", text)
    text = re.sub(r"\s*</response>$", "", text)

    logger.debug(f"extract_json_from_response input: {text[:300]}...")

    # Try to extract from ```json ... ``` or ``` ... ``` blocks (closed)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        extracted = match.group(1).strip()
        logger.debug(f"Extracted from closed code fence: {extracted[:200]}...")
        return extracted

    # Handle unclosed code fence (truncated response)
    match = re.search(r"```(?:json)?\s*([\s\S]*)", text)
    if match:
        extracted = match.group(1).strip()
        logger.debug(f"Extracted from unclosed code fence: {extracted[:200]}...")
        return extracted

    # Try to find raw JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        extracted = match.group(0)
        logger.debug(f"Extracted raw JSON: {extracted[:200]}...")
        return extracted

    logger.warning(f"No JSON found in response")
    return text


def sanitize_json_text(text: str) -> str:
    """Normalize and sanitize an extracted JSON string so json.loads is more likely to succeed.

    - Strip BOM and surrounding code-fence backticks.
    - Replace curly/smart quotes and ellipsis with ASCII equivalents.
    - Escape control chars U+0000..U+001F as \\uXXXX.
    - If possible, trim to the outermost {...} object.
    """
    # Strip BOM and surrounding whitespace
    text = text.lstrip("\ufeff").strip()

    # Remove leading/trailing code-fence remnants like ```json or ``` or ``
    text = re.sub(r"^`{1,3}\s*(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*`{1,3}\s*$", "", text)

    # Normalize common fancy punctuation to ASCII
    trans = {
        0x2018: "'",  # ‘
        0x2019: "'",  # ’
        0x201C: '"',  # “
        0x201D: '"',  # ”
        0x2026: "...",# …
        0x2013: "-",  # –
        0x2014: "-",  # —
    }
    text = text.translate(trans)

    # Escape control characters (keep printable whitespace inside strings by escaping; safe for json.loads)
    text = re.sub(r'[\x00-\x1f]', lambda m: "\\u%04x" % ord(m.group(0)), text)

    # If there's a clear outer JSON object, trim to it
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    return text

def parse_prompt_return_values(prompt_text: str) -> defaultdict[str, str]:
    """Parse JSON `prompt_text` and populate a defaultdict[str].

    - Tries normal json.loads on sanitized text.
    - On parse error, falls back to regex extraction of common string keys so
      presence of `background_story` still counts as success.
    """
    import json
    import re

    result: defaultdict[str, str] = defaultdict(str)
    cleaned_text = extract_json_from_response(prompt_text)
    sanitized = sanitize_json_text(cleaned_text)
    try:
        data = json.loads(sanitized)
    except Exception as e:
        logger.error(f"JSON parse failed: {e}")
        logger.error(f"Attempted to parse: {cleaned_text}")
        # Fallback: try to extract common string fields with regex (handles slightly-broken JSON)
        def _extract_str_key(text: str, key: str) -> str:
            # Try double-quoted JSON strings first
            m = re.search(rf'"{re.escape(key)}"\s*:\s*("(?:\\.|[^"\\])*")', text)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    return m.group(1).strip('"')
            # Try single-quoted fallback (some LLM output uses smart/single quotes)
            m2 = re.search(rf"'{re.escape(key)}'\s*:\s*('(\\.|[^'\\])*')", text)
            if m2:
                return m2.group(1).strip("'")
            # Try a loose capture (unquoted key or malformed)
            m3 = re.search(rf'{re.escape(key)}\s*:\s*("(?:\\.|[^"\\])*"|' + r"'(?:\\.|[^'\\])*')", text)
            if m3:
                val = m3.group(1)
                return val.strip('"').strip("'")
            return ""

        keys = [
            "background_story",
            "personality_trait",
            "personality_traits",
            "ideal",
            "bond",
            "flaw",
            "allies_and_organizations",
            "appearance",
            "commonly_says",
        ]
        for k in keys:
            result[k] = _extract_str_key(cleaned_text, k)
        # If we found a JSON-like object elsewhere, try to coerce it to _value
        if not any(result.values()):
            # attempt to salvage full JSON object text as raw string
            obj_match = re.search(r"\{[\s\S]*\}", cleaned_text)
            if obj_match:
                result["_value"] = obj_match.group(0)
        return result

    # If parsed successfully
    if not isinstance(data, dict):
        result["_value"] = json.dumps(data) if not isinstance(data, str) else data
        return result

    for key, value in data.items():
        if isinstance(value, str):
            result[key] = value
        elif value is None:
            result[key] = ""
        else:
            try:
                result[key] = (
                    str(value)
                    if not isinstance(value, (dict, list))
                    else json.dumps(value)
                )
            except Exception:
                result[key] = ""

    return result


def enhance_character(char: Character, override_values: dict[str, str]):
    override_background_story(char, override_values)
    override_personality_traits(char, override_values)
    override_background_ideals(char, override_values)
    override_background_bond(char, override_values)
    override_background_flaw(char, override_values)
    override_allies_and_organizations(char, override_values)
    override_appearance(char, override_values)
    override_commonly_says(char, override_values)


def override_allies_and_organizations(char: Character, prompt_values):
    if prompt_values["allies_and_organizations"] != "":
        char.allies_and_organizations = prompt_values["allies_and_organizations"]


def override_appearance(char: Character, prompt_values):
    if prompt_values["appearance"] != "":
        char.appearance = prompt_values["appearance"]


def override_commonly_says(char: Character, prompt_values):
    if prompt_values["commonly_says"] != "":
        char.commonly_says = prompt_values["commonly_says"]


def override_background_story(char: Character, prompt_values):
    if prompt_values["background_story"] != "":
        char.background.story = prompt_values["background_story"]


def override_personality_traits(char: Character, prompt_values):
    if prompt_values["personality_traits"] != "":
        char.personality_trait = prompt_values["personality_traits"]


def override_background_ideals(char: Character, prompt_values):
    if prompt_values["ideal"] != "":
        char.ideal = prompt_values["ideal"]


def override_background_bond(char: Character, prompt_values):
    if prompt_values["bond"] != "":
        char.bond = prompt_values["bond"]


def override_background_flaw(char: Character, prompt_values):
    if prompt_values["flaw"] != "":
        char.flaw = prompt_values["flaw"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
