import secrets


def generate_special_random_number(min_val=1, max_val=100):
    """
    Generates a cryptographically secure (truly random) integer.
    Much stronger than random.randint() for security-sensitive or "special" use.
    """
    return secrets.randbelow(max_val - min_val + 1) + min_val


def main():
    print("🔮 Special Truly Random Number Guessing Game 🔮")
    print("=" * 55)

    # Generate the secret truly random number
    secret_number = generate_special_random_number(1, 100)
    print(f"A special truly random number between 1 and 100 has been generated!\n")

    attempts = 0
    max_attempts = 7  # You can change this

    while attempts < max_attempts:
        try:
            print(f"Attempt {attempts + 1}/{max_attempts}")
            num1 = int(input("Enter your first number guess: "))
            num2 = int(input("Enter your second number guess: "))

            user_sum = num1 + num2
            attempts += 1

            if user_sum == secret_number:
                print(f"\n🎉 Congratulations! You got it!")
                print(f"{num1} + {num2} = {secret_number}")
                print(f"It took you {attempts} attempt(s).")
                break
            elif user_sum < secret_number:
                print(f"Too low! Your sum ({user_sum}) is less than the secret number.\n")
            else:
                print(f"Too high! Your sum ({user_sum}) is greater than the secret number.\n")

        except ValueError:
            print("❌ Please enter valid integers only.\n")
            continue

    else:
        # This runs if the loop ends without a break (out of attempts)
        print(f"\n😔 Game over! You've used all {max_attempts} attempts.")

    print(f"\nThe special truly random number was: {secret_number}")


if __name__ == "__main__":
    main()
