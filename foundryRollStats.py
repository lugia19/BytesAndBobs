import json

import numpy as np
import matplotlib.pyplot as plt


#Needs to be filled in, you can get them all by doing game.users in the browser console while on foundry - it will skip users that aren't listed in here.
usernames = {
    "userID": "username",
}

messages_db_path = r"C:\Users\lugia19\Desktop\messages-dnd.db"

def get_rolls_by_user(filepath) -> dict:
    users = {}  # Store rolls per user

    with open(filepath, 'r') as file:
        for line in file:
            data = json.loads(line)

            user_id = data.get("user")
            if user_id is None or user_id not in usernames:
                continue  # Skip lines without a user ID
            if not user_id in users:
                users[user_id] = dict()
                users[user_id]["rolls"] = list()
                users[user_id]["hits"] = 0
                users[user_id]["misses"] = 0
                users[user_id]["lancer_crits"] = 0
            content = data.get("content")
            if "misses</strong>" in content or "MISS</span>" in content:
                users[user_id]["misses"] += 1

            if "hits</strong>" in content or "HIT</span>" in content:
                users[user_id]["hits"] += 1

            if "CRIT</span>" in content:
                users[user_id]["lancer_crits"] += 1
                users[user_id]["hits"] += 1

            rolls = data.get("rolls")
            if not rolls:
                rolls = data.get("roll")
            if rolls:
                user_stats = []
                if isinstance(rolls, str):
                    rolls = [rolls]
                for roll in rolls:
                    try:
                        roll = json.loads(roll)  # If rolls is a string, parse it
                    except json.JSONDecodeError:
                        pass  # Ignore it if it's not valid JSON

                    for term in roll.get("terms", []):
                        if "rolls" in term and len(term["rolls"]) > 0:
                            for inner_roll in term["rolls"]:
                                for inner_term in inner_roll["terms"]:
                                    if inner_term.get("class") == "Die" and inner_term.get("faces") == 20:
                                        for result in inner_term.get("results", []):
                                            user_stats.append(result["result"])

                        if term.get("class") == "Die" and term.get("faces") == 20:
                            for result in term.get("results", []):
                                user_stats.append(result["result"])
                users[user_id]["rolls"].extend(user_stats)

    return users

def print_roll_stats(users):
    # Process collected rolls
    total_len = 0
    for user_id, user_stats in users.items():
        if user_stats['rolls']:
            user_rolls = user_stats['rolls']
            total_len += len(user_rolls)
            average_roll = sum(user_rolls) / len(user_rolls)
            num_twenties = user_rolls.count(20)
            num_ones = user_rolls.count(1)

            print(f"User: {usernames[user_id]} - {user_id}")
            
            print(f"Number of rolls: {len(user_rolls)}")
            print(f"Average Roll: {average_roll:.2f}")  # Format to 2 decimal places
            print(f"Number of 20s: {num_twenties} ({(num_twenties/len(user_rolls)*100):.2f}% of total)")
            print(f"Number of 1s: {num_ones} ({(num_ones/len(user_rolls)*100):.2f}% of total)")

            standard_deviation = np.std(user_rolls)
            print(f"Standard Deviation: {standard_deviation:.2f}")

        else:
            print(f"UserID: {user_id} - No valid rolls found")

        total_attacks = user_stats['hits'] + user_stats['misses']
        if total_attacks > 0:
            print(f"Attacks: {total_attacks}")
            print(f"Hits: {user_stats['hits']} ({(user_stats['hits']/total_attacks*100):.2f}%)")
            print(f"Misses: {user_stats['misses']} ({(user_stats['misses']/total_attacks*100):.2f}%)")
            if user_stats["lancer_crits"] > 0:
                print(f"Crits (LANCER, so just a roll over 20): {user_stats['lancer_crits']} ({(user_stats['lancer_crits']/total_attacks*100):.2f}%)")
        print("")
    print(f"Total rolls: {total_len}")

def generate_user_roll_graph(users:dict):
    """Generates a bar graph of roll frequencies for a given user."""
    rolls = range(1, 21)
    width = 0.8 / len(users.keys())

    fig, ax = plt.subplots(figsize=(12, 6))

    for i, (user_id, user_stats) in enumerate(users.items()):
        total_rolls = len(user_stats['rolls'])
        roll_counts = {roll: 0 for roll in rolls}
        for roll in user_stats['rolls']:
            roll_counts[roll] += 1

        # Calculate percentages
        roll_percentages = [count / total_rolls * 100 for count in roll_counts.values()]

        x_positions = np.arange(1, 21) + i * width - width / 2
        ax.bar(x_positions, roll_percentages, width, label=usernames[user_id])

    ax.set_xlabel("Roll Value")
    ax.set_ylabel("Roll Percentage (%)")  # Update y-axis label
    ax.set_title("Roll Distributions for All Players (Percentage)")
    ax.set_xticks(range(1, 21))
    ax.legend()
    plt.show()

def main():
    user_data = get_rolls_by_user(messages_db_path)
    print_roll_stats(user_data)
    generate_user_roll_graph(user_data)

if __name__=="__main__":
    main()