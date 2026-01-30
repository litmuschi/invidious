#!/usr/bin/env python3
"""
Test suite for youtube_filter_params.py

These tests verify that the Python implementation produces the same output
as the Crystal implementation in src/invidious/search/filters.cr.

Expected values are extracted from spec/invidious/search/yt_filters_spec.cr.
"""

import unittest
from youtube_filter_params import (
    Filters, Date, Type, Duration, Features, Sort,
    encode_filters, _encode_varint, _decode_varint
)


class TestVarint(unittest.TestCase):
    """Test varint encoding/decoding."""
    
    def test_encode_zero(self):
        self.assertEqual(_encode_varint(0), bytes([0]))
    
    def test_encode_small_values(self):
        self.assertEqual(_encode_varint(1), bytes([1]))
        self.assertEqual(_encode_varint(127), bytes([127]))
    
    def test_encode_larger_values(self):
        # 128 requires two bytes
        self.assertEqual(_encode_varint(128), bytes([0x80, 0x01]))
        # 300 = 0x12c = 10101100 00000010
        self.assertEqual(_encode_varint(300), bytes([0xAC, 0x02]))
    
    def test_roundtrip(self):
        for value in [0, 1, 127, 128, 255, 256, 1000, 10000]:
            encoded = _encode_varint(value)
            decoded, pos = _decode_varint(encoded, 0)
            self.assertEqual(decoded, value)
            self.assertEqual(pos, len(encoded))


class TestDateFilters(unittest.TestCase):
    """Test date filter encoding - matches Crystal spec."""
    
    EXPECTED = {
        Date.HOUR:  "EgIIAfABAQ%3D%3D",
        Date.TODAY: "EgIIAvABAQ%3D%3D",
        Date.WEEK:  "EgIIA_ABAQ%3D%3D",
        Date.MONTH: "EgIIBPABAQ%3D%3D",
        Date.YEAR:  "EgIIBfABAQ%3D%3D",
    }
    
    def test_date_filters(self):
        for date_filter, expected in self.EXPECTED.items():
            with self.subTest(date_filter=date_filter):
                filters = Filters(date=date_filter)
                result = filters.to_yt_params()
                self.assertEqual(result, expected,
                    f"Date filter {date_filter.name} produced {result}, expected {expected}")


class TestTypeFilters(unittest.TestCase):
    """Test type filter encoding - matches Crystal spec."""
    
    EXPECTED = {
        Type.VIDEO:    "EgIQAfABAQ%3D%3D",
        Type.CHANNEL:  "EgIQAvABAQ%3D%3D",
        Type.PLAYLIST: "EgIQA_ABAQ%3D%3D",
        Type.MOVIE:    "EgIQBPABAQ%3D%3D",
    }
    
    def test_type_filters(self):
        for type_filter, expected in self.EXPECTED.items():
            with self.subTest(type_filter=type_filter):
                filters = Filters(type=type_filter)
                result = filters.to_yt_params()
                self.assertEqual(result, expected,
                    f"Type filter {type_filter.name} produced {result}, expected {expected}")


class TestDurationFilters(unittest.TestCase):
    """Test duration filter encoding - matches Crystal spec."""
    
    EXPECTED = {
        Duration.SHORT:  "EgIYAfABAQ%3D%3D",
        Duration.MEDIUM: "EgIYA_ABAQ%3D%3D",
        Duration.LONG:   "EgIYAvABAQ%3D%3D",
    }
    
    def test_duration_filters(self):
        for duration_filter, expected in self.EXPECTED.items():
            with self.subTest(duration_filter=duration_filter):
                filters = Filters(duration=duration_filter)
                result = filters.to_yt_params()
                self.assertEqual(result, expected,
                    f"Duration filter {duration_filter.name} produced {result}, expected {expected}")


class TestFeatureFilters(unittest.TestCase):
    """Test feature filter encoding - matches Crystal spec."""
    
    EXPECTED = {
        Features.LIVE:       "EgJAAfABAQ%3D%3D",
        Features.FOUR_K:     "EgJwAfABAQ%3D%3D",
        Features.HD:         "EgIgAfABAQ%3D%3D",
        Features.SUBTITLES:  "EgIoAfABAQ%3D%3D",
        Features.CCOMMONS:   "EgIwAfABAQ%3D%3D",
        Features.THREE_SIXTY: "EgJ4AfABAQ%3D%3D",
        Features.VR180:      "EgPQAQHwAQE%3D",
        Features.THREE_D:    "EgI4AfABAQ%3D%3D",
        Features.HDR:        "EgPIAQHwAQE%3D",
        Features.LOCATION:   "EgO4AQHwAQE%3D",
        Features.PURCHASED:  "EgJIAfABAQ%3D%3D",
    }
    
    def test_feature_filters(self):
        for feature_filter, expected in self.EXPECTED.items():
            with self.subTest(feature_filter=feature_filter):
                filters = Filters(features=feature_filter)
                result = filters.to_yt_params()
                self.assertEqual(result, expected,
                    f"Feature filter {feature_filter.name} produced {result}, expected {expected}")


