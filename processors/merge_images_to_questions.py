#!/usr/bin/env python3
"""
Script to merge image URLs from a text file into corresponding questions in a JSON file.
The script matches URLs based on Fig-X or Table-X patterns where X is the question number.
"""

import json
import re
import sys
import os


def extract_question_number(url):
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


def load_urls(txt_file_path):
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


def load_questions(json_file_path):
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


def merge_urls_to_questions(questions_data, urls):
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


def save_output(data, output_folder, original_filename):
    """
    Save the updated JSON data to the output folder.

    Args:
        data: Updated questions data
        output_folder: Path to output folder
        original_filename: Original JSON filename to use for output
    """
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Generate output filename
    output_filename = os.path.basename(original_filename)
    output_path = os.path.join(output_folder, output_filename)

    # Write JSON with proper formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Successfully merged URLs into questions!")
    print(f"Output saved to: {output_path}")


def main():
    """Main function to orchestrate the merging process."""
    if len(sys.argv) != 4:
        print("Usage: python merge_images_to_questions.py <json_file> <txt_file> <output_folder>")
        print("\nExample:")
        print("  python merge_images_to_questions.py questions.json urls.txt ./output")
        sys.exit(1)

    json_file = sys.argv[1]
    txt_file = sys.argv[2]
    output_folder = sys.argv[3]

    # Validate input files exist
    if not os.path.exists(json_file):
        print(f"Error: JSON file not found: {json_file}")
        sys.exit(1)

    if not os.path.exists(txt_file):
        print(f"Error: TXT file not found: {txt_file}")
        sys.exit(1)

    try:
        # Load data
        print(f"Loading URLs from: {txt_file}")
        urls = load_urls(txt_file)
        print(f"Found {len(urls)} URLs")

        print(f"Loading questions from: {json_file}")
        questions_data = load_questions(json_file)

        # Merge URLs into questions
        print("Merging URLs into questions...")
        updated_data = merge_urls_to_questions(questions_data, urls)

        # Save output
        save_output(updated_data, output_folder, json_file)

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
