"""Unit tests for the deterministic answer verifiers."""
from app.agent.verify import NOT_IN_KB, TurnEvidence, check_booking, check_grounding, citations
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