class TestSortFilters(unittest.TestCase):
    """Test sort filter encoding - matches Crystal spec."""
    
    EXPECTED = {
        Sort.RELEVANCE: "8AEB",
        Sort.DATE:      "CALwAQE%3D",
        Sort.VIEWS:     "CAPwAQE%3D",
        Sort.RATING:    "CAHwAQE%3D",
    }
    
    def test_sort_filters(self):
        for sort_filter, expected in self.EXPECTED.items():
            with self.subTest(sort_filter=sort_filter):
                filters = Filters(sort=sort_filter)
                result = filters.to_yt_params()
                self.assertEqual(result, expected,
                    f"Sort filter {sort_filter.name} produced {result}, expected {expected}")


class TestFiltersDecoding(unittest.TestCase):
    """Test decoding sp= parameters back to Filters."""
    
    def test_decode_date_filters(self):
        for date_filter, encoded in TestDateFilters.EXPECTED.items():
            with self.subTest(date_filter=date_filter):
                decoded = Filters.from_yt_params(encoded)
                self.assertEqual(decoded.date, date_filter)
    
    def test_decode_type_filters(self):
        for type_filter, encoded in TestTypeFilters.EXPECTED.items():
            with self.subTest(type_filter=type_filter):
                decoded = Filters.from_yt_params(encoded)
                self.assertEqual(decoded.type, type_filter)
    
    def test_decode_duration_filters(self):
        for duration_filter, encoded in TestDurationFilters.EXPECTED.items():
            with self.subTest(duration_filter=duration_filter):
                decoded = Filters.from_yt_params(encoded)
                self.assertEqual(decoded.duration, duration_filter)
    
    def test_decode_feature_filters(self):
        for feature_filter, encoded in TestFeatureFilters.EXPECTED.items():
            with self.subTest(feature_filter=feature_filter):
                decoded = Filters.from_yt_params(encoded)
                self.assertIn(feature_filter, decoded.features)
    
    def test_decode_sort_filters(self):
        for sort_filter, encoded in TestSortFilters.EXPECTED.items():
            with self.subTest(sort_filter=sort_filter):
                decoded = Filters.from_yt_params(encoded)
                self.assertEqual(decoded.sort, sort_filter)


class TestCombinedFilters(unittest.TestCase):
    """Test combined filter scenarios."""
    
    def test_combined_features(self):
        """Test combining multiple features."""
        features = Features.HD | Features.SUBTITLES | Features.LIVE
        filters = Filters(features=features)
        result = filters.to_yt_params()
        # Verify it's a valid string (encoding worked)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        
        # Verify round-trip
        decoded = Filters.from_yt_params(result)
        self.assertIn(Features.HD, decoded.features)
        self.assertIn(Features.SUBTITLES, decoded.features)
        self.assertIn(Features.LIVE, decoded.features)
    
    def test_all_filter_types_combined(self):
        """Test combining all filter types."""
        filters = Filters(
            date=Date.MONTH,
            type=Type.VIDEO,
            duration=Duration.MEDIUM,
            features=Features.HD | Features.SUBTITLES,
            sort=Sort.DATE,
        )
        result = filters.to_yt_params()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        
        # Verify round-trip
        decoded = Filters.from_yt_params(result)
        self.assertEqual(decoded.date, Date.MONTH)
        self.assertEqual(decoded.type, Type.VIDEO)
        self.assertEqual(decoded.duration, Duration.MEDIUM)
        self.assertEqual(decoded.sort, Sort.DATE)
        self.assertIn(Features.HD, decoded.features)
        self.assertIn(Features.SUBTITLES, decoded.features)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases."""
    
    def test_default_filters(self):
        """Default filters should produce minimal output."""
        filters = Filters()
        self.assertTrue(filters.is_default())
        result = filters.to_yt_params()
        # Default should just have the self-harm prevention flag
        self.assertEqual(result, "8AEB")
    
    def test_empty_param(self):
        """Empty sp param should return default filters."""
        filters = Filters.from_yt_params("")
        self.assertTrue(filters.is_default())
    
    def test_pagination(self):
        """Test page parameter."""
        filters = Filters(date=Date.WEEK)
        page1 = filters.to_yt_params(page=1)
        page2 = filters.to_yt_params(page=2)
        page3 = filters.to_yt_params(page=3)
        
        # Different pages should produce different results
        self.assertNotEqual(page1, page2)
        self.assertNotEqual(page2, page3)
    
    def test_convenience_function(self):
        """Test the convenience function."""
        result = encode_filters(date=Date.WEEK, sort=Sort.DATE)
        expected = Filters(date=Date.WEEK, sort=Sort.DATE).to_yt_params()
        self.assertEqual(result, expected)


class TestEquality(unittest.TestCase):
    """Test filter equality."""
    
    def test_equal_filters(self):
        f1 = Filters(date=Date.WEEK, sort=Sort.DATE)
        f2 = Filters(date=Date.WEEK, sort=Sort.DATE)
        self.assertEqual(f1, f2)
    
    def test_unequal_filters(self):
        f1 = Filters(date=Date.WEEK)
        f2 = Filters(date=Date.MONTH)
        self.assertNotEqual(f1, f2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
