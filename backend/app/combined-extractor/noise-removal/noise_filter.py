"""
Noise filter for removing headers, footers, and margin junk text from PDF character extraction.

Works with pdfplumber character extraction and filters characters based on detected noise zones.
"""

from typing import List, Dict, Tuple


class NoiseFilter:
    """Filters characters based on detected noise zones."""

    def __init__(self, noise_zones: Dict[str, any]):
        """
        Initialize noise filter with detected noise zones.

        Args:
            noise_zones: Dict from NoiseDetector.detect_noise_zones()
        """
        self.noise_zones = noise_zones
        self.header_zones = noise_zones.get('header_zones', [])
        self.footer_zones = noise_zones.get('footer_zones', [])
        self.left_margin_zones = noise_zones.get('left_margin_zones', [])
        self.right_margin_zones = noise_zones.get('right_margin_zones', [])

    def filter_characters(self, chars: List[Dict]) -> List[Dict]:
        """
        Filter out characters that fall within noise zones.

        Args:
            chars: List of character dicts from pdfplumber

        Returns:
            Filtered list of characters (noise removed)
        """
        if not chars:
            return []

        filtered = []

        for char in chars:
            if not self._is_in_noise_zone(char):
                filtered.append(char)

        return filtered

    def _is_in_noise_zone(self, char: Dict) -> bool:
        """
        Check if a character falls within any noise zone.

        Args:
            char: Character dict with 'x0', 'x1', 'top', 'bottom' keys

        Returns:
            True if character is in a noise zone
        """
        char_x0 = char['x0']
        char_x1 = char['x1']
        char_top = char['top']
        char_bottom = char['bottom']

        # Check header zones (Y-coordinate based)
        for zone in self.header_zones:
            if char_top >= zone['y_min'] and char_top <= zone['y_max']:
                return True

        # Check footer zones (Y-coordinate based)
        for zone in self.footer_zones:
            if char_top >= zone['y_min'] and char_top <= zone['y_max']:
                return True

        # Check left margin zones (X-coordinate based)
        for zone in self.left_margin_zones:
            if char_x0 >= zone['x_min'] and char_x0 <= zone['x_max']:
                return True

        # Check right margin zones (X-coordinate based)
        for zone in self.right_margin_zones:
            if char_x0 >= zone['x_min'] and char_x0 <= zone['x_max']:
                return True

        return False

    def get_noise_statistics(self) -> Dict:
        """
        Get statistics about the noise zones.

        Returns:
            Dict with zone counts and dimensions
        """
        stats = {
            'header_zones_count': len(self.header_zones),
            'footer_zones_count': len(self.footer_zones),
            'left_margin_zones_count': len(self.left_margin_zones),
            'right_margin_zones_count': len(self.right_margin_zones),
            'total_zones': (len(self.header_zones) + len(self.footer_zones) +
                          len(self.left_margin_zones) + len(self.right_margin_zones))
        }

        if self.header_zones:
            stats['header_height'] = self.header_zones[0]['y_max']

        if self.footer_zones:
            page_height = self.noise_zones.get('page_dimensions', (0, 0))[1]
            stats['footer_height'] = page_height - self.footer_zones[0]['y_min']

        if self.left_margin_zones:
            stats['left_margin_width'] = self.left_margin_zones[0]['x_max']

        if self.right_margin_zones:
            page_width = self.noise_zones.get('page_dimensions', (0, 0))[0]
            stats['right_margin_width'] = page_width - self.right_margin_zones[0]['x_min']

        return stats
