"""单容器静态服务器：托管 Vue 构建产物 + 反向代理 /api/* 到 FastAPI。

替代 Node.js server.mjs，仅依赖 Python 标准库（http.server + urllib），
从而允许镜像移除 ~117MB 的 node 二进制。

功能等价：
- 静态文件服务（带 MIME 类型）
- SPA history fallback（未知路径回退到 index.html）
- /api/* 反向代理到 API_INTERNAL_URL（默认 http://127.0.0.1:8010）
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent / "dist"
INDEX_FILE = ROOT / "index.html"
PORT = int(os.environ.get("PORT", "3110"))
API_BASE = os.environ.get("API_INTERNAL_URL", "http://127.0.0.1:8010").rstrip("/")
PROXY_TIMEOUT_SECONDS = 180


class StaticHandler(BaseHTTPRequestHandler):
    server_version = "StockMasterStatic/1.0"

    def do_GET(self) -> None:  # noqa: N802
        self._serve()

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(head_only=True)

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def do_PUT(self) -> None:  # noqa: N802
        self._proxy()

    def do_PATCH(self) -> None:  # noqa: N802
        self._proxy()

    def do_DELETE(self) -> None:  # noqa: N802
        self._proxy()

    # ------------------------------------------------------------------

    def _serve(self, head_only: bool = False) -> None:
        try:
            path = urlsplit(self.path).path
            if path.startswith("/api/"):
                self._proxy()
                return
            decoded = urllib.parse.unquote(path)
            candidate = (ROOT / decoded.lstrip("/")).resolve()
            if candidate == ROOT or not str(candidate).startswith(str(ROOT.resolve())):
                candidate = INDEX_FILE
            if candidate.is_file():
                file_path = candidate
            else:
                file_path = INDEX_FILE
            self._send_file(file_path, head_only=head_only)
        except Exception as exc:  # pragma: no cover - 防御性兜底
            self._send_json(502, {"detail": str(exc)})

    def _send_file(self, file_path: Path, head_only: bool = False) -> None:
        content_type, _encoding = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"
        if content_type == "text/plain":
            content_type = "text/html; charset=utf-8" if file_path.name == "index.html" else content_type
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.end_headers()
        if head_only:
            return
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _proxy(self) -> None:
        try:
            body = None
            content_length = self.headers.get("Content-Length")
            if content_length and int(content_length) > 0:
                body = self.rfile.read(int(content_length))
            target = f"{API_BASE}{self.path}"
            request = urllib.request.Request(
                target,
                data=body,
                method=self.command,
                headers={k: v for k, v in self.headers.items() if k.lower() not in {"host", "content-length"}},
            )
            with urllib.request.urlopen(request, timeout=PROXY_TIMEOUT_SECONDS) as response:
                payload = response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in {"transfer-encoding", "connection"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            self._send_json(exc.code, {"detail": exc.reason})
        except Exception as exc:  # pragma: no cover - 代理上游不可达
            self._send_json(502, {"detail": f"upstream unavailable: {type(exc).__name__}"})

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        sys.stderr.write(f"[static] {self.address_string()} {format % args}\n")


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StaticHandler)
    print(f"StockMaster static server listening on {PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
