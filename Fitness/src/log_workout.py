from database import create_database, add_workout


create_database()

print("\nLog a Workout")
print("-------------")

workout_date = input("Date (YYYY-MM-DD): ")
exercise = input("Exercise: ")

weight = float(input("Weight (lb): "))
sets = int(input("Sets: "))
reps = int(input("Reps: "))
rpe = float(input("RPE: "))
pain = float(input("Pain (0-10): "))

notes = input("Notes: ")


add_workout(
    workout_date,
    exercise,
    weight,
    sets,
    reps,
    rpe,
    pain,
    notes
)


print("\nWorkout saved.")