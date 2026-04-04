from paper.app.cli import build_parser, dispatch_command, known_commands, main

__all__ = [
    "build_parser",
    "dispatch_command",
    "known_commands",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
