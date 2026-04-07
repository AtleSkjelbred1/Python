import secrets

rand = secrets.randbelow(100) + 1

a = int(input("Tall 1: "))
b = int(input("Tall 2: "))

if a + b == rand:
    print("Riktig!")
else:
    print("Feil!")

print("Fasit:", rand)
