from __future__ import annotations

import asyncio
import json
import re

from app.tools.context_tools import ContextTools
from app.tools.public_tools import calculator, fetch_url, weather, dictionary_lookup


def definition(name, description, properties, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required), "additionalProperties": False},
    }}


def string(description, **extra):
    return {"type": "string", "description": description, "maxLength": 600, **extra}


class ToolRegistry:
    """Bound to one request: no shared mutable user/channel state."""

    def __init__(self, web_search, context=None, *, channel_id=None, user_id=None):
        self.web_search = web_search
        self.context = context
        self.local = ContextTools(context, channel_id, user_id) if context else None

    def bind(self, channel_id, user_id):
        return ToolRegistry(self.web_search, self.context, channel_id=channel_id, user_id=user_id)

    def definitions(self):
        channel = {"channel_id": string("ID do canal; omitido usa o canal atual", pattern=r"^[0-9]+$")}
        user = {"user_id": string("ID do usuario; omitido usa o autor", pattern=r"^[0-9]+$")}
        definitions = [
            definition("memory_search", "Pesquisa memorias por usuario, canal ou servidor.", {
                "query": string("Termos; vazio lista memorias", minLength=0),
                "scope": string("Escopo", enum=["user", "channel", "server"]),
                **user, **channel}, ["scope"]),
            definition("recent_messages", "Le as ultimas 5 mensagens em ordem cronologica.", channel),
            definition("fetch_url", "Le texto de pagina publica para aprofundar resultados web.", {
                "url": string("URL publica HTTP/HTTPS", maxLength=2000)}, ["url"]),
            definition("weather", "Clima atual e previsao de hoje via Open-Meteo. Cite a fonte.", {
                "city": string("Nome da cidade"),
                "country_code": string("Pais opcional ISO de duas letras", maxLength=2)}, ["city"]),
            definition("first_count", "Consulta a quantidade de firsts do usuario no servidor.", user),
            definition("top_firsts", "Retorna o top 25 de firsts de todos os tempos, com posicao, username e apelido.", {}),
            definition("monthly_firsts", "Retorna todas as pessoas unicas que conseguiram firsts em um mes.", {
                "year": {"type": "integer", "minimum": 1970, "maximum": 2100},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
            }, ["year", "month"]),
            definition("user_profile", "Busca as informacoes publicas disponiveis do usuario com quem a conversa ocorre, sua entrada no servidor e uma amostra de mensagens acessiveis.", {}),
            definition("get_message", "Le uma mensagem especifica por ID e canal.", {
                **channel, "message_id": string("ID da mensagem", pattern=r"^[0-9]+$")}, ["message_id"]),
            definition("dictionary", "Definicoes portuguesas; sinonimos/traducoes usam busca web quando necessario.", {
                "word": string("Palavra", maxLength=100),
                "mode": string("Tipo da consulta", enum=["definition", "synonyms", "translation"]),
                "target_language": string("Idioma da traducao", maxLength=50)}, ["word"]),
            definition("web_search", "Busca via DuckDuckGo Instant Answer.", {
                "query": string("Termos de busca"),
                "max_results": {"type": "integer", "minimum": 1, "maximum": 5}}, ["query"]),
            definition("calculator", "Calcula expressoes aritmeticas locais sem executar codigo Python.", {
                "expression": string("Conta aritmetica com +, -, *, /, //, %, ** e parenteses", maxLength=256),
            }, ["expression"]),
        ]
        definitions.extend([
            definition("remove_platelminto", "Retira Platelminto do autor atual quando a mensagem dirigida a voce for claramente ofensiva e voce desgostar MUITO dela; criterio oposto de give_platelminto.", {"reason": string("Motivo concreto baseado na mensagem atual", maxLength=400)}, ["reason"]),
            definition("remove_homunco", "Retira Homunco do autor atual quando voce gostar MUITO da mensagem dirigida a voce; criterio oposto de give_homunco.", {"reason": string("Motivo concreto baseado na mensagem atual", maxLength=400)}, ["reason"]),
            definition("remove_quarentena", "Retira Quarentena do autor atual quando voce gostar MUITO da mensagem dirigida a voce; criterio oposto de give_quarentena.", {"reason": string("Motivo concreto baseado na mensagem atual", maxLength=400)}, ["reason"]),
            definition("message_count", "Conta mensagens registradas do autor neste servidor desde o inicio do acompanhamento. Nao e um total historico completo.", {}),
            definition("give_platelminto", "Atribui Platelminto ao autor atual quando voce gostar MUITO da mensagem dirigida a voce.", {"reason": string("Motivo concreto baseado na mensagem atual", maxLength=400)}, ["reason"]),
            definition("give_homunco", "Atribui Homunco ao autor atual quando a mensagem dirigida a voce for claramente ofensiva e voce desgostar muito dela.", {"reason": string("Motivo concreto baseado na mensagem atual", maxLength=400)}, ["reason"]),
            definition("give_quarentena", "Atribui Quarentena ao autor atual quando a mensagem dirigida a voce for claramente ofensiva e voce desgostar muito dela.", {"reason": string("Motivo concreto baseado na mensagem atual", maxLength=400)}, ["reason"]),
        ])
        if self.local is None:
            return [item for item in definitions if item["function"]["name"] == "web_search"]
        return definitions

    async def execute_call(self, tool_call):
        try:
            function = tool_call["function"]
            name = function["name"]
            spec = next((d["function"]["parameters"] for d in self.definitions()
                         if d["function"]["name"] == name), None)
            if spec is None:
                return {"error": "ferramenta nao permitida"}
            args = json.loads(function.get("arguments") or "{}")
            if not isinstance(args, dict) or set(args) - set(spec["properties"]) or set(spec["required"]) - set(args):
                raise ValueError("Argumentos ausentes ou desconhecidos.")
            for key, value in args.items():
                rule = spec["properties"][key]
                if rule["type"] == "string":
                    if not isinstance(value, str) or not rule.get("minLength", 1) <= len(value) <= rule["maxLength"]:
                        raise ValueError("Texto invalido: " + key)
                    if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
                        raise ValueError("ID invalido: " + key)
                elif type(value) is not int or not rule["minimum"] <= value <= rule["maximum"]:
                    raise ValueError("Numero invalido: " + key)
                if "enum" in rule and value not in rule["enum"]:
                    raise ValueError("Opcao invalida: " + key)
            if name == "web_search":
                task = self.web_search.search(**args)
            elif name == "fetch_url":
                task = asyncio.to_thread(fetch_url, **args)
            elif name == "weather":
                task = asyncio.to_thread(weather, **args)
            elif name == "dictionary":
                task = dictionary_lookup(self.web_search, **args)
            elif name == "calculator":
                task = asyncio.to_thread(calculator, **args)
            else:
                task = getattr(self.local, name)(**args)
            return await asyncio.wait_for(task, timeout=25)
        except (ValueError, KeyError, TypeError) as error:
            return {"error": str(error)}
        except Exception as error:
            return {"error": "Consulta indisponivel: " + type(error).__name__}
