from pathlib import Path

import typer

from reportgen.config import Settings, get_settings
from reportgen.graphs import bar_dedicacion, bar_tmd
from reportgen.logging_cfg import setup_logging
from reportgen.ppt.generate import build_presentation

app = typer.Typer(add_completion=False, help="ReportGen – Graphs & PPT automation")


def _override(settings: Settings, template: str | None, leader: str | None):
    if template:
        settings.template_path = Path(template)
    if leader:
        settings.chapter_leader = leader
    return settings


@app.command()
def graphs(
    leader: str = typer.Option(None, help="Override Chapter Leader"),
    output: str = typer.Option("./figures", help="Output directory for PNGs"),
):
    """Solo genera las gráficas como archivos .png."""
    setup_logging()
    settings = _override(get_settings(), None, leader)
    Path(output).mkdir(parents=True, exist_ok=True)
    bar_tmd(settings, output)
    bar_dedicacion(settings, output)
    typer.echo("🎉 Gráficas generadas.")


@app.command()
def ppt(
    template: str = typer.Option(None, help="Ruta a la plantilla .pptx"),
    leader: str = typer.Option(None, help="Override Chapter Leader"),
    outfile: str = typer.Option(None, help="Nombre del archivo .pptx final"),
):
    """Genera la presentación completa."""
    setup_logging()
    settings = _override(get_settings(), template, leader)
    ppt_path = build_presentation(settings, outfile)
    typer.echo(f"✅ PPT guardado en {ppt_path}")


if __name__ == "__main__":
    app()
