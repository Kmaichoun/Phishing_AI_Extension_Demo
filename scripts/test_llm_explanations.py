"""Regression checks for factual, itemized local LLM explanations; no network access."""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import llm_explainer as explainer


LEGACY_OUTPUT_FIELDS = {"risk_type", "simple_explanation", "user_advice", "confidence_note"}
OUTPUT_FIELDS = LEGACY_OUTPUT_FIELDS | {"risk_reasons", "reassuring_reasons"}


def request(**overrides):
    values = {
        "url": "https://web.facebook.com/",
        "rule_score": 0,
        "fuzzy_score": 0,
        "random_forest_score": 46,
        "risk_score": 46,
        "risk_probability": 0.46,
        "decision": "allow",
        "fusion_method": "ml_only",
        "warning_threshold": 60,
        "blocking_threshold": 80,
        "feature_schema_version": "url-v10-reference-root-context",
        "language": "en",
    }
    values.update(overrides)
    return explainer.ExplainRequest(**values)


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        explainer.LLM_CACHE.clear()

    def tearDown(self):
        explainer.LLM_CACHE.clear()

    def assert_reason_groups(self, explanation):
        self.assertEqual(set(explanation), OUTPUT_FIELDS)
        for group in ("risk_reasons", "reassuring_reasons"):
            self.assertIsInstance(explanation[group], list)
            self.assertLessEqual(len(explanation[group]), 4)
            for reason in explanation[group]:
                self.assertEqual(set(reason), {"title", "explanation"})
                self.assertTrue(reason["title"])
                self.assertTrue(reason["explanation"])
                self.assertLessEqual(len(reason["title"]), 120)
                self.assertLessEqual(len(reason["explanation"]), 300)

    def test_private_url_parts_are_removed_from_every_input_channel(self):
        raw = "https://private-user:private-password@example.com/login?token=secret-query-value#secret-fragment-value"
        payload = request(
            url=raw,
            reasons=["Investigate " + raw],
            evidence_reasons=[{"title": "Inspect " + raw, "detail": "Redirect target: " + raw, "points": 0}],
            layer_results={"redirect": {"target": raw, "note": "Visit " + raw}},
        )
        llm_input = explainer.build_llm_input(payload)
        serialized = json.dumps(llm_input, ensure_ascii=False)
        for private in ("private-user", "private-password", "secret-query-value", "secret-fragment-value"):
            self.assertNotIn(private, serialized)
        self.assertEqual(llm_input["sanitized_url"], "https://example.com/login")
        self.assertEqual(llm_input["hostname"], "example.com")
        self.assertEqual(llm_input["features"]["has_at_symbol"], 1)

    def test_ml_only_explains_actual_source_without_changing_scores(self):
        payload = request(rule_score=90, fuzzy_score=80)
        before = payload.model_dump()
        llm_input = explainer.build_llm_input(payload)
        context = llm_input["score_context"]
        self.assertIn("Random Forest", context["score_summary"])
        self.assertIn("46", context["score_summary"])
        self.assertFalse(context["attribution_available"])
        self.assertTrue(context["observations"])
        self.assertIn("explanation_version", llm_input)
        self.assertEqual(llm_input["scores"]["risk_score"], 46)
        self.assertEqual(llm_input["scores"]["random_forest_score"], 46)
        self.assertEqual(llm_input["scores"]["rule_evidence_score"], 90)
        self.assertEqual(llm_input["scores"]["fusion_method"], "ml_only")
        self.assertEqual(payload.model_dump(), before)
        context_text = json.dumps(context, ensure_ascii=False).lower()
        self.assertIn("calibrat", context_text)
        self.assertTrue("advisory" in context_text or "support" in context_text or "reference" in context_text)

    def test_backend_decision_wins_over_display_rounding(self):
        allow = explainer.build_score_context(request(risk_score=20, decision="allow"))
        warn = explainer.build_score_context(request(risk_score=66, decision="warn"))
        block = explainer.build_score_context(request(risk_score=90, decision="block"))
        self.assertEqual(
            explainer.build_score_context(request(risk_score=60, risk_probability=.5999, decision="allow"))["verdict"],
            allow["verdict"],
        )
        self.assertEqual(
            explainer.build_score_context(request(risk_score=80, risk_probability=.7999, decision="warn"))["verdict"],
            warn["verdict"],
        )
        self.assertEqual(len({allow["verdict"], warn["verdict"], block["verdict"]}), 3)
        self.assertEqual(
            explainer.build_score_context(request(risk_score=80, risk_probability=.7999, decision=None))["verdict"],
            warn["verdict"],
        )

    def test_only_positive_evidence_supports_a_rule_warning(self):
        neutral = [
            {"title": "HTTPS", "detail": "Connection is encrypted", "points": -5},
            {"title": "Subdomain", "detail": "One subdomain exists", "points": 0},
        ]
        payload = request(risk_score=66, random_forest_score=66, decision="warn", evidence_reasons=neutral)
        context = explainer.build_score_context(payload)
        self.assertTrue(context["model_only_warning"])
        positive = neutral + [{"title": "IP hostname", "detail": "URL uses an IP address", "points": 20}]
        supported = explainer.build_score_context(request(
            risk_score=66, random_forest_score=66, decision="warn", rule_score=20,
            evidence_reasons=positive,
        ))
        self.assertFalse(supported["model_only_warning"])
        self.assertNotEqual(context["observations"], supported["observations"])

    def test_legacy_rule_total_and_allow_with_real_evidence_remain_honest(self):
        for language in ("en", "th"):
            with self.subTest(language=language):
                no_rule = explainer.build_score_context(request(
                    language=language, risk_score=66, random_forest_score=66, decision="warn", rule_score=0,
                ))
                legacy_rule = explainer.build_score_context(request(
                    language=language, risk_score=66, random_forest_score=66, decision="warn", rule_score=20,
                ))
                self.assertTrue(no_rule["model_only_warning"])
                self.assertFalse(legacy_rule["model_only_warning"])
                self.assertFalse(no_rule["positive_evidence"])
                self.assertEqual(len(legacy_rule["positive_evidence"]), 1)
                self.assertEqual(legacy_rule["observations"], legacy_rule["positive_evidence"])
                aggregate = " ".join(legacy_rule["observations"])
                self.assertIn("itemized" if language == "en" else "รายข้อ", aggregate)
                for invented_cause in ("IP", "redirect", "password", "รหัสผ่าน", "พารามิเตอร์"):
                    self.assertNotIn(invented_cause, aggregate)

                no_evidence_allow = explainer.build_score_context(request(language=language))
                positive_payload = request(
                    language=language, url="https://192.0.2.10/", rule_score=20,
                    evidence_reasons=[{
                        "title": "IP hostname",
                        "detail": "URL ใช้ IP แทนชื่อโดเมน" if language == "th" else "The URL uses an IP instead of a domain name.",
                        "points": 20,
                    }],
                )
                positive_allow = explainer.build_score_context(positive_payload)
                self.assertEqual(positive_allow["decision"], "allow")
                self.assertTrue(positive_allow["positive_evidence"])
                self.assertNotEqual(positive_allow["verdict"], no_evidence_allow["verdict"])
                self.assertIn("IP", " ".join(positive_allow["observations"]))
                fallback = explainer.fallback_explanation(positive_payload, "ollama_unavailable")
                self.assertEqual(fallback["risk_type"], positive_allow["verdict"])
                self.assertIn("IP", fallback["simple_explanation"])
                self.assertIn(positive_allow["score_summary"], fallback["simple_explanation"])

    def test_fallback_allow_does_not_invent_suspicious_signals(self):
        for language in ("en", "th"):
            with self.subTest(language=language):
                payload = request(language=language)
                context = explainer.build_score_context(payload)
                fallback = explainer.fallback_explanation(payload, "ollama_unavailable")
                self.assert_reason_groups(fallback)
                self.assertEqual(fallback["risk_type"], context["verdict"])
                self.assertIn(context["score_summary"], fallback["simple_explanation"])
                for invented in ("url still has signals", "suspicious but", "url มีสัญญาณบางอย่าง", "น่าสงสัยแต่"):
                    self.assertNotIn(invented, fallback["simple_explanation"].lower())
                self.assertIn("ollama_unavailable", fallback["confidence_note"])

    def test_ollama_request_and_response_keep_useful_detail_and_verdict(self):
        payload = request(language="th", risk_score=66, random_forest_score=66, decision="warn")
        before = payload.model_dump()
        llm_input = explainer.build_llm_input(payload)
        model_detail = (
            "URL นี้ใช้ HTTPS ซึ่งช่วยเข้ารหัสการเชื่อมต่อ แต่ไม่ได้ยืนยันว่าเนื้อหาปลอดภัย "
            "ระบบยังไม่มีหลักฐานจากกฎ URL ที่ชี้ถึงอันตรายชัดเจน จึงควรตรวจสอบแหล่งที่มาของลิงก์ก่อนกรอกข้อมูลสำคัญ "
            "โครงสร้าง URL เป็นข้อมูลประกอบและไม่ใช่หลักฐานว่ามีการขโมยข้อมูลจริง"
        )
        self.assertGreater(len(model_detail), 180)
        fake = {
            "risk_type": "ปลอดภัยแน่นอน",
            "simple_explanation": model_detail,
            "user_advice": "ตรวจชื่อโดเมนและแหล่งที่มาก่อนกรอกข้อมูลสำคัญ",
            "confidence_note": "มั่นใจเต็มร้อยว่าไม่มีอันตราย",
        }
        response = io.BytesIO(json.dumps({"message": {"content": json.dumps(fake, ensure_ascii=False)}}).encode())
        with patch.dict(os.environ, {"OLLAMA_MODEL": "qwen3:0.6b", "OLLAMA_BASE_URL": "http://127.0.0.1:11435"}):
            with patch.object(explainer.urllib.request, "urlopen", return_value=response) as http:
                result = explainer.call_ollama(payload, llm_input)
        sent = http.call_args.args[0]
        self.assertEqual(sent.full_url, "http://127.0.0.1:11435/api/chat")
        body = json.loads(sent.data.decode("utf-8"))
        self.assertGreaterEqual(body["format"]["properties"]["simple_explanation"]["maxLength"], 340)
        self.assertEqual(set(body["format"]["required"]), LEGACY_OUTPUT_FIELDS)
        self.assertNotIn("risk_reasons", body["format"]["properties"])
        self.assertNotIn("reassuring_reasons", body["format"]["properties"])
        self.assertFalse(body["stream"])
        prompt_input = json.loads(body["messages"][1]["content"])
        self.assertEqual(prompt_input, explainer.ollama_prompt_input(llm_input))
        self.assertEqual(prompt_input["score_context"], llm_input["score_context"])
        self.assertTrue(prompt_input["score_context"]["risk_facts"])
        self.assertTrue(prompt_input["score_context"]["reassuring_facts"])
        self.assertEqual(prompt_input["hostname"], llm_input["hostname"])
        self.assertEqual(prompt_input["language"], "th")
        for raw_channel in ("features", "evidence_layers", "evidence_reasons", "reasons", "threat_types", "scores"):
            self.assertNotIn(raw_channel, prompt_input)
        self.assertEqual(
            body["format"]["properties"]["user_advice"]["enum"],
            [explainer.default_advice(llm_input["score_context"]["decision"], "th")],
        )
        self.assertTrue(result["ok"])
        self.assert_reason_groups(result["llm"])
        self.assertTrue(result["llm"]["simple_explanation"].startswith(llm_input["score_context"]["score_summary"]))
        self.assertEqual(result["llm"]["risk_type"], llm_input["score_context"]["verdict"])
        self.assertNotEqual(result["llm"]["confidence_note"], fake["confidence_note"])
        self.assertIn(model_detail, result["llm"]["simple_explanation"])
        self.assertEqual(payload.model_dump(), before)

    def test_unobserved_content_claims_and_repeated_numbers_use_approved_facts(self):
        unsupported = [
            ("th", "ตรวจเนื้อหาหน้าเว็บแล้วพบแบบฟอร์มที่ขโมยรหัสผ่าน"),
            ("en", "I inspected the page content and found a form that steals passwords."),
            ("th", "คะแนน 66 สูงกว่าเกณฑ์เตือน 60 จึงต้องระวัง"),
            ("en", "The score is 66 and exceeds the warning threshold of 60."),
        ]
        for language, detail in unsupported:
            with self.subTest(language=language, detail=detail):
                payload = request(language=language, risk_score=66, random_forest_score=66, decision="warn")
                llm_input = explainer.build_llm_input(payload)
                context = llm_input["score_context"]
                fake = {"risk_type": "made-up", "simple_explanation": detail,
                        "user_advice": explainer.default_advice("warn", language), "confidence_note": "made-up"}
                result = explainer.finalize_explanation(fake, payload, llm_input)
                self.assertNotIn(detail.rstrip(" .;"), result["simple_explanation"])
                self.assertEqual(result["simple_explanation"].count(context["score_summary"]), 1)
                self.assertIn(explainer.approved_detail(context, language), result["simple_explanation"])
                self.assertEqual(result["risk_type"], context["verdict"])
                self.assertEqual(result["simple_explanation"].count("66"), 1)
                self.assertEqual(result["simple_explanation"].count("60"), 1)

    def test_detailed_groups_separate_risk_from_reassuring_url_observations(self):
        payload = request(url="https://192.0.2.10/", risk_score=66, random_forest_score=66,
                          decision="warn", rule_score=20, evidence_reasons=[
            {"title": "IP hostname", "detail": "The URL uses an IP instead of a domain name.", "points": 20},
            {"title": "Encrypted connection", "detail": "HTTPS encrypts the connection but does not certify content.", "points": -5},
            {"title": "Neutral observation", "detail": "A single ordinary path is present.", "points": 0},
        ])
        llm_input = explainer.build_llm_input(payload)
        before = payload.model_dump()
        result = explainer.finalize_explanation({}, payload, llm_input)
        self.assert_reason_groups(result)
        risk = " ".join(reason["title"] + " " + reason["explanation"] for reason in result["risk_reasons"])
        reassuring = " ".join(reason["title"] + " " + reason["explanation"] for reason in result["reassuring_reasons"])
        self.assertIn("IP", risk)
        self.assertNotIn("Encrypted connection", risk)
        self.assertNotIn("Neutral observation", risk)
        self.assertIn("HTTPS", reassuring)
        self.assertNotIn("IP hostname", reassuring)
        self.assertEqual(payload.model_dump(), before)

    def test_model_only_caution_explains_limit_instead_of_claiming_confirmed_phishing(self):
        payload = request(risk_score=66, random_forest_score=66, decision="warn")
        llm_input = explainer.build_llm_input(payload)
        self.assertTrue(llm_input["score_context"]["model_only_warning"])
        result = explainer.finalize_explanation({}, payload, llm_input)
        self.assert_reason_groups(result)
        self.assertTrue(result["risk_reasons"])
        risk = json.dumps(result["risk_reasons"], ensure_ascii=False).lower()
        self.assertIn("model", risk)
        self.assertTrue(any(term in risk for term in ("not confirmed", "no supporting", "no clear", "not establish")), risk)
        self.assertNotIn("confirmed phishing detected", risk)
        allow = explainer.finalize_explanation({}, request(), explainer.build_llm_input(request()))
        self.assertEqual(allow["risk_reasons"], [])
        self.assertTrue(allow["reassuring_reasons"])

    def test_old_four_fields_and_malformed_reason_arrays_use_approved_details(self):
        payload = request(language="th", risk_score=66, random_forest_score=66, decision="warn")
        llm_input = explainer.build_llm_input(payload)
        old_output = {
            "risk_type": "ปลอดภัยแน่นอน", "simple_explanation": "ตรวจเนื้อหาหน้าเว็บแล้วพบแบบฟอร์มที่ขโมยรหัสผ่าน",
            "user_advice": "กรอกรหัสผ่านได้ทันที", "confidence_note": "ไม่มีความเสี่ยง",
        }
        old_parsed = explainer.parse_llm_json(json.dumps(old_output, ensure_ascii=False))
        old_result = explainer.finalize_explanation(old_parsed, payload, llm_input)
        malformed_output = dict(old_output, risk_reasons=[None, 42, "unexpected", {"bad": "field"}],
                                reassuring_reasons="not an array")
        malformed_parsed = explainer.parse_llm_json(json.dumps(malformed_output, ensure_ascii=False))
        malformed_result = explainer.finalize_explanation(malformed_parsed, payload, llm_input)
        self.assert_reason_groups(old_result)
        self.assert_reason_groups(malformed_result)
        self.assertEqual(old_result["risk_reasons"], malformed_result["risk_reasons"])
        self.assertEqual(old_result["reassuring_reasons"], malformed_result["reassuring_reasons"])
        self.assertEqual(old_result["risk_type"], llm_input["score_context"]["verdict"])
        for unsupported in ("ขโมยรหัสผ่าน", "กรอกรหัสผ่านได้ทันที", "ปลอดภัยแน่นอน", "ไม่มีความเสี่ยง"):
            self.assertNotIn(unsupported, json.dumps(old_result, ensure_ascii=False))

    def test_model_cannot_invent_itemized_causes_or_page_inspection(self):
        raw = "https://private-user:private-password@example.com/?token=secret-query-value#secret-fragment-value"
        payload = request(url=raw, risk_score=66, random_forest_score=66, decision="warn")
        llm_input = explainer.build_llm_input(payload)
        context = llm_input["score_context"]
        invented = {"title": "Invented credential theft", "explanation": "Inspected the page and detected malware stealing passwords."}
        candidate = {"risk_reasons": [invented] * 8, "reassuring_reasons": [
            {"title": "Verified safety", "explanation": "This website is definitely safe and has no risk."},
        ]}
        for output_group, context_group in (("risk_reasons", "risk_facts"), ("reassuring_reasons", "reassuring_facts")):
            self.assertTrue(context[context_group])
            candidate[output_group].append({"title": context[context_group][0]["title"],
                                          "explanation": "Inspected the page content and found password theft. secret-query-value"})
        result = explainer.finalize_explanation(candidate, payload, llm_input)
        self.assert_reason_groups(result)
        serialized = json.dumps(result, ensure_ascii=False).lower()
        for unsupported in ("invented credential theft", "verified safety", "inspected the page", "password theft", "detected malware",
                            "secret-query-value", "private-user", "private-password", "secret-fragment-value", "definitely safe"):
            self.assertNotIn(unsupported, serialized)
        for output_group, context_group in (("risk_reasons", "risk_facts"), ("reassuring_reasons", "reassuring_facts")):
            self.assertEqual(result[output_group], context[context_group])

    def test_matching_heading_cannot_attach_unobserved_domain_history_or_site_content(self):
        invented_details = [
            "The domain was registered yesterday and is hosting spyware.",
            "The owner steals banking data and sells login information.",
            "The page contains a phishing login form; this link is fully safe after removing it.",
        ]
        payload = request(url="https://192.0.2.10/", rule_score=20, risk_score=66,
                          random_forest_score=66, decision="warn")
        llm_input = explainer.build_llm_input(payload)
        context = llm_input["score_context"]
        for invented_detail in invented_details:
            with self.subTest(invented_detail=invented_detail):
                candidate = {}
                for output_group, context_group in (("risk_reasons", "risk_facts"), ("reassuring_reasons", "reassuring_facts")):
                    self.assertTrue(context[context_group])
                    candidate[output_group] = [{"title": context[context_group][0]["title"],
                                               "explanation": invented_detail}]
                result = explainer.finalize_explanation(candidate, payload, llm_input)
                self.assert_reason_groups(result)
                self.assertNotIn(invented_detail, json.dumps(result, ensure_ascii=False))
                self.assertEqual(result["risk_reasons"], context["risk_facts"])
                self.assertEqual(result["reassuring_reasons"], context["reassuring_facts"])

    def test_model_elaboration_cannot_invent_numeric_feature_contribution(self):
        payload = request(url="https://192.0.2.10/", rule_score=20, risk_score=66,
                          random_forest_score=66, decision="warn")
        llm_input = explainer.build_llm_input(payload)
        context = llm_input["score_context"]
        candidate = {"risk_reasons": [{"title": context["risk_facts"][0]["title"],
                                       "explanation": "This particular feature contributes 37 points and has a weight of 0.84."}]}
        result = explainer.finalize_explanation(candidate, payload, llm_input)
        self.assertEqual(result["risk_reasons"], context["risk_facts"])
        for invented_value in ("37", "0.84"):
            self.assertNotIn(invented_value, json.dumps(result, ensure_ascii=False))

    def test_explanation_version_invalidates_old_cache(self):
        payload = request()
        original_builder = explainer.build_llm_input
        model_result = {"ok": True, "provider": "ollama", "llm": {field: "fixture" for field in LEGACY_OUTPUT_FIELDS}, "cached": False}
        with patch.object(explainer, "llm_provider", return_value="ollama"):
            with patch.object(explainer, "call_ollama", return_value=model_result) as generate:
                self.assertFalse(explainer.explain_with_llm(payload)["cached"])
                self.assertTrue(explainer.explain_with_llm(payload)["cached"])
                self.assertEqual(generate.call_count, 1)

                def new_version(item):
                    data = original_builder(item)
                    data["explanation_version"] = str(data["explanation_version"]) + "-changed"
                    return data

                with patch.object(explainer, "build_llm_input", side_effect=new_version):
                    self.assertFalse(explainer.explain_with_llm(payload)["cached"])
                    self.assertTrue(explainer.explain_with_llm(payload)["cached"])
                self.assertEqual(generate.call_count, 2)

    def test_evidence_input_is_bounded_and_retains_points(self):
        rows = [{"title": "HTTPS", "detail": "Encrypted connection", "points": -5}] * 8
        payload = request(evidence_reasons=rows)
        self.assertEqual(len(payload.evidence_reasons), 8)
        self.assertEqual(payload.model_dump()["evidence_reasons"][0]["points"], -5)
        with self.assertRaises(ValidationError):
            request(evidence_reasons=rows + rows[:1])


if __name__ == "__main__":
    unittest.main()
