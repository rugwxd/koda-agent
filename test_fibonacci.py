"""
Tests for the Fibonacci sequence implementations.
"""

import pytest
from fibonacci import (
    fibonacci_iterative,
    fibonacci_recursive,
    fibonacci_generator,
    fibonacci_memoized
)


class TestFibonacci:
    """Test cases for Fibonacci implementations."""
    
    def test_fibonacci_iterative(self):
        """Test the iterative implementation."""
        assert fibonacci_iterative(0) == []
        assert fibonacci_iterative(1) == [0]
        assert fibonacci_iterative(2) == [0, 1]
        assert fibonacci_iterative(5) == [0, 1, 1, 2, 3]
        assert fibonacci_iterative(10) == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
    
    def test_fibonacci_recursive(self):
        """Test the recursive implementation."""
        assert fibonacci_recursive(0) == 0
        assert fibonacci_recursive(1) == 1
        assert fibonacci_recursive(2) == 1
        assert fibonacci_recursive(5) == 5
        assert fibonacci_recursive(10) == 55
    
    def test_fibonacci_generator(self):
        """Test the generator implementation."""
        assert list(fibonacci_generator(0)) == []
        assert list(fibonacci_generator(1)) == [0]
        assert list(fibonacci_generator(5)) == [0, 1, 1, 2, 3]
        assert list(fibonacci_generator(10)) == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
    
    def test_fibonacci_memoized(self):
        """Test the memoized implementation."""
        assert fibonacci_memoized(0) == 0
        assert fibonacci_memoized(1) == 1
        assert fibonacci_memoized(2) == 1
        assert fibonacci_memoized(5) == 5
        assert fibonacci_memoized(10) == 55
        assert fibonacci_memoized(20) == 6765
    
    def test_consistency_between_methods(self):
        """Test that all methods produce consistent results."""
        n = 8
        iterative_result = fibonacci_iterative(n)
        generator_result = list(fibonacci_generator(n))
        
        assert iterative_result == generator_result
        
        # Check individual values match recursive and memoized
        for i in range(n):
            assert fibonacci_recursive(i) == fibonacci_memoized(i)
            assert iterative_result[i] == fibonacci_recursive(i)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])