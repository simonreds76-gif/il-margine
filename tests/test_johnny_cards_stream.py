import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from johnny_cards import lines, utc
from johnny_cards_review import Analyst, read_assessment


def frame(**event):
    return b"data: " + json.dumps(event).encode()


def chunk(content=None, finish=None):
    return frame(choices=[{"delta": {"content": content}, "finish_reason": finish}])


def replay(packets, times):
    return read_assessment(packets, 0, clock=iter(times).__next__)


class StreamTests(unittest.TestCase):
    def test_cold_prompt_can_take_over_twenty_minutes(self):
        progress = [frame(prompt_progress={"processed": n, "total": 12000})
                    for n in range(0, 12001, 1000)]
        packets = progress + [chunk('{"ok":'), chunk("true}"), chunk(finish="stop"), b"data: [DONE]"]
        times = [110 * i for i in range(len(progress))] + [1321, 1322, 1323, 1324]
        self.assertEqual(replay(packets, times), {"ok": True})

    def test_stalled_processing_and_keepalives(self):
        heartbeat = frame(prompt_progress={"processed": 2, "total": 1000})
        with self.assertRaisesRegex(TimeoutError, "stopped making progress"):
            replay([heartbeat, heartbeat, b": ping", heartbeat], [5, 100, 200, 306])

    def test_truncated_or_disconnected_answers_are_rejected(self):
        for tail in ([chunk(finish="length"), b"data: [DONE]"], [chunk(finish="stop")],
                     [b"data: [DONE]"], [frame(error={"message": "failed"})]):
            with self.subTest(tail=tail), self.assertRaises(RuntimeError):
                replay([chunk('{"ok":true}'), *tail], range(10))

    def test_timeout_remains_bounded_while_progress_continues(self):
        with self.assertRaisesRegex(TimeoutError, "time budget"):
            replay([frame(prompt_progress={"processed": i}) for i in range(30)],
                   [i * 100 for i in range(30)])

    def test_started_fixture_is_removed_from_digest_recommendations(self):
        report = {"day":"2026-11-24","calendar":[{"gap":""}],"failures":0,
                  "slate":[{"home":"A","away":"B","ko":"2026-11-24T17:45:00Z",
                            "screen":"complete","cases":[{"verdict":"BET"}]}]}
        text = "\n".join(lines(report, as_of=utc("2026-11-24T17:45:01Z")))
        self.assertIn("kickoff passed", text)
        self.assertNotIn("BET", text)


if __name__ == "__main__" and "--engine-smoke" in sys.argv:
    # Exercise the actual pinned server and JSON grammar on a public test fixture.
    # Neither the private guide nor any credentials are required by this check.
    analyst = Analyst(None)
    analyst.guide = "Return the number from the sample input unchanged. " + "Example fixture evidence. " * 650
    def verify_stream(events, started):
        positive_progress = []
        def observe():
            for line in events:
                if line.startswith(b"data:") and line[5:].strip() != b"[DONE]":
                    progress = json.loads(line[5:]).get("prompt_progress", {})
                    if progress.get("processed", 0) > 0:
                        positive_progress.append(progress["processed"])
                yield line
        answer = read_assessment(observe(), started)
        if not positive_progress:
            raise RuntimeError("Pinned model returned no positive prompt progress")
        print(f"Verified live progress through {max(positive_progress)} input tokens", flush=True)
        return answer
    try:
        with patch("johnny_cards_review.read_assessment", side_effect=verify_stream):
            value = analyst.ask("Copy sample.", {"sample": 17},
                                {"type":"object","properties":{"sample":{"type":"integer","enum":[17]}},
                                 "required":["sample"],"additionalProperties":False}, 32)
        if value != {"sample": 17}:
            raise SystemExit("Wrong streamed answer")
    finally:
        analyst.__exit__(None,None,None)
