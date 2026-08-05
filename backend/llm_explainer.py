from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Literal
from urllib.parse import urlparse, urlunparse

from pydantic import BaseModel, Field

from feature_extractor import extract_features

DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_OLLAMA_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
LLM_CACHE: dict[str, dict[str, object]] = {}


class ExplainRequest(BaseModel):
    url: str
    rule_score: int | None = Field(default=None, ge=0, le=100)
    risk_probability: float | None = Field(default=None, ge=0, le=1)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    decision: Literal["allow", "warn", "block"] | None = None
    warning_threshold: float | None = Field(default=None, ge=0, le=100)
    blocking_threshold: float | None = Field(default=None, ge=0, le=100)
    model_version: str | None = Field(default=None, max_length=100)
    policy_version: str | None = Field(default=None, max_length=100)
    layer_results: dict[str, object] = Field(default_factory=dict)
    # Legacy fields are accepted while older clients are being upgraded.
    ml_score: int | None = Field(default=None, ge=0, le=100)
    final_score: int | None = Field(default=None, ge=0, le=100)
    alpha: float | None = Field(default=None, ge=0, le=1)
    decision_threshold: float | None = Field(default=None, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    threat_types: list[str] = Field(default_factory=list)
    language: Literal["th", "en"] = "th"


def llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    if provider in {"ollama", "local", "qwen"}:
        return "ollama"
    if provider == "auto":
        return "ollama" if ollama_available(timeout=0.25) else "openai"
    return "openai"


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


def ollama_available(timeout: float = 0.7) -> bool:
    try:
        with urllib.request.urlopen(ollama_base_url() + "/api/tags", timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def llm_status() -> dict[str, object]:
    provider = llm_provider()
    if provider == "ollama":
        return {
            "llm_ready": ollama_available(),
            "provider": "ollama",
            "ollama_model": ollama_model(),
            "ollama_base_url": ollama_base_url(),
            "openai_model": os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        }
    return {
        "llm_ready": bool(os.getenv("OPENAI_API_KEY")),
        "provider": "openai",
        "openai_model": os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "ollama_model": ollama_model(),
    }


def sanitize_url_for_llm(raw_url: str) -> dict[str, str]:
    try:
        parsed = urlparse(raw_url)
        hostname = parsed.hostname or ""
        path = parsed.path[:140]
        display_host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
        port = parsed.port
        netloc = f"{display_host}:{port}" if port else display_host
        safe_url = urlunparse((parsed.scheme, netloc, path, "", "", ""))
        return {"url": safe_url, "hostname": hostname, "path": path}
    except Exception:
        return {"url": "", "hostname": "", "path": ""}


def clean_text(value: object, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def clean_text_list(values: list[str], limit: int = 6) -> list[str]:
    cleaned: list[str] = []
    for value in values[:limit]:
        text = clean_text(value)
        if text:
            cleaned.append(text)
    return cleaned


def fallback_explanation(payload: ExplainRequest, status: str = "fallback") -> dict[str, str]:
    risk_score = payload.risk_score
    if risk_score is None:
        risk_score = payload.final_score if payload.final_score is not None else payload.ml_score
    warning_threshold = (
        payload.warning_threshold
        if payload.warning_threshold is not None
        else payload.decision_threshold
        if payload.decision_threshold is not None
        else 61.0
    )
    decision = payload.decision
    if decision is None and risk_score is not None:
        decision = "warn" if risk_score >= warning_threshold else "allow"

    if payload.language == "en":
        advice = "Do not enter passwords, OTPs, card data, seed phrases, or download unknown files until you verify the website from an official source."
        confidence_note = f"LLM explanation is not active ({status}); this fallback uses the supplied risk evidence only."
    else:
        advice = "อย่ากรอกรหัสผ่าน OTP ข้อมูลบัตร seed phrase หรือดาวน์โหลดไฟล์ จนกว่าจะตรวจสอบจากแหล่งทางการก่อน"
        confidence_note = f"ยังไม่ได้ใช้ LLM จริง ({status}) คำอธิบายสำรองนี้ใช้เฉพาะหลักฐานความเสี่ยงที่ระบบส่งมา"

    if decision in {"warn", "block"}:
        if payload.language == "en":
            return {
                "risk_type": "Potential phishing or suspicious website",
                "simple_explanation": "The system found URL and scoring signals that may indicate phishing, fraud, malware, redirects, or suspicious SEO behavior.",
                "user_advice": advice,
                "confidence_note": confidence_note,
            }
        return {
            "risk_type": "เว็บไซต์อาจเป็น phishing หรือเว็บน่าสงสัย",
            "simple_explanation": "ระบบพบสัญญาณจากรูปแบบ URL และคะแนนตรวจจับที่อาจเกี่ยวข้องกับ phishing, scam, malware, redirect หรือพฤติกรรมน่าสงสัย",
            "user_advice": advice,
            "confidence_note": confidence_note,
        }

    if payload.language == "en":
        return {
            "risk_type": "Suspicious but not confirmed",
            "simple_explanation": "The score is not in the highest risk range, but the URL still has signals worth checking.",
            "user_advice": advice,
            "confidence_note": confidence_note,
        }
    return {
        "risk_type": "น่าสงสัยแต่ยังไม่ยืนยันว่าอันตราย",
        "simple_explanation": "คะแนนยังไม่ถึงระดับอันตรายสูงสุด แต่ URL มีสัญญาณบางอย่างที่ควรตรวจสอบก่อนใช้งาน",
        "user_advice": advice,
        "confidence_note": confidence_note,
    }


def parse_llm_json(raw_text: str) -> dict[str, str]:
    text = raw_text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]

    data = json.loads(text)
    return {
        "risk_type": clean_text(data.get("risk_type"), 120),
        "simple_explanation": clean_text(data.get("simple_explanation"), 420),
        "user_advice": clean_text(data.get("user_advice"), 320),
        "confidence_note": clean_text(data.get("confidence_note"), 220),
    }


def build_llm_input(payload: ExplainRequest) -> dict[str, object]:
    safe = sanitize_url_for_llm(payload.url)
    features = extract_features(payload.url)
    compact_features = {
        "url_length": features["url_length"],
        "hostname_length": features["hostname_length"],
        "num_dots": features["num_dots"],
        "num_hyphens": features["num_hyphens"],
        "num_digits": features["num_digits"],
        "subdomain_count": features["subdomain_count"],
        "has_https": features["has_https"],
        "has_ip_host": features["has_ip_host"],
        "has_at_symbol": features["has_at_symbol"],
        "has_encoded_url": features["has_encoded_url"],
        "has_nested_url": features["has_nested_url"],
        "is_shortener": features["is_shortener"],
        "risky_tld": features["risky_tld"],
        "suspicious_word_count": features["suspicious_word_count"],
    }
    risk_score = payload.risk_score
    if risk_score is None:
        risk_score = payload.final_score if payload.final_score is not None else payload.ml_score
    warning_threshold = (
        payload.warning_threshold
        if payload.warning_threshold is not None
        else payload.decision_threshold
        if payload.decision_threshold is not None
        else 61.0
    )
    blocking_threshold = (
        payload.blocking_threshold
        if payload.blocking_threshold is not None
        else max(81.0, warning_threshold)
    )
    return {
        "sanitized_url": safe["url"],
        "hostname": safe["hostname"],
        "path_sample": safe["path"],
        "scores": {
            "risk_probability": payload.risk_probability,
            "risk_score": risk_score,
            "decision": payload.decision,
            "warning_threshold": warning_threshold,
            "blocking_threshold": blocking_threshold,
            "rule_evidence_score": payload.rule_score,
            "ml_score": payload.ml_score,
            "formula": "FinalScore = 0.40 * RuleScore + 0.60 * MLScore",
            "rule_weight": 0.40,
            "ml_weight": 0.60,
            "model_version": payload.model_version,
            "policy_version": payload.policy_version,
        },
        "evidence_layers": payload.layer_results,
        "threat_types": clean_text_list(payload.threat_types, 5),
        "reasons": clean_text_list(payload.reasons, 6),
        "features": compact_features,
        "language": payload.language,
    }


def build_instructions(language: str) -> str:
    output_language = "Thai" if language == "th" else "English"
    return (
        "You are a cybersecurity explanation assistant for a phishing warning page. "
        "Use only the supplied URL risk signals, scores, reasons, and features. "
        "Do not browse the web and do not claim that the site is definitely malicious unless the signals support caution. "
        "Do not repeat sensitive query parameters. Explain in simple user-friendly language. "
        f"Respond in {output_language}. "
        "Return only valid JSON with exactly these string keys: "
        "risk_type, simple_explanation, user_advice, confidence_note."
    )


def call_ollama(payload: ExplainRequest, llm_input: dict[str, object]) -> dict[str, object]:
    model_name = ollama_model()
    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": build_instructions(payload.language)},
            {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False)},
        ],
        "stream": False,
        "think": False,
        "format": {
            "type": "object",
            "properties": {
                "risk_type": {"type": "string"},
                "simple_explanation": {"type": "string"},
                "user_advice": {"type": "string"},
                "confidence_note": {"type": "string"},
            },
            "required": ["risk_type", "simple_explanation", "user_advice", "confidence_note"],
        },
        "options": {"temperature": 0.2},
    }
    request = urllib.request.Request(
        ollama_base_url() + "/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    raw_text = data.get("message", {}).get("content", "")
    explanation = parse_llm_json(raw_text)
    return {
        "ok": True,
        "provider": "ollama",
        "model": model_name,
        "llm": explanation,
        "sanitized_url": llm_input["sanitized_url"],
        "cached": False,
    }


def openai_error_status(error_text: str) -> str:
    lowered = error_text.lower()
    if "insufficient_quota" in lowered or "exceeded your current quota" in lowered:
        return "insufficient_quota"
    if "invalid_api_key" in lowered or "incorrect api key" in lowered:
        return "invalid_api_key"
    if "model_not_found" in lowered or "does not exist" in lowered:
        return "model_not_available"
    if "rate_limit" in lowered or "rate limit" in lowered:
        return "rate_limited"
    return "llm_error"


def call_openai(payload: ExplainRequest, llm_input: dict[str, object]) -> dict[str, object]:
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "ok": False,
            "provider": "fallback",
            "status": "missing_api_key",
            "llm": fallback_explanation(payload, "missing_api_key"),
        }

    try:
        from openai import OpenAI
    except ImportError:
        return {
            "ok": False,
            "provider": "fallback",
            "status": "openai_package_missing",
            "llm": fallback_explanation(payload, "openai_package_missing"),
        }

    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    try:
        client = OpenAI()
        response = client.responses.create(
            model=model_name,
            instructions=build_instructions(payload.language),
            input=json.dumps(llm_input, ensure_ascii=False),
            max_output_tokens=420,
            store=False,
        )
        explanation = parse_llm_json(response.output_text)
        return {
            "ok": True,
            "provider": "openai",
            "model": model_name,
            "llm": explanation,
            "sanitized_url": llm_input["sanitized_url"],
            "cached": False,
        }
    except Exception as error:
        error_text = str(error)
        status = openai_error_status(error_text)
        return {
            "ok": False,
            "provider": "fallback",
            "status": status,
            "error": error_text,
            "llm": fallback_explanation(payload, status),
        }


def explain_with_llm(payload: ExplainRequest) -> dict[str, object]:
    provider = llm_provider()
    llm_input = build_llm_input(payload)
    cache_key = json.dumps({"provider": provider, "model": ollama_model() if provider == "ollama" else os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL), "input": llm_input}, ensure_ascii=False, sort_keys=True)
    if cache_key in LLM_CACHE:
        cached = dict(LLM_CACHE[cache_key])
        cached["cached"] = True
        return cached

    if provider == "ollama":
        try:
            result = call_ollama(payload, llm_input)
            LLM_CACHE[cache_key] = result
            return result
        except urllib.error.HTTPError as error:
            return {
                "ok": False,
                "provider": "fallback",
                "status": "ollama_error",
                "error": error.read().decode("utf-8", errors="replace"),
                "llm": fallback_explanation(payload, "ollama_error"),
            }
        except Exception as error:
            return {
                "ok": False,
                "provider": "fallback",
                "status": "ollama_unavailable",
                "error": str(error),
                "llm": fallback_explanation(payload, "ollama_unavailable"),
            }

    result = call_openai(payload, llm_input)
    if result.get("ok"):
        LLM_CACHE[cache_key] = result
    return result
