#!/usr/bin/env python3
"""
YouTube Search Filter Parameter Generator

This module provides the same functionality as the Crystal implementation
in src/invidious/search/filters.cr for generating YouTube search filter
parameters (the `sp=` URL parameter).

The filter parameter is a Base64-encoded protobuf object that YouTube uses
to filter search results by date, type, duration, features, and sort order.

Example usage:
    from youtube_filter_params import Filters, Date, Type, Duration, Features, Sort
    
    # Create filters
    filters = Filters(date=Date.WEEK, type=Type.VIDEO, sort=Sort.DATE)
    
    # Generate the sp= parameter value
    sp_param = filters.to_yt_params()
    print(f"sp={sp_param}")
"""

import base64
import binascii
from enum import IntEnum, IntFlag
from typing import Dict, Tuple
from urllib.parse import quote, unquote


class Date(IntEnum):
    """Upload date filter values.
    
    Corresponds to { "2:embedded": { "1:varint": <value> }}
    """
    NONE = 0   # No filter (omitted from output)
    HOUR = 1   # Last hour
    TODAY = 2  # Today
    WEEK = 3   # This week
    MONTH = 4  # This month
    YEAR = 5   # This year


class Type(IntEnum):
    """Content type filter values.
    
    Corresponds to { "2:embedded": { "2:varint": <value> }}
    """
    ALL = 0       # All types (omitted from output)
    VIDEO = 1     # Videos only
    CHANNEL = 2   # Channels only
    PLAYLIST = 3  # Playlists only
    MOVIE = 4     # Movies only
    SHOW = 5      # Shows (not available on YouTube's UI)


class Duration(IntEnum):
    """Video duration filter values.
    
    Corresponds to { "2:embedded": { "3:varint": <value> }}
    """
    NONE = 0    # No filter (omitted from output)
    SHORT = 1   # Under 4 minutes
    LONG = 2    # Over 20 minutes
    MEDIUM = 3  # 4-20 minutes


class Features(IntFlag):
    """Feature filter flags.
    
    Multiple features can be combined using bitwise OR.
    Each feature is a bit flag in this enum, and maps to a specific
    protobuf field number in the embedded message (shown in comments).
    
    Note: The bit positions in this enum are for internal flag storage,
    not the protobuf field numbers. The mapping to protobuf fields is
    done in the to_yt_params() method.
    """
    NONE = 0
    LIVE = 1 << 0        # Live streams - protobuf field 8
    FOUR_K = 1 << 1      # 4K resolution - protobuf field 14
    HD = 1 << 2          # HD quality - protobuf field 4
    SUBTITLES = 1 << 3   # Subtitles/CC - protobuf field 5
    CCOMMONS = 1 << 4    # Creative Commons - protobuf field 6
    THREE_SIXTY = 1 << 5 # 360° video - protobuf field 15
    VR180 = 1 << 6       # VR180 - protobuf field 26
    THREE_D = 1 << 7     # 3D video - protobuf field 7
    HDR = 1 << 8         # HDR - protobuf field 25
    LOCATION = 1 << 9    # Location tagged - protobuf field 23
    PURCHASED = 1 << 10  # Purchased - protobuf field 9


class Sort(IntEnum):
    """Sort order values.
    
    Corresponds to { "1:varint": <value> }
    """
    RELEVANCE = 0  # Default (omitted from output)
    RATING = 1     # Sort by rating
    DATE = 2       # Sort by upload date
    VIEWS = 3      # Sort by view count


def _encode_varint(value: int) -> bytes:
    """Encode an integer as a protobuf varint.
    
    Args:
        value: The integer to encode (must be non-negative)
        
    Returns:
        The varint-encoded bytes
    """
    if value == 0:
        return bytes([0])
    
    result = bytearray()
    # Convert to unsigned representation for encoding
    value = value & 0xFFFFFFFFFFFFFFFF  # Ensure 64-bit unsigned
    
    while value != 0:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte |= 0x80
        result.append(byte)
    
    return bytes(result)


