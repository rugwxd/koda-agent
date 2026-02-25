"""
Fibonacci Sequence Generator

This module provides different implementations to generate the Fibonacci sequence.
The Fibonacci sequence starts with 0 and 1, and each subsequent number is the sum
of the two preceding ones: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, ...
"""


def fibonacci_iterative(n):
    """
    Generate the first n numbers of the Fibonacci sequence using iteration.
    
    Args:
        n (int): Number of Fibonacci numbers to generate
        
    Returns:
        list: List containing the first n Fibonacci numbers
    """
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib_sequence = [0, 1]
    for i in range(2, n):
        next_fib = fib_sequence[i-1] + fib_sequence[i-2]
        fib_sequence.append(next_fib)
    
    return fib_sequence


def fibonacci_recursive(n):
    """
    Calculate the nth Fibonacci number using recursion.
    
    Args:
        n (int): Position in the Fibonacci sequence (0-indexed)
        
    Returns:
        int: The nth Fibonacci number
    """
    if n <= 1:
        return n
    return fibonacci_recursive(n-1) + fibonacci_recursive(n-2)


def fibonacci_generator(n):
    """
    Generate Fibonacci numbers using a generator function.
    
    Args:
        n (int): Number of Fibonacci numbers to generate
        
    Yields:
        int: Next Fibonacci number in the sequence
    """
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b


def fibonacci_memoized(n, memo={}):
    """
    Calculate the nth Fibonacci number using memoization for efficiency.
    
    Args:
        n (int): Position in the Fibonacci sequence (0-indexed)
        memo (dict): Memoization dictionary to store computed values
        
    Returns:
        int: The nth Fibonacci number
    """
    if n in memo:
        return memo[n]
    
    if n <= 1:
        return n
    
    memo[n] = fibonacci_memoized(n-1, memo) + fibonacci_memoized(n-2, memo)
    return memo[n]


def main():
    """
    Demonstrate different Fibonacci implementations.
    """
    print("Fibonacci Sequence Generator")
    print("=" * 40)
    
    n = 10
    print(f"\nFirst {n} Fibonacci numbers:")
    
    # Using iterative approach
    print(f"Iterative: {fibonacci_iterative(n)}")
    
    # Using generator
    print(f"Generator: {list(fibonacci_generator(n))}")
    
    # Using recursive approach for individual numbers
    print(f"Recursive (first 10): {[fibonacci_recursive(i) for i in range(n)]}")
    
    # Using memoized approach for larger numbers
    print(f"\nLarger Fibonacci numbers using memoization:")
    for i in [20, 30, 40]:
        print(f"F({i}) = {fibonacci_memoized(i)}")
    
    # Performance comparison for a specific number
    import time
    
    print(f"\nPerformance comparison for F(35):")
    
    # Memoized (fast)
    start = time.time()
    result_memo = fibonacci_memoized(35)
    time_memo = time.time() - start
    print(f"Memoized: {result_memo} (Time: {time_memo:.6f} seconds)")
    
    # Recursive (slow for large numbers)
    start = time.time()
    result_recursive = fibonacci_recursive(35)
    time_recursive = time.time() - start
    print(f"Recursive: {result_recursive} (Time: {time_recursive:.6f} seconds)")


if __name__ == "__main__":
    main()