"""Unit tests for Auto-Prompt Optimizer and Multimodal Visual Redaction."""

from router.optimizer import PromptOptimizer
from kubemind_policy.multimodal import MultimodalPrivacyEngine


def test_prompt_optimizer_history_compression():
    opt = PromptOptimizer()
    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "system", "content": "You are a helpful coding assistant."},  # Duplicate
        {"role": "user", "content": "Hello! Could you please write a quick function to add two numbers? Thanks!"},
        {"role": "assistant", "content": "Sure thing! As an AI, here is the function:\ndef add(a, b):\n    return a + b\n\nHope this helps!"},
        {"role": "user", "content": "Can you make it handle floats?"},
    ]

    optimized, report = opt.optimize_messages(messages, intent="code", confidence=0.95)

    assert len(optimized) == 4  # Duplicate system prompt removed
    assert report.tokens_saved > 0
    assert report.compression_ratio < 1.0


def test_prompt_optimizer_borderline_few_shot_injection():
    opt = PromptOptimizer(enable_few_shot=True)
    messages = [
        {"role": "user", "content": "Write a secure SQL query to find users"},
    ]

    # Borderline confidence (0.55) triggers few-shot injection
    optimized, report = opt.optimize_messages(messages, intent="security", confidence=0.55)

    assert report.exemplars_injected is True
    assert len(optimized) > 1
    assert any("parameterized queries" in m["content"] for m in optimized)


def test_multimodal_visual_pii_detection_and_redaction():
    engine = MultimodalPrivacyEngine()

    fake_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Can you analyze this receipt?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{fake_b64}"},
                },
            ],
        }
    ]

    # OCR text contains a credit card number and email
    ocr_dict = {
        fake_b64: "Invoice Total: $450.00. Paid with Card: 4532-1234-5678-9012. Receipt to billing@acme.com."
    }

    redacted_messages, results = engine.redact_message_images(messages, mock_ocr_dict=ocr_dict)

    assert len(results) == 1
    assert results[0].is_modified is True
    assert "credit_card" in results[0].detectors_fired
    assert "email" in results[0].detectors_fired
    assert len(results[0].bounding_boxes) == 2

    # Verify visual image url in message was tokenized
    img_part = redacted_messages[0]["content"][1]
    assert "[KM_VISUAL_REDACTED_1]" in img_part["image_url"]["url"]