def _encode_field(field_number: int, wire_type: int, value: bytes) -> bytes:
    """Encode a protobuf field with its header.
    
    Args:
        field_number: The protobuf field number
        wire_type: The wire type (0=varint, 2=length-delimited)
        value: The encoded value bytes
        
    Returns:
        The complete field encoding including header
    """
    header = (field_number << 3) | wire_type
    return _encode_varint(header) + value


def _encode_embedded(fields: Dict[int, int]) -> bytes:
    """Encode multiple varint fields as an embedded protobuf message.
    
    Args:
        fields: Dictionary mapping field numbers to their varint values
        
    Returns:
        The encoded embedded message bytes
    """
    result = bytearray()
    
    # Sort fields by field number for consistent output
    for field_num in sorted(fields.keys()):
        value = fields[field_num]
        encoded_value = _encode_varint(value)
        result.extend(_encode_field(field_num, 0, encoded_value))
    
    return bytes(result)


class Filters:
    """YouTube search filter parameters.
    
    This class represents the various filter options available for YouTube search
    and can generate the encoded `sp=` parameter used in search URLs.
    
    Attributes:
        date: Upload date filter
        type: Content type filter
        duration: Video duration filter
        features: Feature flags (can be combined with |)
        sort: Sort order
    """
    
    def __init__(
        self,
        *,
        date: Date = Date.NONE,
        type: Type = Type.ALL,
        duration: Duration = Duration.NONE,
        features: Features = Features.NONE,
        sort: Sort = Sort.RELEVANCE,
    ):
        """Initialize filter parameters.
        
        Args:
            date: Upload date filter (default: NONE)
            type: Content type filter (default: ALL)
            duration: Video duration filter (default: NONE)
            features: Feature flags (default: NONE)
            sort: Sort order (default: RELEVANCE)
        """
        self.date = date
        self.type = type
        self.duration = duration
        self.features = features
        self.sort = sort
    
    def is_default(self) -> bool:
        """Check if all filters are at their default values.
        
        Returns:
            True if no filters are active, False otherwise
        """
        return (
            self.date == Date.NONE
            and self.type == Type.ALL
            and self.duration == Duration.NONE
            and self.features == Features.NONE
            and self.sort == Sort.RELEVANCE
        )
    
    def to_yt_params(self, page: int = 1) -> str:
        """Generate the YouTube search parameter string.
        
        This produces the value for the `sp=` URL parameter that YouTube
        uses for search filtering. The format is a Base64-encoded protobuf
        object, URL-encoded for safe transmission.
        
        Args:
            page: Page number for pagination (default: 1)
            
        Returns:
            The encoded filter parameter string (URL-safe)
        """
        # Build the embedded message (field 2)
        embedded_fields: Dict[int, int] = {}
        
        # Add date filter (field 2:1)
        if self.date != Date.NONE:
            embedded_fields[1] = self.date.value
        
        # Add type filter (field 2:2)
        if self.type != Type.ALL:
            embedded_fields[2] = self.type.value
        
        # Add duration filter (field 2:3)
        if self.duration != Duration.NONE:
            embedded_fields[3] = self.duration.value
        
        # Add feature filters (various fields)
        if self.features != Features.NONE:
            if Features.HD in self.features:
                embedded_fields[4] = 1
            if Features.SUBTITLES in self.features:
                embedded_fields[5] = 1
            if Features.CCOMMONS in self.features:
                embedded_fields[6] = 1
            if Features.THREE_D in self.features:
                embedded_fields[7] = 1
            if Features.LIVE in self.features:
                embedded_fields[8] = 1
            if Features.PURCHASED in self.features:
                embedded_fields[9] = 1
            if Features.FOUR_K in self.features:
                embedded_fields[14] = 1
            if Features.THREE_SIXTY in self.features:
                embedded_fields[15] = 1
            if Features.LOCATION in self.features:
                embedded_fields[23] = 1
            if Features.HDR in self.features:
                embedded_fields[25] = 1
            if Features.VR180 in self.features:
                embedded_fields[26] = 1
        
        # Build the main protobuf message
        result = bytearray()
        
        # Add sort order (field 1) - only if not default (relevance)
        if self.sort != Sort.RELEVANCE:
            result.extend(_encode_field(1, 0, _encode_varint(self.sort.value)))
        
        # Add embedded filters (field 2) - only if there are any
        if embedded_fields:
            embedded_data = _encode_embedded(embedded_fields)
            result.extend(_encode_varint((2 << 3) | 2))  # field 2, wire type 2
            result.extend(_encode_varint(len(embedded_data)))
            result.extend(embedded_data)
        
        # Add page offset (field 9) - only if page > 1
        if page > 1:
            offset = (page - 1) * 20
            result.extend(_encode_field(9, 0, _encode_varint(offset)))
        
        # Add self-harm content flag (field 30) - prevents censoring
        # See https://github.com/iv-org/invidious/issues/4398
        result.extend(_encode_field(30, 0, _encode_varint(1)))
        
        # Base64 URL-safe encode
        encoded = base64.urlsafe_b64encode(bytes(result)).decode('ascii')
        
        # URL encode
        return quote(encoded, safe='')
    
    @classmethod
    def from_yt_params(cls, sp_param: str) -> 'Filters':
        """Parse a YouTube search parameter string into Filters.
        
        Args:
            sp_param: The value of the `sp=` URL parameter
            
        Returns:
            A Filters instance with the decoded values
        """
        if not sp_param:
            return cls()
        
        # URL decode
        decoded_url = unquote(sp_param)
        
        # Base64 decode
        try:
            data = base64.urlsafe_b64decode(decoded_url)
        except (binascii.Error, ValueError):
            # Try standard base64 if URL-safe fails
            data = base64.b64decode(decoded_url)
        
        # Parse protobuf
        filters = cls()
        pos = 0
        embedded_data = None
        
        while pos < len(data):
            # Read header
            header, pos = _decode_varint(data, pos)
            field_num = header >> 3
            wire_type = header & 0x07
            
            if wire_type == 0:  # Varint
                value, pos = _decode_varint(data, pos)
                if field_num == 1:
                    try:
                        filters.sort = Sort(value)
                    except ValueError:
                        pass
            elif wire_type == 2:  # Length-delimited
                length, pos = _decode_varint(data, pos)
                if field_num == 2:
                    embedded_data = data[pos:pos + length]
                pos += length
        
        # Parse embedded message
        if embedded_data:
            pos = 0
            feature_value = Features.NONE
            
            while pos < len(embedded_data):
                header, pos = _decode_varint(embedded_data, pos)
                field_num = header >> 3
                wire_type = header & 0x07
                
                if wire_type == 0:  # Varint
                    value, pos = _decode_varint(embedded_data, pos)
                    
                    if field_num == 1:
                        try:
                            filters.date = Date(value)
                        except ValueError:
                            pass
                    elif field_num == 2:
                        try:
                            filters.type = Type(value)
                        except ValueError:
                            pass
                    elif field_num == 3:
                        try:
                            filters.duration = Duration(value)
                        except ValueError:
                            pass
                    elif field_num == 4 and value == 1:
                        feature_value |= Features.HD
                    elif field_num == 5 and value == 1:
                        feature_value |= Features.SUBTITLES
                    elif field_num == 6 and value == 1:
                        feature_value |= Features.CCOMMONS
                    elif field_num == 7 and value == 1:
                        feature_value |= Features.THREE_D
                    elif field_num == 8 and value == 1:
                        feature_value |= Features.LIVE
                    elif field_num == 9 and value == 1:
                        feature_value |= Features.PURCHASED
                    elif field_num == 14 and value == 1:
                        feature_value |= Features.FOUR_K
                    elif field_num == 15 and value == 1:
                        feature_value |= Features.THREE_SIXTY
                    elif field_num == 23 and value == 1:
                        feature_value |= Features.LOCATION
                    elif field_num == 25 and value == 1:
                        feature_value |= Features.HDR
                    elif field_num == 26 and value == 1:
                        feature_value |= Features.VR180
            
            filters.features = feature_value
        
        return filters
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Filters):
            return NotImplemented
        return (
            self.date == other.date
            and self.type == other.type
            and self.duration == other.duration
            and self.features == other.features
            and self.sort == other.sort
        )
    
    def __repr__(self) -> str:
        return (
            f"Filters(date={self.date.name}, type={self.type.name}, "
            f"duration={self.duration.name}, features={self.features}, "
            f"sort={self.sort.name})"
        )


