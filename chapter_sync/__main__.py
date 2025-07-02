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
    sub.add_parser("gui", help="Launch GUI")

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
        gui.main()


if __name__ == "__main__":
    main()
