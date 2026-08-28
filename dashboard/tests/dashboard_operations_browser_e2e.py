from __future__ import annotations

import pathlib
import ssl
import subprocess
import tempfile
import threading

from dashboard_live_browser_e2e import (
    DASHBOARD_DIR,
    FixtureHandler,
    ThreadingServer,
    create_certificate,
    find_chrome,
)


PROBE = """
<script>
(() => {
  let attempts = 0;
  const timer = setInterval(() => {
    attempts += 1;
    const buttons = [...document.querySelectorAll('#lane-gates button[data-lane]')];
    const initialHeading = document.querySelector('#gate-detail h3');
    if (buttons.length === 3 && initialHeading) {
      clearInterval(timer);
      const waiting = buttons.find((button) => button.dataset.lane === 'waiting');
      document.body.dataset.restoredBeforeKeyboard = String(initialHeading.textContent.includes('判断待ち'));
      document.body.dataset.gatesNamed = String(buttons.every((button) => button.type === 'button' && button.textContent.trim().length > 0));
      waiting.focus();
      waiting.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
      setTimeout(() => {
        document.body.dataset.keyboardLane = new URL(window.location.href).searchParams.get('lane') || '';
        document.body.dataset.keyboardFocus = document.activeElement?.dataset?.lane || '';
        document.body.dataset.keyboardDetail = document.querySelector('#gate-detail h3')?.textContent || '';
        document.body.dataset.noHorizontalOverflow = String(document.documentElement.scrollWidth <= window.innerWidth);
      }, 100);
      return;
    }
    if (attempts >= 80) {
      clearInterval(timer);
      document.body.dataset.operationsProbe = 'timeout';
    }
  }, 50);
})();
</script>
"""


class OperationsHandler(FixtureHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API
        path = self.path.split("?", 1)[0]
        if path == "/operations-test.html":
            html = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
            body = html.replace("</body>", f"{PROBE}</body>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    OperationsHandler.live_requests = 0
    with tempfile.TemporaryDirectory() as tmp, ThreadingServer(("127.0.0.1", 0), OperationsHandler) as server:
        cert_path, key_path = create_certificate(pathlib.Path(tmp))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    find_chrome(),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--no-proxy-server",
                    "--ignore-certificate-errors",
                    "--window-size=390,844",
                    "--virtual-time-budget=5000",
                    "--dump-dom",
                    f"https://localhost:{port}/operations-test.html?lane=waiting",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    dom = result.stdout
    checks = {
        "URL lane restored before keyboard": 'data-restored-before-keyboard="true"' in dom,
        "gate buttons have names": 'data-gates-named="true"' in dom,
        "ArrowRight updates URL": 'data-keyboard-lane="failed"' in dom,
        "ArrowRight moves focus": 'data-keyboard-focus="failed"' in dom,
        "ArrowRight changes detail": 'data-keyboard-detail="失敗・要確認 (1)"' in dom,
        "mobile width has no horizontal overflow": 'data-no-horizontal-overflow="true"' in dom,
        "probe did not time out": 'data-operations-probe="timeout"' not in dom,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise SystemExit("operations browser E2E failed: " + ", ".join(failures))
    print("operations browser E2E: URL restore + keyboard + mobile width PASS")


if __name__ == "__main__":
    main()
