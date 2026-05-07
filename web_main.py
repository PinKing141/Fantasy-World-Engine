"""Entry point for the Fantasy Engine web map viewer.

Usage:
    python web_main.py                  # default: localhost:5000
    python web_main.py --port 8080
    python web_main.py --host 0.0.0.0   # share on local network
"""
from __future__ import annotations

import argparse

from fantasy_engine.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fantasy Engine web map viewer")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    parser.add_argument("--width", type=int, default=512, help="Default world width")
    parser.add_argument("--height", type=int, default=320, help="Default world height")
    args = parser.parse_args()

    app = create_app(default_size=(args.width, args.height))
    print(f"Fantasy Engine web viewer running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
