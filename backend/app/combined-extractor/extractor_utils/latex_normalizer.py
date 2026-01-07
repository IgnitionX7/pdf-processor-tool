r"""
LaTeX notation normalizer for chemical formulas.

Performs semantic normalization of LaTeX chemical notation, including:
- Nuclide notation repair (merging split mass/atomic numbers)
- Element symbol formatting with \mathrm{}
"""

import re
from typing import List, Tuple


class LatexNormalizer:
    """Normalizes LaTeX chemical notation."""

    # Pattern to match element symbols (1-2 letters, first uppercase)
    _ELEMENT_PATTERN = re.compile(r'\b([A-Z][a-z]?)\b')

    # Pattern to match nuclide notation: ^{digit(s)}_{digit(s)}^{digit(s)}_{digit(s)}Element
    # Captures: (^{A1})(_{Z1})(^{A2})(_{Z2})(Element)
    _NUCLIDE_SPLIT_PATTERN = re.compile(
        r'(\^{(\d+)})(_\{(\d+)\})(\^{(\d+)})(_\{(\d+)\})([A-Z][a-z]?)'
    )

    # Pattern to match already-normalized nuclide: ^{digits}_{digits}Element or ^{digits}_{digits}\mathrm{Element}
    _NUCLIDE_NORMALIZED_PATTERN = re.compile(
        r'\^{(\d+)}_\{(\d+)\}(\\mathrm\{)?([A-Z][a-z]?)'
    )

    def __init__(self,
                 normalize_nuclides: bool = True,
                 wrap_elements_mathrm: bool = True):
        r"""
        Initialize LaTeX normalizer.

        Args:
            normalize_nuclides: Enable nuclide notation repair (merge split mass/atomic numbers)
            wrap_elements_mathrm: Wrap element symbols in \mathrm{} for proper formatting
        """
        self.normalize_nuclides = normalize_nuclides
        self.wrap_elements_mathrm = wrap_elements_mathrm

    def normalize(self, text: str) -> str:
        """
        Normalize LaTeX chemical notation in text.

        Args:
            text: Text containing LaTeX notation

        Returns:
            Normalized text
        """
        if not text:
            return text

        # Step 1: Normalize nuclide notation (merge split numbers)
        if self.normalize_nuclides:
            text = self._normalize_nuclides(text)

        # Step 2: Wrap element symbols in \mathrm{} if not already wrapped
        if self.wrap_elements_mathrm:
            text = self._wrap_elements_in_mathrm(text)

        return text

    def _normalize_nuclides(self, text: str) -> str:
        """
        Normalize split nuclide notation by merging adjacent super/subscripts.

        Transforms: ^{3}_{1}^{5}_{7}Cl → ^{35}_{17}Cl
        """
        def merge_nuclide(match):
            # Extract all captured groups
            sup1_full = match.group(1)  # ^{A1}
            sup1_num = match.group(2)   # A1
            sub1_full = match.group(3)  # _{Z1}
            sub1_num = match.group(4)   # Z1
            sup2_full = match.group(5)  # ^{A2}
            sup2_num = match.group(6)   # A2
            sub2_full = match.group(7)  # _{Z2}
            sub2_num = match.group(8)   # Z2
            element = match.group(9)    # Element symbol

            # Merge the numbers
            mass_number = sup1_num + sup2_num  # Concatenate strings: "3" + "5" = "35"
            atomic_number = sub1_num + sub2_num  # "1" + "7" = "17"

            # Return normalized notation
            return f"^{{{mass_number}}}_{{{atomic_number}}}{element}"

        return self._NUCLIDE_SPLIT_PATTERN.sub(merge_nuclide, text)

    def _wrap_elements_in_mathrm(self, text: str) -> str:
        r"""
        Wrap element symbols in \mathrm{} for proper LaTeX formatting.

        Only wraps standalone elements or elements in nuclide notation that aren't already wrapped.
        """
        # First, wrap elements in normalized nuclide notation if not already wrapped
        def wrap_nuclide_element(match):
            mass = match.group(1)
            atomic = match.group(2)
            mathrm_exists = match.group(3)  # \mathrm{ if present
            element = match.group(4)

            if mathrm_exists:
                # Already wrapped, don't change
                return match.group(0)
            else:
                # Wrap element symbol
                return f"^{{{mass}}}_{{{atomic}}}\\mathrm{{{element}}}"

        text = self._NUCLIDE_NORMALIZED_PATTERN.sub(wrap_nuclide_element, text)

        return text

    def normalize_batch(self, texts: List[str]) -> List[str]:
        """
        Normalize multiple text strings.

        Args:
            texts: List of text strings containing LaTeX notation

        Returns:
            List of normalized text strings
        """
        return [self.normalize(text) for text in texts]

    def get_statistics(self, original: str, normalized: str) -> dict:
        """
        Get statistics about normalization changes.

        Args:
            original: Original text before normalization
            normalized: Text after normalization

        Returns:
            Dictionary with normalization statistics
        """
        # Count nuclide patterns before and after
        original_split = len(self._NUCLIDE_SPLIT_PATTERN.findall(original))
        normalized_split = len(self._NUCLIDE_SPLIT_PATTERN.findall(normalized))

        # Count normalized nuclides
        normalized_count = len(self._NUCLIDE_NORMALIZED_PATTERN.findall(normalized))

        return {
            "original_split_nuclides": original_split,
            "remaining_split_nuclides": normalized_split,
            "normalized_nuclides": normalized_count,
            "nuclides_repaired": original_split - normalized_split,
            "text_changed": original != normalized
        }


# Convenience function for quick normalization
def normalize_latex(text: str,
                    normalize_nuclides: bool = True,
                    wrap_elements_mathrm: bool = True) -> str:
    r"""
    Quick normalization of LaTeX chemical notation.

    Args:
        text: Text containing LaTeX notation
        normalize_nuclides: Enable nuclide notation repair
        wrap_elements_mathrm: Wrap element symbols in \mathrm{}

    Returns:
        Normalized text
    """
    normalizer = LatexNormalizer(
        normalize_nuclides=normalize_nuclides,
        wrap_elements_mathrm=wrap_elements_mathrm
    )
    return normalizer.normalize(text)


# Example usage and tests
if __name__ == "__main__":
    normalizer = LatexNormalizer()

    # Test cases
    test_cases = [
        ("^{3}_{1}^{5}_{7}Cl", "^{35}_{17}\\mathrm{Cl}"),
        ("^{3}_{1}^{9}_{9}K", "^{39}_{19}\\mathrm{K}"),
        ("^{2}_{9}^{38}_{2}U", "^{238}_{92}\\mathrm{U}"),  # Uranium-238
        ("Some text with ^{3}_{1}^{5}_{7}Cl in the middle",
         "Some text with ^{35}_{17}\\mathrm{Cl} in the middle"),
        ("Multiple: ^{3}_{1}^{5}_{7}Cl and ^{3}_{1}^{9}_{9}K",
         "Multiple: ^{35}_{17}\\mathrm{Cl} and ^{39}_{19}\\mathrm{K}"),
    ]

    print("LaTeX Normalizer Test Cases:")
    print("=" * 70)

    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = normalizer.normalize(input_text)
        status = "[OK]" if result == expected else "[FAIL]"

        print(f"\nTest {i}: {status}")
        print(f"  Input:    {input_text}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")

        if result == expected:
            stats = normalizer.get_statistics(input_text, result)
            if stats['nuclides_repaired'] > 0:
                print(f"  Stats: Repaired {stats['nuclides_repaired']} nuclide(s)")
