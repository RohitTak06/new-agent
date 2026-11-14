"""Unit tests for the deterministic answer verifiers."""
from app.agent.verify import (NOT_IN_KB, TurnEvidence, check_booking, check_figures, check_grounding, check_no_false_grant,
                              check_outbound, citations)
from app.contracts.models import ApprovalRequest, BookingResult, CancelResult, Chunk, CounsellorInfo, KnowledgeResult, Slot

SRC = "programs_and_fees.md#bachelor-of-technology-b-tech"
KB = KnowledgeResult(answer_found=True, chunks=[Chunk(
    source=SRC, score=0.4,
    text="Annual Academic Fee: INR 2,65,000 per year (INR 1,32,500 per semester). Duration: 4 Years",
)])


def ev(*kb, bookings=()):
    return TurnEvidence(knowledge=list(kb), bookings=list(bookings))


def test_citations_extracted_in_order_unique():
    text = f"Fee is INR 2,65,000 [{SRC}]. Again [{SRC}] and [scholarships.md#x]."
    assert citations(text) == [SRC, "scholarships.md#x"]


def test_grounded_answer_passes():
    v = check_grounding(f"The B.Tech fee is INR 2,65,000 per year for 4 years [{SRC}].", ev(KB),
                        "institutional_question")
    assert v.ok, v.reason


def test_number_formats_normalised():
    assert check_grounding(f"INR 265000 a year [{SRC}]", ev(KB), "institutional_question").ok


def test_fabricated_number_fails():
    v = check_grounding(f"The B.Tech fee is INR 3,10,000 per year [{SRC}].", ev(KB), "institutional_question")
    assert not v.ok and v.action == "replan"
    assert v.details["ungrounded_numbers"] == ["310000"]


def test_number_from_student_question_allowed():
    v = check_grounding(f"With 92% in 12th, the fee is still INR 2,65,000 [{SRC}].", ev(KB),
                        "institutional_question", question="I got 92% in 12th, what is the fee?")
    assert v.ok, v.reason


def test_missing_citation_replans():
    v = check_grounding("The fee is INR 2,65,000.", ev(KB), "institutional_question")
    assert not v.ok and v.action == "replan"


def test_unretrieved_source_replans():
    v = check_grounding("Fee INR 2,65,000 [fees_2027.md#cse]", ev(KB), "institutional_question")
    assert not v.ok and v.details["unknown_sources"] == ["fees_2027.md#cse"]


def test_no_kb_result_escalates():
    v = check_grounding("The fee is INR 2,65,000.", ev(KnowledgeResult(answer_found=False, chunks=[])),
                        "institutional_question")
    assert not v.ok and v.action == "escalate"


def test_model_not_in_kb_marker_escalates():
    v = check_grounding(f"{NOT_IN_KB} I don't have that information.", ev(KB), "institutional_question")
    assert not v.ok and v.action == "escalate"


def test_chitchat_needs_no_grounding():
    assert check_grounding("Hello! How can I help?", ev(), "chitchat").ok


SLOT = Slot(slot_id="s2", counsellor="Dr. Sharma", start="2026-11-03T11:00:00", end="2026-11-03T11:30:00")


def test_booking_claim_without_success_fails():
    v = check_booking("Your session is booked for 11:00.", ev(bookings=[BookingResult(ok=False, reason="slot_taken")]))
    assert not v.ok and v.action == "replan"


def test_booking_claim_with_success_passes():
    assert check_booking("Your session is booked.", ev(bookings=[BookingResult(ok=True, slot=SLOT)])).ok


def test_negated_booking_is_not_a_claim():
    assert check_booking("That slot could not be booked; here are alternatives.", ev()).ok


def test_false_grants_are_rejected():
    for text in ("Your fee waiver has been approved.", "I have approved your discount.", "You have been granted a seat.",
                 "You are guaranteed admission.", "Enjoy your free seat!", "I can waive that for you."):
        assert not check_no_false_grant(text).ok, text


def test_honest_wording_is_not_a_false_grant():
    for text in ("I can't approve waivers myself.", "I cannot grant that.", "There is no free seat.",
                 "Your request is pending counsellor approval.", "JKLU is UGC approved.",
                 "Your fee waiver has not been approved yet."):
        assert check_no_false_grant(text).ok, text
    assert check_no_false_grant("Your fee waiver has been approved.", {"fee_waiver"}).ok


