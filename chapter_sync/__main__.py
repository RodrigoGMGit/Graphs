import argparse
import logging

from chapter_sync import graphs, gui, presentation


def main(argv=None):
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("matplotlib.category").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(
        prog="chaptersync", description="ChapterSync tools"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_graphs = sub.add_parser("graphs", help="Generate graphs")
    p_graphs.add_argument("--root")
    p_graphs.add_argument("--rev", nargs="?", const=True, default=None)
    p_graphs.add_argument("--dr", nargs="?", const=True, default=None)
    p_graphs.add_argument("--m", nargs="?", const=True, default=None)
    p_graphs.add_argument("--tmd", nargs="?", const=True, default=None)

    sub.add_parser("ppt", help="Generate presentation")
    p_gui = sub.add_parser("gui", help="Launch GUI")
    p_gui.add_argument(
        "--ui",
        choices=["qt", "dpg"],
        default="qt",
        help="Selecciona la interfaz gráfica (qt = PySide6 [default], dpg = DearPyGUI [legacy])",
    )

    args = parser.parse_args(argv)

    if args.cmd == "graphs":
        g_args = [f"--root={args.root}"] if args.root else []
        if args.rev is not None:
            g_args.append("--rev" if args.rev is True else f"--rev={args.rev}")
        if args.dr is not None:
            g_args.append("--dr" if args.dr is True else f"--dr={args.dr}")
        if args.m is not None:
            g_args.append("--m" if args.m is True else f"--m={args.m}")
        if args.tmd is not None:
            g_args.append("--tmd" if args.tmd is True else f"--tmd={args.tmd}")
        graphs.main(g_args)
    elif args.cmd == "ppt":
        presentation.main()
    elif args.cmd == "gui":
        if args.ui == "dpg":
            gui.main()
        else:
            try:
                import PySide6  # Check if PySide6 is available
            except ImportError:
                raise SystemExit(
                    "PySide6 no está instalado. Ejecuta 'pip install -e .[qt]' "
                    "o 'pip install PySide6' antes de lanzar la interfaz Qt."
                )
            
            try:
                from chapter_sync.gui_qt import main as qt_main
                qt_main()
            except Exception as exc:  # pragma: no cover - runtime dependency
                import traceback
                raise SystemExit(
                    f"Error al cargar la interfaz Qt: {exc}\n"
                    f"Traceback:\n{traceback.format_exc()}"
                ) from exc


if __name__ == "__main__":
    main()
