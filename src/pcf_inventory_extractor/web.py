"""FastAPI web UI + CSV download."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pcf_inventory_extractor.inventory import ExtractConfig, default_output_name
from pcf_inventory_extractor.run import run_extraction

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "templates"
STATIC = REPO_ROOT / "static"
_TEMPL: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _TEMPL
    if _TEMPL is None:
        _TEMPL = Jinja2Templates(directory=str(TEMPLATES))
    return _TEMPL


def create_app() -> FastAPI:
    app = FastAPI(
        title="pcf-inventory-extractor",
        description="CF v3 org metadata to CSV (same as extract-pcf-inventory).",
    )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Any:
        return get_templates().TemplateResponse(
            "index.html",
            {
                "request": request,
                "default_hint": "Leave blank to use "
                f"{default_output_name('<org>')} on the server working directory",
            },
        )

    @app.get("/help", response_class=HTMLResponse)
    def help_page(request: Request) -> Any:
        return get_templates().TemplateResponse("help.html", {"request": request})

    @app.post("/extract")
    def do_extract(
        org_name: str = Form(..., min_length=1, description="CF org name"),
        output_path: str = Form(""),
        debug: str | None = Form(default=None),
    ) -> FileResponse:
        is_debug = (debug or "").strip().lower() in ("on", "true", "1", "yes")
        o = (output_path or "").strip()
        if o:
            out = Path(o).expanduser()
        else:
            out = Path(default_output_name(org_name))
        cfg = ExtractConfig(
            org_name=org_name.strip(),
            output_path=out.resolve(),
            debug=is_debug,
        )
        run_extraction(cfg)
        p = out.resolve()
        return FileResponse(
            path=str(p),
            media_type="text/csv; charset=utf-8",
            filename=p.name,
        )

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    a = parser.parse_args()
    app = create_app()
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")