def test_figures_need_a_source():
    assert not check_figures("It costs INR 5,00,000 a year.", ev()).ok
    assert not check_figures("You get a 90% scholarship.", ev()).ok
    assert not check_figures("About 3 lakh a year.", ev()).ok
    assert check_figures("It costs INR 2,65,000 a year.", ev(KB)).ok
    assert check_figures("Your 92% and 8 lakh budget are noted.", ev(), "I got 92% and have 8 lakh").ok
    assert check_figures("We have 3 counsellors free.", ev()).ok            # not money or a percentage


def test_outbound_messages_need_every_number_sourced():
    assert not check_outbound("Your fee is INR 1,000", ev()).ok
    assert not check_outbound("Details [made_up.md#x]", ev()).ok
    assert not check_outbound("Your waiver has been approved", ev()).ok
    assert check_outbound(f"The fee is INR 2,65,000 [{SRC}]", ev(KB)).ok
    assert check_outbound("Hello! A counsellor will call you.", ev()).ok
    booked = TurnEvidence(tool_text=["{'start': '2026-11-05T10:00:00+05:30'}"])
    assert check_outbound("Your session is on 2026-11-05 at 10:00", booked).ok


# ---------------------------------------------------------------- several sources in one bracket (seen live)
def test_citations_reads_several_sources_in_one_bracket():
    text = "A fact [a.md#x, b.md#y]. Another [c.md; d.md#z] and [a.md#x]."
    assert citations(text) == ["a.md#x", "b.md#y", "c.md", "d.md#z"]


def test_bracketed_text_that_is_not_a_source_is_not_a_citation():
    assert citations("See [note, a.md#x] and [the fees]") == []


# ---------------------------------------------------------------- an earlier approval only covers its own kind (seen live)
def test_answered_question_does_not_unlock_a_waiver_claim():
    assert not check_no_false_grant("Your fee waiver has been approved.", {"escalate_question"}).ok


def test_booking_override_does_not_unlock_a_waiver_claim():
    assert not check_no_false_grant("Your fee waiver has been approved.", {"booking_override"}).ok


def test_an_approved_waiver_does_not_unlock_a_seat_claim():
    assert not check_no_false_grant("Your seat has been confirmed.", {"fee_waiver"}).ok


def test_answered_question_does_not_unlock_request_approved():
    assert not check_no_false_grant("Your request has been approved.", {"escalate_question"}).ok
    assert check_no_false_grant("Your request has been approved.", {"fee_waiver"}).ok


# ---------------------------------------------------------------- reporting a request (seen live)
def filed(status="pending"):
    return TurnEvidence(approvals=[ApprovalRequest(approval_id=7, status=status, action="fee_waiver")])


def test_a_filed_request_can_be_reported_in_any_wording():
    for text in ("I've sent this to a counsellor to review.", "Request #7 is with a counsellor now."):
        assert check_grounding(text, filed(), "sensitive_request").ok, text


def test_a_figure_beside_a_filed_request_is_reworded_not_escalated():
    verdict = check_grounding("Your fee is INR 2,65,000, and I've sent your request on.", filed(), "sensitive_request")
    assert not verdict.ok and verdict.action == "replan"


def test_status_of_an_earlier_request_needs_no_source():
    evidence = TurnEvidence(request_ids={7})
    assert check_grounding("Request #7 is still with a counsellor.", evidence, "sensitive_request").ok


def test_status_wording_gives_no_pass_outside_sensitive_requests():
    evidence = TurnEvidence(request_ids={7})
    assert not check_grounding("JKLU has a large campus.", evidence, "institutional_question").ok


def test_an_earlier_request_gives_no_pass_for_figures():
    assert not check_grounding("A waiver is worth INR 5,000.", TurnEvidence(request_ids={7}), "sensitive_request").ok


# ---------------------------------------------------------------- promising a scholarship
def test_promising_a_scholarship_is_a_false_grant():
    for text in ("With 96 percentile, you qualify for a 100% scholarship.", "You are eligible for a merit scholarship.",
                 "You will qualify for the 75% scholarship.", "you're eligible for a 50% scholarship",
                 "Your marks fall in that band, which qualifies you for a 30% scholarship."):
        assert not check_no_false_grant(text).ok, text


