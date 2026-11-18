"""Cliente do Nemotron Super (NVIDIA) via API compatível com OpenAI."""
import json
import re
import time

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from . import config

_cliente = None


def _client():
    global _cliente
    if _cliente is None:
        if not config.NVIDIA_API_KEY:
            raise SystemExit("Defina NVIDIA_API_KEY no arquivo .env (crie em https://build.nvidia.com)")
        # Sem limite, uma chamada travada na NVIDIA prende a ferramenta por até 30 min
        _cliente = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY, timeout=240, max_retries=2)
    return _cliente


def _limpar(texto):
    # Modelos Nemotron com raciocínio podem devolver <think>...</think> antes da resposta
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    return texto.strip()


def chat(prompt, sistema="", temperatura=0.7, max_tokens=8192, pensar=False):
    """pensar=True liga o raciocínio do Nemotron 3: ~10x mais lento, útil só para revisão/checagem."""
    mensagens = [{"role": "user", "content": prompt}]
    if sistema:
        mensagens.insert(0, {"role": "system", "content": sistema})
    esperas = [15, 30, 60, 90, 120, 180]
    for tentativa in range(len(esperas) + 1):
        try:
            resp = _client().chat.completions.create(
                model=config.NVIDIA_MODEL,
                messages=mensagens,
                temperature=temperatura,
                top_p=0.95,
                max_tokens=max_tokens + (8000 if pensar else 0),
                extra_body={"chat_template_kwargs": {"enable_thinking": pensar}},
            )
            return _limpar(resp.choices[0].message.content)
        except (RateLimitError, InternalServerError, APITimeoutError, APIConnectionError) as e:
            # O plano gratuito da NVIDIA fica sobrecarregado às vezes (503/429): espera e tenta de novo
            if tentativa == len(esperas):
                raise
            print(f"    NVIDIA indisponível ({e.__class__.__name__}), tentando de novo em {esperas[tentativa]}s...")
            time.sleep(esperas[tentativa])


def _extrair_json(texto):
    texto = re.sub(r"```(?:json)?", "", texto)
    inicio = min((i for i in (texto.find("{"), texto.find("[")) if i != -1), default=-1)
    if inicio == -1:
        raise ValueError("nenhum JSON na resposta")
    fecha = "}" if texto[inicio] == "{" else "]"
    fim = texto.rfind(fecha)
    return json.loads(texto[inicio:fim + 1])


def chat_json(prompt, sistema="", temperatura=0.7, tentativas=3, max_tokens=8192, pensar=False):
    """Pede uma resposta em JSON e tenta de novo se vier malformada."""
    sistema = (sistema + "\nResponda SOMENTE com JSON válido, sem texto antes ou depois.").strip()
    ultimo_erro = None
    for _ in range(tentativas):
        texto = chat(prompt, sistema, temperatura, max_tokens, pensar)
        try:
            return _extrair_json(texto)
        except (ValueError, json.JSONDecodeError) as e:
            ultimo_erro = e
    raise RuntimeError(f"O modelo não devolveu JSON válido: {ultimo_erro}")
