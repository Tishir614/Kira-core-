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
        webbrowser.open(f"http://{a.host if a.host not in ('0.0.0.0', '::') else '127.0.0.1'}:{a.port}")
    loopback = a.host in ("127.0.0.1", "localhost", "::1")
    if not loopback:
        print("ВНИМАНИЕ: сервер открыт в сеть без авторизации — любой в вашей сети сможет управлять моделями и файлами.")
    uvicorn.run(create_app(allow_any_host=not loopback), host=a.host, port=a.port)


main()