def test_describing_a_band_is_not_a_grant():
    for text in ("A 96 percentile falls in the 100% scholarship band.", "If you qualify for a scholarship, a counsellor confirms it.",
                 "A counsellor can check whether you qualify for a scholarship.", "You may qualify for a scholarship."):
        assert check_no_false_grant(text).ok, text


# --- booking words in sentences that are not about a session -----------------------------------------
import pytest  # noqa: E402


@pytest.mark.parametrize("answer", [
    "The B.Tech fee is INR 3,40,000 as confirmed on the official fee page [programs_and_fees.md#b-tech].",
    "Seats are reserved for Rajasthan domicile students.",
    "Classes are scheduled to begin in August.",
    "I've scheduled a follow-up reminder for you.",
])
def test_a_booking_word_outside_a_session_sentence_is_not_a_claim(answer):
    assert check_booking(answer, ev()).ok


@pytest.mark.parametrize("answer", [
    "Your counselling session is confirmed.",
    "You're booked with Ms. Rekha Verma.",
    "Done! Confirmed for 3 pm tomorrow.",
    "Great news. I have booked it for Tuesday at 10:00.",
])
def test_a_session_claim_without_a_booking_is_caught(answer):
    assert not check_booking(answer, ev()).ok


# ---------------------------------------------------------------- school years aren't figures (seen live)
def test_a_school_year_is_not_an_invented_figure():
    for text in (f"The fee is INR 2,65,000 per year for students who passed Class 12 [{SRC}].",
                 f"You need good 12th marks; the fee is INR 2,65,000 [{SRC}].",
                 f"After Class 10 and Class 12th, the fee is INR 2,65,000 [{SRC}]."):
        assert check_grounding(text, ev(KB), "institutional_question").ok, text


def test_invented_figures_beside_a_school_year_still_fail():
    for text in (f"Class 12 students pay INR 12,000 extra [{SRC}].",
                 f"Classes start on 12th March; the fee is INR 2,65,000 [{SRC}].",
                 f"You get 12 free credits and the fee is INR 2,65,000 [{SRC}]."):
        verdict = check_grounding(text, ev(KB), "institutional_question")
        assert not verdict.ok and verdict.details["ungrounded_numbers"], text


# ---------------------------------------------------------------- cancellations (seen live: claimed with no cancel tool)
@pytest.mark.parametrize("answer", [
    "Your 10:00 AM counselling session has been cancelled.",
    "I've deleted your booking with Ms. Rekha Verma.",
    "Your slot has been released.",
])
def test_a_cancellation_claim_without_cancel_booking_is_caught(answer):
    v = check_booking(answer, ev())
    assert not v.ok and v.action == "replan"


def test_a_cancellation_claim_after_cancel_booking_passes():
    evidence = ev()
    evidence.cancellations.append(CancelResult(ok=True, slot=SLOT))
    assert check_booking("Your counselling session has been cancelled.", evidence).ok


def test_a_negated_or_unrelated_cancellation_is_not_a_claim():
    assert check_booking("Your session could not be cancelled right now.", ev()).ok
    assert check_booking("Results are released in June.", ev()).ok


# ---------------------------------------------------------------- counsellor questions (seen live: "who is Sunil Mathur" escalated)
COUNSELLORS = [CounsellorInfo(name="Mr. Sunil Mathur", next_free="2026-11-16T11:00:00+05:30")]


def counsellor_ev():
    evidence = ev()
    evidence.counsellors = list(COUNSELLORS)
    evidence.tool_text = [str([c.model_dump() for c in COUNSELLORS])]
    return evidence


def test_a_counsellor_answer_from_the_counsellor_list_is_grounded():
    answer = "Mr. Sunil Mathur is one of our admissions counsellors. His next free session is Mon, 16 Nov at 11:00 am."
    assert check_grounding(answer, counsellor_ev(), "institutional_question", "who is Sunil Mathur").ok


def test_a_counsellor_answer_with_an_invented_number_is_not():
    answer = "Mr. Sunil Mathur is one of our counsellors, with 15 years of experience."
    assert not check_grounding(answer, counsellor_ev(), "institutional_question", "who is Sunil Mathur").ok


def test_a_person_who_is_not_a_counsellor_still_escalates():
    v = check_grounding("Rahul Gupta is our Dean of Engineering.", counsellor_ev(), "institutional_question", "who is Rahul Gupta")
    assert not v.ok and v.action == "escalate"
