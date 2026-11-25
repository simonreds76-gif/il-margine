import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from johnny_cards import lines, utc
from johnny_cards_review import Analyst, AssessmentError, IDLE_SECONDS, choice_schema, exact_choices, read_assessment


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
            replay([heartbeat, heartbeat, b": ping", heartbeat], [5, 100, 310, 606])

    def test_november_25_prefill_pause_and_late_progress(self):
        packets = [frame(prompt_progress={"processed":14055,"total":17156}),
                   b": ping", frame(prompt_progress={"processed":16103,"total":17156}),
                   chunk("{}", "stop"), b"data: [DONE]"]
        self.assertEqual(replay(packets, [278, 580, 586, 589, 590]), {})
        self.assertEqual(replay(packets, [1, 100, 601, 602, 603]), {})

    def test_bounded_player_selection_and_runtime_validation(self):
        schema = choice_schema(22,4)
        self.assertEqual(schema["maxItems"],4)
        self.assertTrue(schema["uniqueItems"])
        players=list(range(22))
        for valid in ([],[3,7,0,21]):
            self.assertEqual(exact_choices(valid,players,4),valid)
        for bad in ([0,1,2,3,4], [3,3], [22], [True], [-1], None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                exact_choices(bad,players,4)

    def test_silent_socket_releases_worker_and_next_fixture_can_start(self):
        analyst = Analyst(None)
        child = MagicMock()
        analyst.child = child
        good = MagicMock()
        good.__enter__.return_value.iter_lines.return_value=[chunk("{}", "stop"), b"data: [DONE]"]
        with patch.object(analyst.http,"post",side_effect=[requests.ReadTimeout(), good]) as post:
            with self.assertRaises(AssessmentError):
                analyst.ask("first",{}, {},32)
            child.terminate.assert_called_once()
            self.assertIsNone(analyst.child)
            with patch.object(analyst,"start") as start:
                self.assertEqual(analyst.ask("next",{}, {},32),{})
                start.assert_called_once()
            self.assertGreater(post.call_args.kwargs["timeout"][1],308)
            self.assertEqual(post.call_args.kwargs["timeout"][1],IDLE_SECONDS)

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
            value = analyst.ask("Return just the one supplied player index in the players array.", {"index":17},
                                {"type":"object","properties":{"players":choice_schema(22,4)},
                                 "required":["players"],"additionalProperties":False}, 32)
        if exact_choices(value["players"],list(range(22)),4) != [17]:
            raise SystemExit("Wrong streamed answer")
    finally:
        analyst.__exit__(None,None,None)
