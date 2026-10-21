import unittest

from core.brain.context_budget import (ANSWER_RESERVE_TOKENS, CHARS_PER_TOKEN, estimate_tokens, fit_prompt,
                                       split_sections)


def block(header, size):
    return header + "\n" + ("x" * (size - len(header) - 1))


class ContextBudgetTest(unittest.TestCase):
    def test_sections_follow_their_headers(self):
        text = "ABOUT GREY (owner):\n- a\n\n- b continues\n\nTECH NEWS from sources:\n- c"
        sections = split_sections(text)
        self.assertEqual([s.header[:10] for s in sections], ["ABOUT GREY", "TECH NEWS "])
        self.assertIn("- b continues", sections[0].text)

    def test_small_prompt_is_untouched(self):
        fitted = fit_prompt(fixed_text="system", question="hi", behavior="ABOUT GREY:\n- calm", conversation=None,
                            history=[{"role": "user", "content": "hello"}], context_window=8192)
        self.assertEqual(fitted.behavior, "ABOUT GREY:\n- calm")
        self.assertEqual(fitted.dropped_messages, 0)

    def test_overflow_drops_low_priority_first_and_keeps_room_to_answer(self):
        behavior = "\n\n".join([block("ABOUT GREY (owner):", 2500), block("LOCAL ZÆNIA BEHAVIOR PROFILE:", 1800),
                                block("TECH NEWS from sources:", 2400)])
        conversation = "\n\n".join([block("SAVED SOURCE LIBRARY — ref", 4000), block("VOICE CONTEXT STATE:", 500)])
        history = [{"role": "user" if i % 2 == 0 else "assistant", "content": "y" * 900} for i in range(16)]
        fixed = "s" * 5600
        fitted = fit_prompt(fixed_text=fixed, question="what's new?", behavior=behavior, conversation=conversation,
                            history=history, context_window=4096)
        self.assertLessEqual(fitted.prompt_tokens, 4096 - ANSWER_RESERVE_TOKENS + 40)
        self.assertIn("TECH NEWS", fitted.behavior)           # highest-priority section kept
        self.assertNotIn("VOICE CONTEXT STATE", fitted.conversation or "")  # lowest priority goes first
        self.assertGreater(fitted.dropped_messages, 0)
        self.assertEqual(fitted.history[-1]["content"], history[-1]["content"])  # newest turn kept

    def test_caps_apply_even_with_room(self):
        fitted = fit_prompt(fixed_text="s", question="q", behavior=None, conversation=block("SAVED SOURCE LIBRARY — r", 9500),
                            history=[], context_window=32768)
        self.assertLessEqual(len(fitted.conversation), 4000)
        self.assertIn("shortened to fit", fitted.conversation)

    def test_estimate_is_conservative(self):
        self.assertGreaterEqual(estimate_tokens("a" * 340), int(340 / CHARS_PER_TOKEN))


if __name__ == "__main__":
    unittest.main()
