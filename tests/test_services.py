"""
Unit tests for services.py - especially parse_message function
"""

import pytest
from src.services import parse_message, ParsedMessage


class TestParseMessage:
    """Test cases for parse_message function"""
    
    def test_simple_k_suffix(self):
        """Test parsing with 'k' suffix (thousands)"""
        result = parse_message("50k cafe")
        assert result.is_valid is True
        assert result.amount == 50_000
        assert result.note == "cafe"
    
    def test_tr_suffix(self):
        """Test parsing with 'tr' suffix (millions)"""
        result = parse_message("2tr tiền nhà")
        assert result.is_valid is True
        assert result.amount == 2_000_000
        assert result.note == "tiền nhà"
    
    def test_m_suffix(self):
        """Test parsing with 'm' suffix (millions)"""
        result = parse_message("1.5m điện")
        assert result.is_valid is True
        assert result.amount == 1_500_000
        assert result.note == "điện"
    
    def test_no_suffix(self):
        """Test parsing without suffix"""
        result = parse_message("10000 ăn sáng")
        assert result.is_valid is True
        assert result.amount == 10_000
        assert result.note == "ăn sáng"
    
    def test_decimal_with_k(self):
        """Test parsing decimal numbers with k suffix"""
        result = parse_message("2.5k nước")
        assert result.is_valid is True
        assert result.amount == 2_500
        assert result.note == "nước"
    
    def test_comma_decimal(self):
        """Test parsing with comma as decimal separator"""
        result = parse_message("1,5tr phí dịch vụ")
        assert result.is_valid is True
        assert result.amount == 1_500_000
        assert result.note == "phí dịch vụ"
    
    def test_uppercase_suffix(self):
        """Test parsing with uppercase suffix"""
        result = parse_message("100K grab")
        assert result.is_valid is True
        assert result.amount == 100_000
        assert result.note == "grab"
    
    def test_no_note(self):
        """Test parsing amount without note"""
        result = parse_message("50k")
        assert result.is_valid is True
        assert result.amount == 50_000
        assert result.note == ""
    
    def test_empty_string(self):
        """Test parsing empty string"""
        result = parse_message("")
        assert result.is_valid is False
        assert "trống" in result.error_message.lower()
    
    def test_whitespace_only(self):
        """Test parsing whitespace only"""
        result = parse_message("   ")
        assert result.is_valid is False
    
    def test_no_amount(self):
        """Test parsing text without amount"""
        result = parse_message("cafe sáng")
        assert result.is_valid is False
    
    def test_nghin_suffix(self):
        """Test parsing with 'nghìn' suffix"""
        result = parse_message("50nghìn bánh mì")
        assert result.is_valid is True
        assert result.amount == 50_000
        assert result.note == "bánh mì"
    
    def test_trieu_suffix(self):
        """Test parsing with 'triệu' suffix"""
        result = parse_message("3triệu điện thoại")
        assert result.is_valid is True
        assert result.amount == 3_000_000
        assert result.note == "điện thoại"
    
    def test_raw_text_preserved(self):
        """Test that raw_text is preserved"""
        original = "50k cafe sữa đá"
        result = parse_message(original)
        assert result.raw_text == original
    
    def test_multiword_note(self):
        """Test parsing with multi-word note"""
        result = parse_message("150k đi siêu thị mua đồ ăn")
        assert result.is_valid is True
        assert result.amount == 150_000
        assert result.note == "đi siêu thị mua đồ ăn"
    
    def test_large_amount(self):
        """Test parsing large amounts"""
        result = parse_message("50m mua xe")
        assert result.is_valid is True
        assert result.amount == 50_000_000
        assert result.note == "mua xe"


class TestParseMessageEdgeCases:
    """Edge case tests for parse_message"""
    
    def test_zero_amount(self):
        """Test parsing zero amount"""
        result = parse_message("0k test")
        assert result.is_valid is True
        assert result.amount == 0
    
    def test_extra_whitespace(self):
        """Test parsing with extra whitespace"""
        result = parse_message("  50k   cafe  ")
        assert result.is_valid is True
        assert result.amount == 50_000
        assert result.note == "cafe"
    
    def test_number_in_note(self):
        """Test parsing when note contains numbers"""
        result = parse_message("50k cafe 2 ly")
        assert result.is_valid is True
        assert result.amount == 50_000
        assert "cafe 2 ly" in result.note
