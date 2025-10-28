"""
Script to merge image URLs from a text file into corresponding questions in a JSON file.
The script matches URLs based on Fig-X or Table-X patterns where X is the question number.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any


def extract_question_number(url: str) -> Optional[int]:
    """
    Extract question number from URL patterns like Fig-X-Y or Table-X-Y.

    Args:
        url: String containing the image URL

    Returns:
        int: Question number if pattern found, None otherwise
    """
    # Pattern to match Fig-X or Table-X where X is the question number
    pattern = r'(?:Fig|Table)-(\d+)-'
    match = re.search(pattern, url)

    if match:
        return int(match.group(1))
    return None


def load_urls_from_file(txt_file_path: Path) -> List[str]:
    """
    Load URLs from text file.

    Args:
        txt_file_path: Path to the text file containing URLs

    Returns:
        list: List of URL strings
    """
    with open(txt_file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    return urls


def load_urls_from_string(txt_content: str) -> List[str]:
    """
    Load URLs from string content.

    Args:
        txt_content: String containing URLs (one per line)

    Returns:
        list: List of URL strings
    """
    urls = [line.strip() for line in txt_content.splitlines() if line.strip()]
    return urls


def load_questions_from_file(json_file_path: Path) -> Any:
    """
    Load questions from JSON file.

    Args:
        json_file_path: Path to the JSON file containing questions

    Returns:
        dict or list: Parsed JSON data
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def load_questions_from_string(json_content: str) -> Any:
    """
    Load questions from JSON string.

    Args:
        json_content: String containing JSON data

    Returns:
        dict or list: Parsed JSON data
    """
    data = json.loads(json_content)
    return data


def merge_urls_to_questions(questions_data: Any, urls: List[str]) -> Any:
    """
    Merge URLs into the corresponding questions based on question number.

    Args:
        questions_data: JSON data containing questions
        urls: List of image URLs

    Returns:
        dict or list: Updated questions data with imageUrls populated
    """
    # Create a mapping of question_number -> list of URLs
    url_mapping = {}

    for url in urls:
        question_num = extract_question_number(url)
        if question_num is not None:
            if question_num not in url_mapping:
                url_mapping[question_num] = []
            url_mapping[question_num].append(url)

    # Update questions with their corresponding URLs
    # Handle both list and dict formats
    if isinstance(questions_data, list):
        for question in questions_data:
            if 'questionNumber' in question:
                q_num = question['questionNumber']
                if q_num in url_mapping:
                    question['imageUrls'] = url_mapping[q_num]
    elif isinstance(questions_data, dict):
        # If it's a dict, check if it has a 'questions' key or similar
        if 'questions' in questions_data:
            for question in questions_data['questions']:
                if 'questionNumber' in question:
                    q_num = question['questionNumber']
                    if q_num in url_mapping:
                        question['imageUrls'] = url_mapping[q_num]
        else:
            # If the dict itself is a single question
            if 'questionNumber' in questions_data:
                q_num = questions_data['questionNumber']
                if q_num in url_mapping:
                    questions_data['imageUrls'] = url_mapping[q_num]

    return questions_data


def save_merged_json(data: Any, output_path: Path) -> None:
    """
    Save the updated JSON data to a file.

    Args:
        data: Updated questions data
        output_path: Path to output file
    """
    # Create output folder if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON with proper formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Successfully merged URLs into questions!")
    print(f"Output saved to: {output_path}")
