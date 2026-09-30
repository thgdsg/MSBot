from __future__ import annotations

import http.client
import ipaddress
import json
import ast
import operator
import socket
import ssl
import time
from decimal import Decimal, DecimalException
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, urlencode


_CALCULATOR_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


def calculator(expression):
    """Evaluate a small arithmetic expression without Python eval/side effects."""
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 256:
        raise ValueError("Expressao vazia ou longa demais.")
    try:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 64:
            raise ValueError("Expressao complexa demais.")

        def bounded(value):
            if not value.is_finite() or (value and abs(value.adjusted()) > 500):
                raise ValueError("Numero fora do intervalo permitido.")
            return value

        def evaluate(node):
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = Decimal(str(node.value))
                return bounded(value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = evaluate(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp):
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Pow):
                    if right != right.to_integral_value() or abs(right) > 100:
                        raise ValueError("O expoente deve ser um inteiro entre -100 e 100.")
                    return bounded(left ** int(right))
                operation = _CALCULATOR_OPERATORS.get(type(node.op))
                if operation is None:
                    raise ValueError("Operador nao permitido.")
                return bounded(operation(left, right))
            raise ValueError("Use apenas numeros, parenteses e operadores + - * / // % **.")

        result = evaluate(tree)
        if not result.is_finite() or abs(result.adjusted()) > 500:
            raise ValueError("Resultado fora do intervalo permitido.")
        rendered = format(result.normalize(), "f")
        if len(rendered) > 512:
            raise ValueError("Resultado longo demais.")
        return {"expression": expression, "result": rendered}
    except (SyntaxError, DecimalException, ZeroDivisionError, OverflowError) as error:
        raise ValueError("Expressao aritmetica invalida.") from error


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, text):
        if not self.hidden and text.strip():
            self.parts.append(text.strip())


def public_address(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Somente enderecos publicos sao permitidos.")
    return addresses[0]


def download(url):
    """Pin the validated IP; validate every redirect and bound downloaded bytes."""
    deadline = time.monotonic() + 18
    for _ in range(4):
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("URL HTTP/HTTPS publica obrigatoria.")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError("Porta nao permitida.")
        host = parsed.hostname.encode("idna").decode("ascii")
        address = public_address(host, port)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        connection = http.client.HTTPConnection(host, port, timeout=min(8, remaining))
        raw = socket.socket(address[0], socket.SOCK_STREAM)
        try:
            raw.settimeout(min(8, remaining))
            raw.connect(address[4])
            connection.sock = (ssl.create_default_context().wrap_socket(raw, server_hostname=host)
                               if parsed.scheme == "https" else raw)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.request("GET", path, headers={
                "User-Agent": "MSBot/1.0", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirecionamento sem destino.")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"Pagina indisponivel: HTTP {response.status}.")
            kind = response.headers.get_content_type()
            if kind not in {"text/html", "text/plain", "application/json", "application/xhtml+xml"}:
                raise ValueError("Formato nao suportado; use paginas de texto.")
            chunks, size = [], 0
            while size <= 512_000:
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                chunk = response.read1(min(8192, 512_001 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            if size > 512_000:
                raise ValueError("Pagina excede o limite de tamanho.")
            return url, kind, b"".join(chunks).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        finally:
            connection.close()
            raw.close()
    raise ValueError("Muitos redirecionamentos.")


def fetch_url(url):
    url, kind, text = download(url)
    if "html" in kind:
        parser = PageText()
        parser.feed(text)
        text = "\n".join(parser.parts)
    return {"url": url, "text": text[:8000], "truncated": len(text) > 8000}


def weather(city, country_code=None):
    params = {"name": city, "count": 5, "language": "pt", "format": "json"}
    if country_code:
        params["countryCode"] = country_code.upper()
    _, _, text = download("https://geocoding-api.open-meteo.com/v1/search?" + urlencode(params))
    locations = json.loads(text).get("results") or []
    if not locations:
        return {"error": "Cidade nao encontrada."}
    place = locations[0]
    params = {"latitude": place["latitude"], "longitude": place["longitude"],
              "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
              "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
              "forecast_days": 1, "timezone": "auto"}
    _, _, text = download("https://api.open-meteo.com/v1/forecast?" + urlencode(params))
    data = json.loads(text)
    return {"source": "https://open-meteo.com/", "location": {
        k: place.get(k) for k in ("name", "admin1", "country", "latitude", "longitude")},
        "other_matches": [{"name": p.get("name"), "region": p.get("admin1"), "country": p.get("country")}
                          for p in locations[1:]],
        **{k: data.get(k) for k in ("timezone", "current", "current_units", "daily", "daily_units")}}


def local_definition(word):
    from python_pt_dictionary import dictionary
    from python_pt_dictionary.database import models
    from pathlib import Path
    from unidecode import unidecode

    # Temporarily bind this synchronous lookup to the installed package DB.
    # The context manager restores the shared model before returning.
    import peewee
    database = peewee.SqliteDatabase(str(Path(dictionary.__file__).parent / "database" / "dictionary.db"))
    with database.connection_context(), models.Any.bind_ctx(database):
        entry = dictionary.select(unidecode(word).lower(), dictionary.Selector.SIMPLE)
        return {"word": entry.text, "definition": entry.meaning[:5000]} if entry else {"word": word, "definition": None}


async def dictionary_lookup(search, word, mode="definition", target_language=None):
    if mode == "translation" and not target_language:
        raise ValueError("Informe target_language para traduzir.")
    # Keep Peewee model binding in the event-loop thread to avoid racing other
    # dictionary calls that share the model class.
    result = local_definition(word)
    result["source"] = "python_pt_dictionary"
    if mode != "definition":
        query = (f"sinonimos de {word}" if mode == "synonyms"
                 else f"traducao de {word} portugues para {target_language}")
        result["web_results"] = await search.search(query, 3)
        result["notice"] = "A biblioteca fornece definicoes; use somente evidencias da busca para sinonimos/traducoes."
    return result
