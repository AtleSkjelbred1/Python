import secrets


def random_sum_challenge():
    # Generate a truly random number between 1 and 100
    # secrets.randbelow(n) returns a random int in the range [0, n)
    target_number = secrets.randbelow(100) + 1

    print("--- The Truly Random Challenge ---")
    print("A secret number between 1 and 100 has been generated.")

    try:
        # Prompt user for two numbers
        num1 = int(input("Enter your first guess: "))
        num2 = int(input("Enter your second guess: "))

        user_sum = num1 + num2

        # Evaluate the results
        print(f"\nYour total: {num1} + {num2} = {user_sum}")
        print(f"The secret number was: {target_number}")

        if user_sum == target_number:
            print("Success! Your sum matches the random number.")
        else:
            print("No match. Better luck next time!")

    except ValueError:
        print("Invalid input. Please enter whole numbers only.")


if __name__ == "__main__":
    random_sum_challenge()
