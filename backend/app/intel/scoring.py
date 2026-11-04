"""Lead Qualification and Scoring Engine for JKLU Admissions.
Evaluates profile completeness, academics, budget and engagement signals.

Reasons describe the student's profile only. They never state institutional facts
(scholarship bands, costs, cutoffs): those come from the knowledge base, with citations.
"""
import re
from typing import List
from app.contracts.models import LeadProfile, LeadScore


def score_lead(profile: LeadProfile) -> LeadScore:
    """Calculates lead score (0-100), tier (hot/warm/cold), and transparent reasons."""
    score = 0
    reasons: List[str] = []

    # 1. Academic Strength & Scholarship Mapping (Max 35 points)
    if profile.twelfth_percent is not None:
        pct = profile.twelfth_percent
        if pct >= 95.0:
            score += 35
            reasons.append(f"Outstanding 12th marks ({pct:.1f}%)")
        elif pct >= 90.0:
            score += 30
            reasons.append(f"High 12th marks ({pct:.1f}%)")
        elif pct >= 80.0:
            score += 24
            reasons.append(f"Strong 12th marks ({pct:.1f}%)")
        elif pct >= 65.0:
            score += 18
            reasons.append(f"Good 12th marks ({pct:.1f}%)")
        elif pct >= 55.0:
            score += 12
            reasons.append(f"Moderate 12th marks ({pct:.1f}%)")
        else:
            score += 5
            reasons.append(f"Lower 12th marks ({pct:.1f}%): eligibility needs checking")
    else:
        reasons.append("Academic 12th percentage not yet disclosed")

    # Entrance Exam assessment (Bonus up to 10 points)
    if profile.entrance_exam:
        ee = profile.entrance_exam.lower()
        # Look for numbers/percentiles
        # Scores only: a percentile is at most 100, so "JEE Main 2026" is not a score
        nums = [n for n in map(float, re.findall(r"\d+(?:\.\d+)?", ee)) if n <= 100]
        if "jee" in ee and any(n >= 90 for n in nums):
            score += 10
            reasons.append(f"High JEE Main score ({profile.entrance_exam})")
        elif "jee" in ee or "cuet" in ee or "jk-det" in ee or "uceed" in ee:
            score += 8
            reasons.append(f"Entrance exam reported ({profile.entrance_exam}): candidate ready for counselling")

    # 2. Program Intent (Max 20 points)
    if profile.program_interest:
        score += 20
        reasons.append(f"Explicit program interest declared: {profile.program_interest}")
    else:
        score += 5
        reasons.append("Program interest still undecided or exploratory")

    # 3. Contact & Reachability (Max 20 points)
    has_phone = bool(profile.phone and len(profile.phone.strip()) >= 10)
    has_email = bool(profile.email and "@" in profile.email)

    if has_phone and has_email:
        score += 20
        reasons.append("High reachability: both valid phone and email provided")
    elif has_phone:
        score += 14
        reasons.append("Direct phone number provided for WhatsApp / call outreach")
    elif has_email:
        score += 10
        reasons.append("Email address provided for nurture communications")
    else:
        reasons.append("Incomplete contact details; anonymous visitor")

    # 4. Budget & Financial Viability (Max 15 points)
    if profile.budget_lakh is not None:
        b = profile.budget_lakh
        if b >= 8.0:
            score += 15
            reasons.append(f"Higher stated budget ({b:.1f} lakh)")
        elif b >= 4.0:
            score += 12
            reasons.append(f"Moderate stated budget ({b:.1f} lakh)")
        else:
            score += 6
            reasons.append(f"Lower stated budget ({b:.1f} lakh)")
    else:
        score += 8  # Neutral baseline
        reasons.append("Budget not disclosed; neutral assessment")

    # 5. High Intent Signals (Max 10 points)
    if profile.asked_scholarship:
        score += 8
        reasons.append("High buying intent: actively asked about scholarship schemes")

    if profile.channel in ("whatsapp", "web"):
        score += 2

    # Final clamping
    final_score = min(100, max(0, score))

    # Tier assignment
    if final_score >= 75:
        tier = "hot"
    elif final_score >= 50:
        tier = "warm"
    else:
        tier = "cold"

    return LeadScore(
        score=final_score,
        tier=tier,
        reasons=reasons
    )
