"""
HTML report generator.

generate_html_report(df, analysis_result, project_name, mode) → str

Renders the Jinja2 template in reporting/templates/report.html.
mode = "analyst"   (default) — full detail
mode = "executive"           — KPIs + narrative + top 3 insights only
"""
from __future__ import annotations

import pathlib

import jinja2
import pandas as pd

from .context import build_context

_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(["html"]),
)


def generate_html_report(
    df: pd.DataFrame,
    analysis_result: dict,
    project_name: str = "Dataset Analysis",
    mode: str = "analyst",
) -> str:
    template = _ENV.get_template("report.html")
    ctx = build_context(df, analysis_result, project_name, mode=mode)
    return template.render(**ctx)
