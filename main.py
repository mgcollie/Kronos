import os
import requests
import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as path_effects
from dotenv import load_dotenv
load_dotenv()

# Timeular API setup
API_ENDPOINT = "https://api.timeular.com/api/v3"
API_KEY = os.getenv('TIMEULAR_API_KEY')
API_SECRET = os.getenv('TIMEULAR_API_SECRET')
OBSIDIAN_ROOT = os.getenv('OBSIDIAN_ROOT', r'C:\Users\mgcol\Dropbox\obsidian\obsidian')


# Authenticate and get token
def get_token(api_key, api_secret):
    response = requests.post(
        f"{API_ENDPOINT}/developer/sign-in",
        json={"apiKey": api_key, "apiSecret": api_secret},
    )
    response.raise_for_status()
    return response.json()["token"]


def pad_isoformat(timestamp):
    parts = timestamp.split('.')
    if len(parts) == 2:
        while len(parts[1]) < 3:
            parts[1] += '0'
        return '.'.join(parts)
    return timestamp


def fetch_activity_names_and_colors(token):
    url = "https://api.timeular.com/api/v3/activities"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return {activity["id"]: (activity["name"], activity["color"]) for activity in data["activities"]}


def fetch_yesterdays_activities(token):
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    # Adjust the timestamp format to include milliseconds
    start_time = yesterday.strftime('%Y-%m-%dT00:00:00.000')
    end_time = yesterday.strftime('%Y-%m-%dT23:59:59.999')

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_ENDPOINT}/time-entries/{start_time}/{end_time}",
        headers=headers,
    )
    response.raise_for_status()

    time_entries = response.json()["timeEntries"]
    return time_entries


def calculate_y_position(i):
    y_position = 0.65 - i * 0.1
    return y_position


# Visualize activities
def visualize_activities(token: str, activities: list) -> None:
    """
    Visualize the provided activities using a donut chart and two columns for activity names and durations.

    :param token: Authentication token
    :param activities: List of activities to visualize
    """
    activity_details = fetch_activity_names_and_colors(token)

    facecolor = '#1e1e1e'

    # Accumulate the durations for each unique activity
    accumulated_durations = {}
    for activity in activities:
        activity_id = activity["activityId"]
        start_time = datetime.datetime.fromisoformat(pad_isoformat(activity["duration"]["startedAt"][:-1]))
        stop_time = datetime.datetime.fromisoformat(pad_isoformat(activity["duration"]["stoppedAt"][:-1]))
        duration = (stop_time - start_time).seconds / 60

        if activity_id in accumulated_durations:
            accumulated_durations[activity_id] += duration
        else:
            accumulated_durations[activity_id] = duration

    # Extract the labels, colors, and accumulated durations for plotting
    labels = [activity_details[activity_id][0] for activity_id in accumulated_durations.keys()]
    colors = [activity_details[activity_id][1] for activity_id in accumulated_durations.keys()]
    durations = list(accumulated_durations.values())
    total_duration_minutes = sum(durations)
    total_time_str = f"{int(total_duration_minutes // 60)}h {int(total_duration_minutes % 60)}m"

    fig, axs = plt.subplots(1, 3, figsize=(12, 5), gridspec_kw={'width_ratios': [.5, .5, .5]}, facecolor=facecolor)

    # Donut chart
    axs[0].pie(durations, wedgeprops=dict(width=0.17), colors=colors)
    axs[0].axis('off')
    axs[0].text(0, 0, total_time_str, fontweight='bold', ha='center', va='center', fontsize=32, color='white')
    axs[0].set_facecolor(facecolor)
    axs[0].set_aspect('equal')

    # Activity names with colored icons
    axs[1].text(0, .75, "Activity", verticalalignment='top', fontsize=14, fontweight='bold', color='silver')
    for i, (label, color) in enumerate(zip(labels, colors)):
        y_position = calculate_y_position(i)
        axs[1].text(0.075, y_position, label, verticalalignment='center', fontsize=12, fontweight='bold', color='white',
                    ha='left')
        icon = patches.Circle((0.030, y_position), radius=0.025, color=color, transform=axs[1].transAxes)
        axs[1].add_patch(icon)
    axs[1].set_facecolor(facecolor)
    axs[1].set_aspect('equal')

    # Time durations with colored backgrounds
    axs[2].text(1, .75, "Time", verticalalignment='top', fontsize=14, fontweight='bold', color='silver', ha='right')
    for i, duration in enumerate(durations):
        y_position = calculate_y_position(i)
        color = colors[i]  # Use the same color as used for the activity label
        background = patches.Rectangle((.78, y_position - 0.04), 1, 0.08, facecolor=color, transform=axs[2].transAxes)
        axs[2].add_patch(background)
        axs[2].text(0.99, y_position, f"{int(duration // 60)}h {int(duration % 60)}m", verticalalignment='center',
                    fontsize=12, color='white', fontweight='bold', ha='right').set_path_effects(
            [path_effects.SimpleLineShadow(linewidth=2), path_effects.Normal()])
    axs[2].set_facecolor(facecolor)
    axs[2].set_aspect('equal')

    axs[1].axis('off')
    axs[2].axis('off')

    plt.tight_layout()
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    obsidian_root = os.environ.get("OBSIDIAN_ROOT")
    filename = os.path.join(obsidian_root, 'Media', 'Images', yesterday.strftime('%Y-%m-%d-timeular.png'))
    plt.savefig(filename, facecolor=facecolor)
    plt.show()


def insert_image_into_obsidian_note():
    # Get the OBSIDIAN_ROOT from the environment variable
    obsidian_root = os.environ.get("OBSIDIAN_ROOT")
    if not obsidian_root:
        raise ValueError("OBSIDIAN_ROOT environment variable not set!")

    # Calculate the filename for "yesterday"
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    note_filename = os.path.join(obsidian_root, yesterday.strftime('%Y-%m-%d.md'))
    image_filename = yesterday.strftime('%Y-%m-%d-timeular.png')

    # Check if the note file exists
    if not os.path.exists(note_filename):
        raise FileNotFoundError(f"{note_filename} not found!")

    # Read the contents of the file
    with open(note_filename, 'r') as file:
        content = file.readlines()

    # Locate the line with "# Timeular" and insert the image link on the next line
    for index, line in enumerate(content):
        if line.strip() == "# Timeular":
            content.insert(index + 1, f'![[{image_filename}]]\n')
            break
    else:
        raise ValueError("# Timeular header not found in the note!")

    # Write the modified content back to the file
    with open(note_filename, 'w') as file:
        file.writelines(content)


def main():
    token = get_token(API_KEY, API_SECRET)
    activities = fetch_yesterdays_activities(token)
    visualize_activities(token, activities)
    insert_image_into_obsidian_note()


if __name__ == "__main__":
    main()
