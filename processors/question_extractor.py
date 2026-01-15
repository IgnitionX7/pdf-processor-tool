"""
Question extraction processor - refactored from questions_extractor_cd.py
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any


def extract_marks(text: str) -> Optional[int]:
    """Extract marks from text like [2] or [1]"""
    match = re.search(r'\[(\d+)\]', text)
    return int(match.group(1)) if match else None


def extract_total_marks(text: str) -> Optional[int]:
    """Extract total marks from text like [Total: 9]"""
    match = re.search(r'\[Total:\s*(\d+)\]', text)
    return int(match.group(1)) if match else None


def is_question_start(line: str) -> bool:
    """Check if line starts a new question (e.g., '1 ', '2 ', 'A1 ', 'B1 ', etc.)"""
    # Pattern 1: Plain number - single digit (1-9) or two digits (10-99) followed by space
    # Then either:
    # - A capital letter (start of sentence)
    # - Fig (figure reference)
    # - Part marker like (a), (b)
    # This avoids matching things like "0 time", "80 cm", "50 ms"
    plain_number = re.match(r'^([1-9]|1[0-9])\s+([A-Z]|Fig|\([a-z]\))', line)

    # Pattern 2: Prefixed number - A1, A2, B1, B2, etc. followed by space
    # Then either a capital letter, Fig, or part marker
    prefixed_number = re.match(r'^[AB]([1-9]|1[0-9])\s+([A-Z]|Fig|\([a-z]\))', line)

    return bool(plain_number or prefixed_number)


def get_question_number(line: str) -> Optional[int]:
    """Extract question number from start of line.
    Strips A or B prefix if present (A1 -> 1, B4 -> 4).
    Returns int for all cases.
    """
    # Match optional 'A' or 'B' prefix followed by digits
    match = re.match(r'^[AB]?(\d+)\s+', line)
    if match:
        return int(match.group(1))
    return None


def detect_part_type(line: str) -> Optional[Dict[str, Any]]:
    """
    Detect if line contains a part marker like (a), (b), (i), (ii), etc.
    Returns dict with 'label', 'type' ('letter' or 'roman'), 'position', and 'match_obj'
    """
    # Check for roman numeral parts FIRST: (i), (ii), (iii), (iv), (v), etc. at start of line
    # We check this first because 'i' and 'v' are both letters AND roman numerals
    roman_match = re.match(r'^\s*\((i{1,3}|iv|v|vi{1,3}|ix|x)\)\s+', line, re.IGNORECASE)
    if roman_match:
        return {
            'label': roman_match.group(1).lower(),
            'type': 'roman',
            'position': roman_match.start(),
            'match': roman_match
        }

    # Check for letter parts: (a), (b), (c), etc. at start of line
    # Exclude 'i' and 'v' since they should be treated as roman numerals
    letter_match = re.match(r'^\s*\(([a-hjkl-uw-z])\)\s+', line)
    if letter_match:
        return {
            'label': letter_match.group(1),
            'type': 'letter',
            'position': letter_match.start(),
            'match': letter_match
        }

    return None


class QuestionExtractor:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.lines = []
        self.current_line_idx = 0

    def load_file(self):
        """Load and preprocess the file"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()

    def skip_page_separators(self):
        """Skip page separator lines"""
        while self.current_line_idx < len(self.lines):
            line = self.lines[self.current_line_idx].strip()
            if line.startswith('==================== CLEANED PAGE'):
                self.current_line_idx += 1
            elif line == '':
                self.current_line_idx += 1
            else:
                break

    def parse_part_content(self, part_type: str) -> Dict[str, Any]:
        """
        Parse content for a part (letter or roman numeral)
        Returns dict with partLabel, text, marks, markingScheme, and nested parts
        """
        # Get the current line which contains the part marker
        current_line = self.lines[self.current_line_idx].strip()
        part_info = detect_part_type(current_line)

        if not part_info:
            return None

        # Remove the part marker from the line to get the text
        # Use the match object to get the exact text to remove
        part_text_start = current_line[part_info['match'].end():]
        part_text_lines = []
        nested_parts = []

        # Check if the remaining text starts with a nested part marker
        # This handles cases like: (a) (i) Some text - where (a) has no text and (i) is nested
        if part_type == 'letter' and part_text_start.strip():
            # Check if what follows immediately is a roman numeral part
            nested_check = detect_part_type(part_text_start.strip())
            if nested_check and nested_check['type'] == 'roman':
                # Found inline nested part: (a) (i) text
                # Part (a) should have empty text
                # Replace current line with the nested part text and let while loop handle it
                self.lines[self.current_line_idx] = part_text_start.strip()
                # Don't increment - the while loop below will process this line as a nested part
                # part_text_lines stays empty, so parent part (a) will have empty text
            else:
                # Normal text after the part marker
                part_text_lines = [part_text_start] if part_text_start.strip() else []
                self.current_line_idx += 1
        else:
            # No text after part marker, or roman numeral part
            part_text_lines = [part_text_start] if part_text_start.strip() else []
            self.current_line_idx += 1

        # Collect text until we hit another part of the same or higher level, or a new question
        while self.current_line_idx < len(self.lines):
            line = self.lines[self.current_line_idx].strip()

            # Skip empty lines and page separators
            if line == '' or line.startswith('==================== CLEANED PAGE'):
                self.current_line_idx += 1
                continue

            # Check if this is a new question
            if is_question_start(line):
                break

            # Check for [Total: X] marker - this ends the current part/question
            if '[Total:' in line:
                break

            # Check if this is a part marker
            next_part = detect_part_type(line)

            if next_part:
                # If it's a deeper nested part (roman under letter), parse it recursively
                if part_type == 'letter' and next_part['type'] == 'roman':
                    nested_part = self.parse_part_content('roman')
                    if nested_part:
                        nested_parts.append(nested_part)
                    continue
                # If it's the same level or higher, stop collecting text
                elif (part_type == 'letter' and next_part['type'] == 'letter') or \
                     (part_type == 'roman' and next_part['type'] == 'roman') or \
                     (part_type == 'roman' and next_part['type'] == 'letter'):
                    break

            # Add line to text
            part_text_lines.append(line)
            self.current_line_idx += 1

        # Join all text lines
        full_text = ' '.join(part_text_lines).strip()

        # Extract marks from the text
        marks = extract_marks(full_text)

        return {
            'partLabel': part_info['label'],
            'text': full_text,
            'marks': marks,
            'markingScheme': None,
            'imageUrls': [],
            'parts': nested_parts
        }

    def parse_question(self) -> Optional[Dict[str, Any]]:
        """Parse a complete question with all its parts"""
        self.skip_page_separators()

        if self.current_line_idx >= len(self.lines):
            return None

        line = self.lines[self.current_line_idx].strip()

        # Check if this is a question start
        if not is_question_start(line):
            return None

        question_num = get_question_number(line)

        # Remove the question number from the line
        remaining_line = re.sub(r'^\d+\s+', '', line, count=1)

        # Check if the remaining line starts with a part marker
        first_part_info = detect_part_type(remaining_line)

        main_text_lines = []
        parts = []
        total_marks = None

        if first_part_info and first_part_info['type'] == 'letter':
            # The first part is on the same line as the question number
            # Replace the current line with just the part text (without question number)
            # so it will be processed as a part in the loop below
            self.lines[self.current_line_idx] = remaining_line
            # Don't increment, so the while loop will process this line as a part
        else:
            # Add the remaining text to main text
            if remaining_line.strip():
                main_text_lines.append(remaining_line)
            self.current_line_idx += 1

        # Collect main text and parts
        while self.current_line_idx < len(self.lines):
            line = self.lines[self.current_line_idx].strip()

            # Skip empty lines and page separators
            if line == '' or line.startswith('==================== CLEANED PAGE'):
                self.current_line_idx += 1
                continue

            # Check for total marks
            if '[Total:' in line:
                total_marks = extract_total_marks(line)
                self.current_line_idx += 1
                break

            # Check if this is a new question
            if is_question_start(line):
                break

            # Check if this is a part
            part_info = detect_part_type(line)
            if part_info and part_info['type'] == 'letter':
                # Parse the part
                part = self.parse_part_content('letter')
                if part:
                    parts.append(part)
                continue

            # Otherwise, add to main text
            main_text_lines.append(line)
            self.current_line_idx += 1

        main_text = ' '.join(main_text_lines).strip()

        # Fix nesting: move roman parts under their parent letter parts
        parts = self.fix_part_nesting(parts)

        # If total_marks not found in [Total: X], calculate from parts
        if total_marks is None:
            total_marks = self.calculate_total_marks(parts)

        return {
            'questionNumber': question_num,
            'mainText': main_text,
            'totalMarks': total_marks,
            'topic': '',
            'imageUrls': [],
            'parts': parts
        }

    def fix_part_nesting(self, parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fix part nesting by moving roman numeral parts under their parent letter parts.
        Roman parts (i, ii, iii, etc.) should be nested under the previous letter part.
        Also flattens any roman parts that are incorrectly nested under other roman parts.
        """
        fixed_parts = []
        i = 0
        while i < len(parts):
            part = parts[i]

            # Check if this is a letter part
            if part['partLabel'] in 'abcdefghijklmnopqrstuvwxyz' and len(part['partLabel']) == 1:
                # This is a letter part
                # Check if the next parts are roman numerals
                nested_roman_parts = []
                j = i + 1
                while j < len(parts):
                    next_part = parts[j]
                    # Check if it's a roman numeral part
                    if next_part['partLabel'] in ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']:
                        # Flatten: if this roman part has nested roman parts, bring them up
                        nested_roman_parts.append(next_part)
                        # Also add any roman parts nested under this roman part
                        nested_roman_parts.extend(self.flatten_roman_parts(next_part['parts']))
                        # Clear the parts array of the roman part
                        next_part['parts'] = []
                        j += 1
                    else:
                        break

                # Add the nested roman parts to this letter part
                if nested_roman_parts:
                    part['parts'] = nested_roman_parts
                    fixed_parts.append(part)
                    i = j  # Skip the roman parts we just nested
                else:
                    fixed_parts.append(part)
                    i += 1
            else:
                # Not a letter part (might be a roman part that wasn't nested)
                fixed_parts.append(part)
                i += 1

        return fixed_parts

    def flatten_roman_parts(self, parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Recursively flatten roman numeral parts from nested structures.
        Returns a flat list of all roman parts.
        """
        flat_parts = []
        for part in parts:
            if part['partLabel'] in ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']:
                flat_parts.append(part)
                # Recursively flatten nested parts
                if part['parts']:
                    flat_parts.extend(self.flatten_roman_parts(part['parts']))
                    part['parts'] = []  # Clear nested parts
        return flat_parts

    def calculate_total_marks(self, parts: List[Dict[str, Any]]) -> Optional[int]:
        """Recursively calculate total marks from parts"""
        total = 0
        for part in parts:
            if part['marks'] is not None:
                total += part['marks']
            if part['parts']:
                nested_total = self.calculate_total_marks(part['parts'])
                if nested_total:
                    total += nested_total
        return total if total > 0 else None

    def extract_all_questions(self) -> List[Dict[str, Any]]:
        """Extract all questions from the file"""
        self.load_file()
        questions = []

        while self.current_line_idx < len(self.lines):
            question = self.parse_question()
            if question:
                questions.append(question)
            else:
                # Move forward if we couldn't parse a question
                self.current_line_idx += 1

        return questions


def extract_questions_from_text(text_file_path: Path, output_json_path: Path) -> List[Dict[str, Any]]:
    """
    Main function to extract questions from cleaned text file.

    Args:
        text_file_path: Path to cleaned text file
        output_json_path: Path to write questions JSON

    Returns:
        List of extracted questions
    """
    extractor = QuestionExtractor(str(text_file_path))
    questions = extractor.extract_all_questions()

    # Write to JSON file
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    return questions
