"""Unit tests for the deterministic answer verifiers."""
from app.agent.verify import (NOT_IN_KB, TurnEvidence, check_booking, check_figures, check_grounding, check_no_false_grant,
                              check_outbound, citations)
from app.contracts.models import BookingResult, Chunk, KnowledgeResult, Slot

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