def _decode_varint(data: bytes, pos: int) -> Tuple[int, int]:
    """Decode a varint from a byte sequence.
    
    Args:
        data: The byte sequence
        pos: Starting position
        
    Returns:
        Tuple of (decoded value, new position)
    """
    result = 0
    shift = 0
    
    while True:
        if pos >= len(data):
            raise ValueError("Unexpected end of data while reading varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if (byte & 0x80) == 0:
            break
        if shift >= 64:
            raise ValueError("Varint too long")
    
    return result, pos


# Convenience function for quick encoding
def encode_filters(
    date: Date = Date.NONE,
    type: Type = Type.ALL,
    duration: Duration = Duration.NONE,
    features: Features = Features.NONE,
    sort: Sort = Sort.RELEVANCE,
    page: int = 1,
) -> str:
    """Convenience function to generate YouTube search filter parameters.
    
    Args:
        date: Upload date filter
        type: Content type filter
        duration: Video duration filter
        features: Feature flags
        sort: Sort order
        page: Page number for pagination
        
    Returns:
        The encoded filter parameter string
        
    Example:
        >>> encode_filters(date=Date.WEEK)
        'EgIIA_ABAQ%3D%3D'
    """
    return Filters(
        date=date,
        type=type,
        duration=duration,
        features=features,
        sort=sort,
    ).to_yt_params(page)


if __name__ == "__main__":
    # Demo: Print some example filter encodings
    print("YouTube Search Filter Parameter Generator")
    print("=" * 50)
    
    # Test cases matching the Crystal spec file
    test_cases = [
        ("Date: Hour", Filters(date=Date.HOUR)),
        ("Date: Today", Filters(date=Date.TODAY)),
        ("Date: Week", Filters(date=Date.WEEK)),
        ("Date: Month", Filters(date=Date.MONTH)),
        ("Date: Year", Filters(date=Date.YEAR)),
        ("Type: Video", Filters(type=Type.VIDEO)),
        ("Type: Channel", Filters(type=Type.CHANNEL)),
        ("Type: Playlist", Filters(type=Type.PLAYLIST)),
        ("Type: Movie", Filters(type=Type.MOVIE)),
        ("Duration: Short", Filters(duration=Duration.SHORT)),
        ("Duration: Medium", Filters(duration=Duration.MEDIUM)),
        ("Duration: Long", Filters(duration=Duration.LONG)),
        ("Feature: Live", Filters(features=Features.LIVE)),
        ("Feature: 4K", Filters(features=Features.FOUR_K)),
        ("Feature: HD", Filters(features=Features.HD)),
        ("Feature: Subtitles", Filters(features=Features.SUBTITLES)),
        ("Feature: Creative Commons", Filters(features=Features.CCOMMONS)),
        ("Feature: 360°", Filters(features=Features.THREE_SIXTY)),
        ("Feature: VR180", Filters(features=Features.VR180)),
        ("Feature: 3D", Filters(features=Features.THREE_D)),
        ("Feature: HDR", Filters(features=Features.HDR)),
        ("Feature: Location", Filters(features=Features.LOCATION)),
        ("Feature: Purchased", Filters(features=Features.PURCHASED)),
        ("Sort: Relevance", Filters(sort=Sort.RELEVANCE)),
        ("Sort: Date", Filters(sort=Sort.DATE)),
        ("Sort: Views", Filters(sort=Sort.VIEWS)),
        ("Sort: Rating", Filters(sort=Sort.RATING)),
    ]
    
    for name, filters in test_cases:
        sp = filters.to_yt_params()
        print(f"{name:30} -> sp={sp}")
    
    print("\n" + "=" * 50)
    print("Combined filters example:")
    combined = Filters(
        date=Date.MONTH,
        type=Type.VIDEO,
        duration=Duration.MEDIUM,
        features=Features.HD | Features.SUBTITLES,
        sort=Sort.DATE,
    )
    print(f"Filters: {combined}")
    print(f"sp={combined.to_yt_params()}")
