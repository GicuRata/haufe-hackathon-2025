def add_numbers(a, b):
    """Add two numbers and return the result."""
    return a + b

def multiply_numbers(a, b):
    """Multiply two numbers and return the result."""
    return a * b

def main():
    print("Simple Calculator")
    print("-" * 20)
    
    num1 = float(input("Enter first number: "))
    num2 = float(input("Enter second number: "))
    
    print(f"\n{num1} + {num2} = {add_numbers(num1, num2)}")
    print(f"{num1} * {num2} = {multiply_numbers(num1, num2)}")

if __name__ == "__main__":
    main()

