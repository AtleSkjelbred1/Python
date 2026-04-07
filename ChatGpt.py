import secrets

# Generate a "truly random" number (cryptographically secure)
random_number = secrets.randbelow(100) + 1  # Random number between 1 and 100

print("A random number has been generated between 1 and 100.")

# Get user input
try:
    num1 = int(input("Enter your first guess number: "))
    num2 = int(input("Enter your second guess number: "))

    user_sum = num1 + num2

    print(f"Your sum: {user_sum}")
    print(f"Random number: {random_number}")

    # Check if the sum matches the random number
    if user_sum == random_number:
        print("Correct! Your numbers add up to the random number 🎉")
    else:
        print("Wrong! The sum does not match the random number.")

except ValueError:
    print("Please enter valid integers.")
