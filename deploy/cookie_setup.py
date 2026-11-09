"""Temporary, capability-protected HTTPS upload receiver behind nginx."""
import email.policy
import hmac
import os
import tempfile
import time
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

MAX_BODY = 1024 * 1024
AUTH_NAMES = {"SID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO"}


class CookieError(ValueError):
    pass


def youtube_cookies(raw, now=None):
    """Keep only unexpired YouTube cookies; never retain other sites' cookies."""
    now = time.time() if now is None else now
    if len(raw) > MAX_BODY:
        raise CookieError("Файл слишком большой.")
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeError:
        raise CookieError("Нужен текстовый файл cookies в формате Netscape.") from None
    if not lines or lines[0].strip() not in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}:
        raise CookieError("Экспортируйте cookies в формате Netscape (.txt).")
    retained, authenticated = [], False
    for line in lines[1:]:
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        fields = line.removeprefix("#HttpOnly_").split("\t")
        if len(fields) != 7:
            raise CookieError("Некорректный формат файла cookies.")
        domain, subdomains, path, secure, expires, name, value = fields
        host = domain.lower().lstrip(".")
        if host != "youtube.com" and not host.endswith(".youtube.com"):
            continue
        if (subdomains not in {"TRUE", "FALSE"} or secure not in {"TRUE", "FALSE"}
                or not path.startswith("/") or not expires.isdigit() or not name
                or any(ord(c) < 32 for c in line if c != "\t")):
            raise CookieError("Некорректные cookies YouTube.")
        if int(expires) and int(expires) <= now:
            continue
        retained.append(line)
        authenticated |= name in AUTH_NAMES and bool(value)
    if not retained or not authenticated:
        raise CookieError("В файле нет активной сессии YouTube. Сначала войдите в аккаунт и повторите экспорт.")
    return ("# Netscape HTTP Cookie File\n" + "\n".join(retained) + "\n").encode()


PAGE = """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Подключение YouTube к боту</title>
<style>body{font:17px/1.6 system-ui,sans-serif;background:#f2f5f7;color:#142332;margin:0;padding:24px}main{max-width:620px;margin:30px auto;background:white;padding:28px;border-radius:24px}h1{font-size:26px;line-height:1.25}li{margin:12px 0}button{border:0;border-radius:14px;padding:14px 20px;background:#176b58;color:white;font:inherit;cursor:pointer}input{display:block;margin:20px 0;max-width:100%}a{color:#176b58}.note{color:#526471;font-size:15px}</style>
<main><h1>Подключение YouTube к боту</h1>
<p>Передайте файл сессии YouTube прямо на сервер бота.</p>
<ol><li>Установите в Chrome расширение <a rel="noreferrer" target="_blank" href="https://chromewebstore.google.com/detail/cclelndahbckbenkjhflpdbgdldlbecc">Get cookies.txt LOCALLY</a>. В настройках расширения включите «Разрешить использование в режиме инкогнито».</li>
<li>Откройте одно окно инкогнито и войдите в YouTube. Для бота лучше использовать отдельный Google-аккаунт.</li>
<li>В той же вкладке откройте <a rel="noreferrer" target="_blank" href="https://www.youtube.com/robots.txt">youtube.com/robots.txt</a> — скопируйте этот адрес в окно инкогнито.</li>
<li>Через расширение экспортируйте cookies только <strong>youtube.com</strong> в формате Netscape (.txt), затем закройте окно инкогнито.</li>
<li>Выберите полученный файл ниже и нажмите «Подключить сессию».</li></ol>
<form method="post" enctype="multipart/form-data"><input type="file" name="cookies" accept=".txt,text/plain" required aria-label="Файл cookies YouTube"><button type="submit">Подключить сессию</button></form>
<p class="note">Ссылка действует ограниченное время и принимает один файл. Файл содержит доступ к сессии: не отправляйте его в чат. Использование аккаунта для скачивания может привести к ограничениям YouTube.</p></main></html>"""


def handler(token, expires, destination, origin):
    expected = "/youtube-bot-setup/" + token + "/"

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass  # Neither capability URLs nor uploaded content belong in logs.

        def respond(self, status, body):
            data = body.encode()
            self.send_response(status)
            for k, v in {
                "Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(data)),
                # Keep Origin on form POSTs while excluding the capability path
                # from all Referer headers. no-referrer makes Chrome send null.
                "Cache-Control": "no-store", "Referrer-Policy": "strict-origin",
                "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
                "Connection": "close",
            }.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def authorize(self):
            if not hmac.compare_digest(urlsplit(self.path).path.encode(), expected.encode()):
                self.respond(404, "Страница не найдена.")
                return False
            if time.time() >= expires:
                self.respond(410, "Срок действия ссылки истёк. Запросите новую ссылку.")
                return False
            return True

        def do_GET(self):
            if self.authorize():
                if destination.exists():
                    self.respond(200, "Файл сессии уже передан. Сообщите в чате: «Готово» — проверим скачивание.")
                else:
                    self.respond(200, PAGE)

        def do_POST(self):
            if not self.authorize():
                return
            if self.headers.get("Origin") != origin:
                self.respond(403, "Откройте форму по выданной ссылке.")
                return
            if destination.exists():
                self.respond(409, "Эта ссылка уже использована.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                content_type = self.headers.get("Content-Type", "")
                if not 0 < length <= MAX_BODY or not content_type.startswith("multipart/form-data;"):
                    raise CookieError("Выберите текстовый файл cookies размером до 1 МБ.")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise CookieError("Файл передан не полностью.")
                message = BytesParser(policy=email.policy.default).parsebytes(
                    b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
                parts = [p for p in message.iter_parts() if p.get_param("name", header="content-disposition") == "cookies"]
                if len(parts) != 1:
                    raise CookieError("Выберите один файл cookies YouTube.")
                cleaned = youtube_cookies(parts[0].get_payload(decode=True) or b"")
            except (CookieError, ValueError, UnicodeError):
                # Error text is fixed; input values and cookie values are never echoed.
                self.respond(400, "Не найден файл активной сессии YouTube в формате Netscape. Вернитесь назад, войдите в YouTube и экспортируйте cookies заново.")
                return
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as f:
                    temporary = Path(f.name)
                    os.chmod(temporary, 0o600)
                    f.write(cleaned)
                os.replace(temporary, destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self.respond(200, "Файл сессии передан на сервер. Сообщите в чате: «Готово» — проверим скачивание.")

    return Handler


if __name__ == "__main__":
    token = os.environ["SETUP_TOKEN"]
    if len(token) < 32:
        raise SystemExit("Invalid setup token")
    destination = Path(os.environ["SETUP_COOKIE_FILE"])
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    HTTPServer(("127.0.0.1", 8794), handler(token, int(os.environ["SETUP_EXPIRES"]), destination,
                                        "https://logic-coin.online")).serve_forever()
