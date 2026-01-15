"""
Merge processor - refactored from merge_marking_schemes.py
Merges marking schemes into questions JSON
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_question_reference(ref: str) -> Tuple[Optional[int], List[str]]:
    """
    Parse a question reference like '1(a)', '1(c)(i)', '4a(i)', 'A1(a)', 'B4(a)' into components.

    Returns:
        tuple: (question_number, part_labels)
        Example: '1(c)(i)' -> (1, ['c', 'i'])
                 '4a(i)' -> (4, ['a', 'i'])
                 'A1(a)' -> (1, ['a'])  - A prefix stripped
                 'B4(a)' -> (4, ['a'])  - B prefix stripped
    """
    # Handle formats like '4a(i)' or 'A4a(i)' by adding missing parentheses
    ref = re.sub(r'^([AB]?\d+)([a-z])\(', r'\1(\2)(', ref)

    # Try to extract question number with optional A/B prefix
    # Both A and B prefixes are stripped: A1 -> 1, B4 -> 4
    match = re.match(r'^[AB]?(\d+)', ref)
    if not match:
        return None, []

    question_num = int(match.group(1))

    # Extract part labels
    part_labels = re.findall(r'\(([a-z]+|i{1,3}|iv|v|vi{0,3})\)', ref, re.IGNORECASE)

    return question_num, [label.lower() for label in part_labels]


def find_part_by_label(parts: List[Dict], label: str) -> Optional[Dict]:
    """Find a part in a list by its label"""
    for part in parts:
        if part.get('partLabel') == label:
            return part
    return None


def set_marking_scheme(questions: List[Dict], ref: str, marking_scheme: str) -> bool:
    """
    Set the marking scheme for a specific question part.

    Args:
        questions: List of question dictionaries
        ref: Question reference like '1(a)' or '1(c)(i)'
        marking_scheme: The marking scheme text to set

    Returns:
        bool: True if successful, False otherwise
    """
    question_num, part_labels = parse_question_reference(ref)

    if question_num is None:
        return False

    # Find the question
    question = None
    for q in questions:
        if q.get('questionNumber') == question_num:
            question = q
            break

    if not question:
        return False

    # Navigate through the part hierarchy
    current_parts = question['parts']
    current_part = None

    for i, label in enumerate(part_labels):
        part = find_part_by_label(current_parts, label)

        if not part:
            return False

        current_part = part

        # If there are more labels, navigate deeper
        if i < len(part_labels) - 1:
            current_parts = part.get('parts', [])

    # Set the marking scheme
    if current_part:
        current_part['markingScheme'] = marking_scheme
        return True

    return False


def merge_marking_schemes_into_questions(
    questions: List[Dict],
    marking_schemes: Dict[str, str]
) -> Tuple[List[Dict], Dict[str, any]]:
    """
    Merge marking schemes into questions.

    Args:
        questions: List of questions
        marking_schemes: Dictionary of marking schemes

    Returns:
        Tuple of (updated_questions, merge_stats)
    """
    # Track statistics
    successful = 0
    failed = 0
    failed_refs = []

    # Merge each marking scheme
    for ref, scheme in marking_schemes.items():
        if set_marking_scheme(questions, ref, scheme):
            successful += 1
        else:
            failed += 1
            failed_refs.append(ref)

    # Calculate coverage
    total_parts = 0
    parts_with_schemes = 0

    def count_parts(parts):
        nonlocal total_parts, parts_with_schemes
        for part in parts:
            # Only count parts that have marks (actual question parts, not containers)
            if part.get('marks') is not None:
                total_parts += 1
                if part.get('markingScheme'):
                    parts_with_schemes += 1
            # Still recurse into nested parts
            if part.get('parts'):
                count_parts(part['parts'])

    for question in questions:
        count_parts(question['parts'])

    merge_stats = {
        "successful": successful,
        "failed": failed,
        "failed_refs": failed_refs,
        "total_parts": total_parts,
        "parts_with_schemes": parts_with_schemes,
        "coverage_percentage": (parts_with_schemes / total_parts * 100) if total_parts > 0 else 0
    }

    return questions, merge_stats


def merge_files(
    questions_file: Path,
    marking_schemes_file: Path,
    output_file: Path
) -> Tuple[List[Dict], Dict[str, any]]:
    """
    Main function to merge marking schemes into questions.

    Args:
        questions_file: Path to questions JSON file
        marking_schemes_file: Path to marking schemes JSON file
        output_file: Path to output merged JSON file

    Returns:
        Tuple of (merged_questions, merge_stats)
    """
    # Load questions
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    # Load marking schemes
    with open(marking_schemes_file, 'r', encoding='utf-8') as f:
        marking_schemes = json.load(f)

    # Merge
    merged_questions, merge_stats = merge_marking_schemes_into_questions(
        questions, marking_schemes
    )

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_questions, f, indent=2, ensure_ascii=False)

    return merged_questions, merge_stats
