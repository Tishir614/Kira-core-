import argparse
import webbrowser

import uvicorn

from .server import create_app


def main() -> None:
    p = argparse.ArgumentParser(prog="kira_local")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()
    if not a.no_browser:
        webbrowser.open(f"http://{a.host}:{a.port}")
    uvicorn.run(create_app(), host=a.host, port=a.port)


main()
