"""Tests for the parts that decide what ends up in the result.

None of these need a model or a video, so the whole file runs in well under a
second. What is pinned here are the promises this tool makes: existing files are
never overwritten, the timeline is in order, and a screen that has not changed
is not written down twice.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_to_text.core.output import build_srt, build_txt, free_name
from video_to_text.core.screen import (
    FINGERPRINT_SIDE,
    frame_difference,
    numbers_in,
    same_screen,
    tidy_text,
)
from video_to_text.core.settings import ALL_QUALITIES, FAST, THOROUGH, find_quality
from video_to_text.core.timeline import HEARD, SHOWN, Line, clock, merge

DOTS = FINGERPRINT_SIDE * FINGERPRINT_SIDE


class Segment:
    """Stands in for either a speech segment or a screen segment."""

    def __init__(self, start, end, text):
        self.start, self.end, self.text = start, end, text


# --- the timeline ---------------------------------------------------------

def test_result_is_ordered_by_time():
    speech = [Segment(5.0, 6.0, "second sentence"), Segment(1.0, 2.0, "first sentence")]
    screen = [Segment(3.0, 4.0, "text in between")]

    lines = merge(speech, screen)

    assert [line.text for line in lines] == [
        "first sentence", "text in between", "second sentence",
    ]
    assert [line.start for line in lines] == sorted(line.start for line in lines)


def test_speech_comes_first_when_both_start_together():
    lines = merge([Segment(2.0, 3.0, "spoken")], [Segment(2.0, 3.0, "shown")])
    assert [line.source for line in lines] == [HEARD, SHOWN]


def test_each_line_is_labelled_with_where_it_came_from():
    lines = merge([Segment(0.0, 1.0, "hello")], [Segment(0.0, 1.0, "title")])
    body = build_txt(lines, "sample.mp4", "summary")
    assert "[SPEECH] hello" in body
    assert "[SCREEN] title" in body


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "00:00:00,000"),
        (1.5, "00:00:01,500"),
        (61.25, "00:01:01,250"),
        (3661.0, "01:01:01,000"),
        (-5, "00:00:00,000"),
        (1.9999, "00:00:02,000"),
    ],
)
def test_clock_formatting(seconds, expected):
    assert clock(seconds) == expected


# --- the output files -----------------------------------------------------

def test_an_existing_file_is_never_overwritten(tmp_path):
    existing = tmp_path / "video.txt"
    existing.write_text("work that matters", encoding="utf-8")

    chosen = free_name(existing)

    assert chosen != existing
    assert not chosen.exists()
    assert existing.read_text(encoding="utf-8") == "work that matters"


def test_the_name_keeps_climbing_on_repeated_runs(tmp_path):
    for name in ("video.txt", "video (2).txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert free_name(tmp_path / "video.txt").name == "video (3).txt"


def test_srt_is_shaped_the_way_a_player_expects():
    lines = [Line(1.0, 2.5, HEARD, "hello everyone"), Line(3.0, 3.0, SHOWN, "title")]
    body = build_srt(lines).splitlines()

    assert body[0] == "1"
    assert body[1] == "00:00:01,000 --> 00:00:02,500"
    assert body[2] == "[SPEECH] hello everyone"
    # a subtitle with no duration never appears, so it is given the shortest one
    assert body[5] == "00:00:03,000 --> 00:00:03,500"


def test_txt_says_plainly_that_the_result_is_only_an_estimate():
    body = build_txt([], "sample.mp4", "summary")
    assert "best guess" in body.lower()
    assert "no speech or screen text could be read" in body


# --- not writing the same screen twice ------------------------------------

def test_an_unchanged_frame_is_recognised():
    fingerprint = [100] * DOTS
    assert frame_difference(fingerprint, fingerprint) == 0.0


def test_a_completely_different_frame_is_recognised():
    assert frame_difference([0] * DOTS, [255] * DOTS) == pytest.approx(1.0)


def test_the_first_frame_always_counts_as_changed():
    assert frame_difference(None, [10] * DOTS) == 1.0


def test_a_change_in_one_small_tile_is_still_seen():
    """The heart of how frames are compared: a counter changes one patch only.

    Averaged over the whole screen a change this small measures 0.0001 and
    disappears. Taking the most-changed tile instead keeps it plainly visible.
    """
    still = [120] * DOTS
    changed = list(still)
    for row in range(8):  # one 8x8 tile in the top-left corner changes completely
        for column in range(8):
            changed[row * FINGERPRINT_SIDE + column] = 255

    averaged = sum(abs(a - b) for a, b in zip(still, changed)) / (DOTS * 255)
    by_tile = frame_difference(still, changed)

    assert averaged < 0.003, "averaged out, this change is nearly invisible"
    assert by_tile > 0.5, "by tile, the same change is obvious"
    assert by_tile > averaged * 100, "hundreds of times apart"


def test_default_thresholds_sit_below_real_measured_change():
    """The 0.003 figure comes from measuring actual screen recordings."""
    for quality in ALL_QUALITIES:
        assert 0 < quality.min_frame_change <= 0.003


def test_the_same_words_with_different_spacing_count_as_the_same():
    assert same_screen("Hello   World", "hello world")


def test_one_misread_letter_still_counts_as_the_same_screen():
    right = "Pick the source and target folders, then press Start Copy right now please"
    misread = "Pick the source and target folders, then press Start Capy right now please"
    assert same_screen(right, misread)


def test_a_letter_misread_as_a_digit_is_deliberately_treated_as_different():
    """A trade-off made with open eyes: OCR sometimes reads the letter l as 1.

    Since digits are what mark a change, a misreading like that produces one
    duplicate line. That was chosen on purpose: a spare line costs less than a
    changed number vanishing without trace.
    """
    assert not same_screen("press Start Copy all", "press Start Copy a1l")


def test_genuinely_different_screens_are_not_merged():
    assert not same_screen("Copying the first file", "Finished without errors")


def test_a_climbing_counter_is_recorded_as_a_new_screen():
    """Taken from a real test video: the counter climbs, everything else holds still.

    Without the digit rule a change like this is swallowed, because 95 percent of
    the text is identical, when the number is the very thing worth recording.
    """
    before = "Preparing to copy from Local Disk (E:) to Local Disk (D:)\nDiscovered 1.912 items (1,56GB)"
    after = "Preparing to copy from Local Disk (E:) to Local Disk (D:)\nDiscovered 8.046 items (5,23GB)"
    assert not same_screen(before, after)


def test_digits_are_read_without_their_grouping_marks():
    assert numbers_in("Discovered 8.046 items (5,23GB)") == ["8046", "523"]


def test_a_changing_countdown_also_counts_as_a_new_screen():
    assert not same_screen("Time remaining: 2 minutes", "Time remaining: 1 minutes")


def test_empty_ocr_lines_are_dropped():
    assert tidy_text(["  ", "Line one", "", "Line two  "]) == "Line one\nLine two"


# --- the quality presets --------------------------------------------------

def test_thorough_works_harder_than_fast():
    assert THOROUGH.frame_interval_seconds < FAST.frame_interval_seconds
    assert THOROUGH.min_frame_change < FAST.min_frame_change
    assert THOROUGH.beam_size > FAST.beam_size


def test_every_preset_uses_a_model_the_app_ships():
    # The packaged app downloads nothing, so a preset naming a model that is
    # not in the bundle would fail on every user's machine.
    from video_to_text.core import speech

    for quality in (FAST, THOROUGH):
        assert speech.model_available(quality.speech_model), quality.speech_model


def test_an_unknown_preset_is_refused():
    with pytest.raises(ValueError):
        find_quality("very-thorough")


# --- writing only what is new on screen ----------------------------------------

from video_to_text.core.screen import new_lines  # noqa: E402


def test_a_title_that_stays_on_screen_is_not_repeated():
    before = "Can AI find Apple's hidden rule?\nTHERE'S A GITHUB PROJECT"
    after = "Can AI find Apple's hidden rule?\nVIRAL"
    assert new_lines(after, before) == "VIRAL"


def test_a_line_read_slightly_differently_is_still_recognised():
    before = "Can Al find Apple's hidden rule?"
    after = "Can AI find Apples hidden rule?\nSHORT FOR REVERSE"
    assert new_lines(after, before) == "SHORT FOR REVERSE"


def test_a_changed_number_is_written_again():
    before = "Discovered 8,046 items"
    after = "Discovered 8,312 items"
    assert new_lines(after, before) == "Discovered 8,312 items"


def test_a_completely_new_screen_is_written_whole():
    assert new_lines("Bab 2\nRumus umur", "Bab 1\nPendahuluan") == "Bab 2\nRumus umur"


def test_the_latin_ocr_model_ships_with_the_app():
    from video_to_text.core.screen import latin_model_path

    assert latin_model_path().is_file()


def test_counts_agree_with_their_noun():
    from video_to_text.core.pipeline import counted

    assert counted(1, "piece") == "1 piece"
    assert counted(3, "piece") == "3 pieces"
    assert counted(1, "entry", "entries") == "1 entry"
    assert counted(0, "entry", "entries") == "0 entries"
