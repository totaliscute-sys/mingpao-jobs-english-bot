#!/usr/bin/env python3
"""
Local logic tests for the job-filtering pipeline.

These run WITHOUT any network / Telegram / secrets — they only exercise the
pure classification functions against real job titles that appeared in the
GitHub Actions run log, to lock in the behaviour we want:

  * APSM (助理小學學位教師) English posts are ACCEPTED
  * Teaching-assistant / 支援教師 / NET / substitute posts are REJECTED
  * A generic post that merely *requires* English is NOT treated as English-subject
"""

import mingpao_jobs as m


def classify(title, school="", content=""):
    """Run a job through the same gates verify_jobs() uses, return (accepted, reason)."""
    is_teaching, why = m.is_teaching_role(title, content)
    if not is_teaching:
        return False, f"non-teaching ({why})"

    is_support, kw = m.is_support_role(title)
    if is_support:
        return False, f"support/TA ({kw})"

    if any(k in title.lower() for k in m.SUBSTITUTE_KEYWORDS):
        return False, "substitute"

    if not m.is_confirmed_primary_school(school, content, title):
        return False, "not-primary"

    if m.is_social_service_org(school) and school:
        return False, "social-service"

    is_eng, eng_why = m.is_english_subject(title, content)
    if not is_eng:
        return False, f"not-english ({eng_why})"

    return True, eng_why


# (title, school, content, expected_accept)
CASES = [
    # --- should be ACCEPTED: APSM / degree English-subject primary posts ---
    ("助理小學學位教師 (英文科) (2026/27 學年)", "官立小學", "", True),
    ("常額助理小學學位教師 (英文科) (2026/2027 年度)", "天主教小學", "", True),
    ("助理小學學位教師 APSM (2026/27)", "聖博德天主教小學",
     "本校為一所津貼小學，現誠聘助理小學學位教師一名，任教英文科，"
     "須具備認可大學學位及小學師資訓練，並通過《基本法及香港國安法》測試。"
     "申請人須負責課堂教學、評估學生及班主任工作。有意者請將履歷電郵至本校。" * 2, True),

    # --- should be REJECTED: teaching assistant / support roles ---
    ("支援教師 / 教學助理 (9 月到職)", "某小學",
     "Applicants should have a good command of written and spoken English.", False),
    ("教學助理 TA", "某小學", "", False),
    ("English Language Associate Teacher", "某小學", "", False),
    ("英文科教學助理", "某小學", "", False),
    ("Full-time English Teaching Assistant (NT)", "某小學", "", False),

    # --- should be REJECTED: NET / 外籍 ---
    ("Full-time Native-speaking English Teacher", "某小學", "", False),
    ("Substitute Teacher (NET) (Maternity Leave)", "某小學", "", False),

    # --- should be REJECTED: substitute / 代課 ---
    ("日薪代課教師 (地理科) (2026-2027 學年)", "某小學", "", False),

    # --- should be REJECTED: wrong subject ---
    ("中文科教師 (合約) 一名", "某小學", "", False),
    ("數學科合約教師", "某小學", "", False),
    ("香港課程小學教師 - 數學、英國語文、視覺藝術", "某小學", "", False),

    # --- should be REJECTED: secondary school ---
    ("英文科教師", "某中學", "", False),

    # --- generic teacher whose content only *requires* English -> NOT english ---
    ("助理小學學位教師 (2026/27)", "某小學",
     "Requirements: degree holder with good command of English and Chinese.", False),
]


def main():
    passed = failed = 0
    for title, school, content, expected in CASES:
        accepted, reason = classify(title, school, content)
        ok = accepted == expected
        mark = "✓" if ok else "✗ FAIL"
        verdict = "ACCEPT" if accepted else "reject"
        print(f"{mark}  [{verdict:6}] {title[:46]:46}  ({reason})")
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"        expected {'ACCEPT' if expected else 'reject'}")
    print("-" * 70)
    print(f"{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
