"""40+ Question Benchmark Evaluation Suite for JKLU Admissions Knowledge Base.
Tests retrieval correctness, source citation accuracy, and zero-hallucination refusal guards.
"""
from typing import Dict, Any, List

BENCHMARK_QUESTIONS: List[Dict[str, Any]] = [
    # --- 1. B.Tech Scholarships & Criteria (In-Scope) ---
    {
        "id": "q01",
        "query": "What is the scholarship for B.Tech if I scored 96 percentile in JEE Mains?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "btech_scholarship"
    },
    {
        "id": "q02",
        "query": "Can I get a 100% scholarship in B.Tech, and what is the requirement?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "btech_scholarship"
    },
    {
        "id": "q03",
        "query": "What scholarship will I get in B.Tech with 92% in 12th class?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "btech_scholarship"
    },
    {
        "id": "q04",
        "query": "What are the specified subjects for B.Tech 12th percentage calculation?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "btech_scholarship"
    },
    {
        "id": "q05",
        "query": "What happens if a B.Tech applicant scores between 50 and 55 in Math?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "scholarship_rules"
    },
    {
        "id": "q06",
        "query": "I passed 12th in 2024, am I eligible for JKLU scholarships?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "scholarship_rules"
    },
    {
        "id": "q07",
        "query": "What CUET score is needed for a 50% scholarship in B.Tech?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "btech_scholarship"
    },

    # --- 2. BBA Scholarships & Eligibility (In-Scope) ---
    {
        "id": "q08",
        "query": "What is the scholarship criteria for BBA based on 12th percentage?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bba_scholarship"
    },
    {
        "id": "q09",
        "query": "What is the minimum 12th marks percentage required for BBA admission?",
        "expected_answer_found": True,
        "expected_source": "admissions_and_eligibility.md",
        "category": "bba_eligibility"
    },
    {
        "id": "q10",
        "query": "Does BBA consider Physical Education or Informatics Practices in 12th percentage?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bba_scholarship"
    },
    {
        "id": "q11",
        "query": "What is the CUET score requirement for a 30% scholarship in BBA?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bba_scholarship"
    },

    # --- 3. B.Des Scholarships & Design Exams (In-Scope) ---
    {
        "id": "q12",
        "query": "How are scholarships awarded for B.Des students?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bdes_scholarship"
    },
    {
        "id": "q13",
        "query": "What scholarship do I get if I score 92 percentile in JK-DET and 4.5 in portfolio?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bdes_scholarship"
    },
    {
        "id": "q14",
        "query": "If I only score 4 in portfolio but less than 90 in JK-DET, do I get any scholarship in B.Des?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bdes_scholarship"
    },
    {
        "id": "q15",
        "query": "Is there a scholarship for UCEED, NID, or NIFT entrance exam ranks at JKLU?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "bdes_scholarship"
    },

    # --- 4. Sibling Discount & Continuation Policy (In-Scope) ---
    {
        "id": "q16",
        "query": "Is there a sibling or alumni discount at JKLU?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "discounts"
    },
    {
        "id": "q17",
        "query": "Can an already enrolled sibling avail the 20% alumni sibling discount?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "discounts"
    },
    {
        "id": "q18",
        "query": "Can I combine my 12th marks scholarship with the sibling discount?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "scholarship_rules"
    },
    {
        "id": "q19",
        "query": "How do I maintain my scholarship in second year?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "continuation"
    },
    {
        "id": "q20",
        "query": "What is the minimum CGPA required to retain scholarship after first year?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "continuation"
    },
    {
        "id": "q21",
        "query": "What scholarship percentage will I get in 2nd year if my CGPA is 9.2?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "continuation"
    },
    {
        "id": "q22",
        "query": "Do scholarships apply to hostel and mess fees?",
        "expected_answer_found": True,
        "expected_source": "scholarships.md",
        "category": "scholarship_rules"
    },

    # --- 5. Program Fees & Cost Structure (In-Scope) ---
    {
        "id": "q23",
        "query": "What is the annual tuition fee for B.Tech Computer Science Engineering?",
        "expected_answer_found": True,
        "expected_source": "programs_and_fees.md",
        "category": "fees"
    },
    {
        "id": "q24",
        "query": "What is the fee for BBA per year at JKLU?",
        "expected_answer_found": True,
        "expected_source": "programs_and_fees.md",
        "category": "fees"
    },
    {
        "id": "q25",
        "query": "What is the annual academic fee for Bachelor of Design (B.Des)?",
        "expected_answer_found": True,
        "expected_source": "programs_and_fees.md",
        "category": "fees"
    },
    {
        "id": "q26",
        "query": "How much is the one-time caution deposit and is it refundable?",
        "expected_answer_found": True,
        "expected_source": "programs_and_fees.md",
        "category": "fees"
    },
    {
        "id": "q27",
        "query": "What are the hostel room charges for double occupancy air-cooled room?",
        "expected_answer_found": True,
        "expected_source": "programs_and_fees.md",
        "category": "hostel_fees"
    },
    {
        "id": "q28",
        "query": "What are the charges for an AC hostel room?",
        "expected_answer_found": True,
        "expected_source": "programs_and_fees.md",
        "category": "hostel_fees"
    },

    # --- 6. Admissions Eligibility, Process & Deadlines (In-Scope) ---
    {
        "id": "q29",
        "query": "What is the eligibility criteria for B.Tech admission at JKLU?",
        "expected_answer_found": True,
        "expected_source": "admissions_and_eligibility.md",
        "category": "btech_eligibility"
    },
    {
        "id": "q30",
        "query": "What is the step by step admission process for prospective students?",
        "expected_answer_found": True,
        "expected_source": "admissions_and_eligibility.md",
        "category": "admission_process"
    },
    {
        "id": "q31",
        "query": "What is the last date to apply in Round 1 early bird admissions?",
        "expected_answer_found": True,
        "expected_source": "admissions_and_eligibility.md",
        "category": "dates"
    },
    {
        "id": "q32",
        "query": "What is the refund policy if I cancel my admission before classes start?",
        "expected_answer_found": True,
        "expected_source": "admissions_and_eligibility.md",
        "category": "refund_policy"
    },

    # --- 7. Campus Facilities, Placements & Location (In-Scope) ---
    {
        "id": "q33",
        "query": "Where is the JKLU campus located?",
        "expected_answer_found": True,
        "expected_source": "campus_and_facilities.md",
        "category": "campus"
    },
    {
        "id": "q34",
        "query": "What was the highest package and average package for B.Tech CSE?",
        "expected_answer_found": True,
        "expected_source": "campus_and_facilities.md",
        "category": "placements"
    },
    {
        "id": "q35",
        "query": "Who are the top recruiters visiting JKLU for campus placements?",
        "expected_answer_found": True,
        "expected_source": "campus_and_facilities.md",
        "category": "placements"
    },
    {
        "id": "q36",
        "query": "Does JKLU have international collaborations or semester exchange programs?",
        "expected_answer_found": True,
        "expected_source": "campus_and_facilities.md",
        "category": "academics"
    },

    # --- 8. Zero-Hallucination & Out-of-Scope Trap Questions (Must Return answer_found=False) ---
    {
        "id": "q37",
        "query": "Can I get an admission in MBBS or medical college at JKLU?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q38",
        "query": "Do you offer commercial pilot license and aviation training?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q39",
        "query": "Will I get a free laptop or iPad upon joining B.Tech?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q40",
        "query": "Is there a guaranteed research internship at NASA for first year students?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q41",
        "query": "Do you provide free flight tickets for international travel to students?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q42",
        "query": "What is the syllabus and fee structure for Bachelor of Pharmacy (B.Pharm)?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q43",
        "query": "What is the monthly stipend given to all B.Tech students?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    },
    {
        "id": "q44",
        "query": "Can I get a 100% scholarship for BBA through Class 12 marks?",
        "expected_answer_found": True,  # Found because policy states max 50% for BBA
        "expected_source": "scholarships.md",
        "category": "bba_scholarship"
    },
    {
        "id": "q45",
        "query": "Do you have a Dental BDS degree program?",
        "expected_answer_found": False,
        "category": "out_of_scope_trap"
    }
]


def run_benchmark_evaluation():
    """Run all benchmark queries against the retrieval engine and compute metrics."""
    from app.intel.retrieval import store

    total = len(BENCHMARK_QUESTIONS)
    passed = 0
    in_scope_total = 0
    in_scope_passed = 0
    trap_total = 0
    trap_passed = 0
    failures = []

    for item in BENCHMARK_QUESTIONS:
        qid = item["id"]
        query = item["query"]
        expected_found = item["expected_answer_found"]
        expected_src = item.get("expected_source")

        result = store.search(query)
        is_pass = False

        if not expected_found:
            trap_total += 1
            if not result.answer_found:
                is_pass = True
                trap_passed += 1
            else:
                failures.append({
                    "id": qid,
                    "query": query,
                    "reason": "Expected answer_found=False (hallucination guard), but retrieved chunks",
                    "got_chunks": [c.source for c in result.chunks]
                })
        else:
            in_scope_total += 1
            if result.answer_found:
                if expected_src:
                    sources = [c.source for c in result.chunks]
                    if any(expected_src in s for s in sources):
                        is_pass = True
                        in_scope_passed += 1
                    else:
                        failures.append({
                            "id": qid,
                            "query": query,
                            "reason": f"Expected source {expected_src}, got {sources}",
                        })
                else:
                    is_pass = True
                    in_scope_passed += 1
            else:
                failures.append({
                    "id": qid,
                    "query": query,
                    "reason": "Expected answer_found=True, but system returned answer_found=False"
                })

        if is_pass:
            passed += 1

    accuracy = (passed / total) * 100.0
    in_scope_acc = (in_scope_passed / in_scope_total * 100.0) if in_scope_total else 0.0
    guard_acc = (trap_passed / trap_total * 100.0) if trap_total else 0.0

    return {
        "total_questions": total,
        "passed": passed,
        "accuracy_percent": round(accuracy, 2),
        "in_scope_accuracy_percent": round(in_scope_acc, 2),
        "zero_hallucination_guard_accuracy_percent": round(guard_acc, 2),
        "failures": failures
    }
