import argparse
import datetime
import logging
import os
import sys
import requests
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as path_effects
from dotenv import load_dotenv
from typing import Dict, Tuple, List, Union
from schema import Schema, And, Use

# Setup logging
logger = logging.getLogger(__name__)

# Constants
API_ENDPOINT = "https://api.timeular.com/api/v3"

# Load environment variables
load_dotenv()

API_KEY = os.getenv('TIMEULAR_API_KEY')
API_SECRET = os.getenv('TIMEULAR_API_SECRET')
OBSIDIAN_VAULT = os.getenv('OBSIDIAN_VAULT', r'C:\Users\mgcol\Dropbox\obsidian\obsidian')


def setup_logging(log_level: str) -> None:
    """
    Configure logging based on the provided log level.

    :param log_level: The log level to use.
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(levelname)s - %(message)s')


def valid_date(date_string: str) -> str:
    """
    Validate that the provided string is in the format "YYYY-MM-DD".

    :param date_string: Date string to be checked.
    :return: Date string if valid.
    :raises: SchemaError if the format is invalid.
    """
    date_schema = Schema(And(Use(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').strftime('%Y-%m-%d')), str))
    return date_schema.validate(date_string)


def parse_args():
    """
    This function is responsible for parsing the command line interface of this program.

    :return: Namespace object with parsed arguments.
    """
    parser = argparse.ArgumentParser()
    # Default to "yesterday" if no date argument is provided
    default_date = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    parser.add_argument('-d', '--date', default=default_date, type=valid_date, help="Date in the format 'YYYY-MM-DD'")
    parser.add_argument('-f', '--facecolor', default='#1e1e1e', help="Background color for the visualization. "
                                                                     "Defaults to '#1e1e1e'.")
    parser.add_argument('-l', '--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set the logging level.')
    return parser.parse_args()


# Authenticate and get token
def get_token(api_key: str, api_secret: str) -> str:
    """
    Authenticate and get the Timeular API token.

    :param api_key: The API key.
    :param api_secret: The API secret.
    :return: The API token.
    :raises: HTTPError if the request fails.
    """
    response = requests.post(
        f"{API_ENDPOINT}/developer/sign-in",
        json={"apiKey": api_key, "apiSecret": api_secret},
    )
    response.raise_for_status()
    return response.json()["token"]


def pad_isoformat(timestamp: str) -> str:
    """
    Pads ISO formatted timestamp to ensure milliseconds precision.

    :param timestamp: The timestamp string.
    :return: Padded timestamp string.
    """
    parts = timestamp.split('.')
    if len(parts) == 2:
        while len(parts[1]) < 3:
            parts[1] += '0'
        return '.'.join(parts)
    return timestamp


def fetch_activity_names_and_colors(token: str) -> Dict[str, Tuple[str, str]]:
    """
    Fetch activity names and their respective colors.

    :param token: The API token.
    :return: Dictionary with activity ID as key and tuple (name, color) as value.
    :raises: HTTPError if the request fails.
    """
    url = f"{API_ENDPOINT}/activities"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return {activity["id"]: (activity["name"], activity["color"]) for activity in data["activities"]}


def fetch_activities(token: str, date: str) -> List[Dict[str, Union[str, Dict[str, str]]]]:
    """
    Fetch activities from Timeular API for the specified date or yesterday if no date is provided.

    :param token: The API token.
    :param date: The date string in "YYYY-MM-DD" format.
    :return: List of activity dictionaries.
    :raises: HTTPError if the request fails.
    """
    # Convert the date string to a datetime.date object for easier manipulation
    target_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    start_time = target_date.strftime('%Y-%m-%dT00:00:00.000')
    end_time = target_date.strftime('%Y-%m-%dT23:59:59.999')

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_ENDPOINT}/time-entries/{start_time}/{end_time}",
        headers=headers,
    )
    response.raise_for_status()

    time_entries = response.json()["timeEntries"]
    return time_entries


def calculate_y_position(i: int) -> float:
    """
    Calculate y-position for visualization.

    :param i: Index of the activity.
    :return: y-position.
    """
    y_position = 0.65 - i * 0.1
    return y_position


# Visualize activities
def create_visualization_of_daily_activities(token: str, activities: List[Dict[str, Union[str, Dict[str, str]]]],
                                             date: str, facecolor: str = '#1e1e1e') -> None:
    """
    Visualize activities using matplotlib.

    :param token: The API token.
    :param activities: List of activity dictionaries.
    :param date: The date string in "YYYY-MM-DD" format.
    :param facecolor: Background color for the visualization. Defaults to '#1e1e1e'.
    """
    activity_details = fetch_activity_names_and_colors(token)

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
    axs[2].text(.92, .75, "Time", verticalalignment='top', fontsize=14, fontweight='bold', color='silver', ha='right')
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
    # Use the provided date for filename
    target_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    obsidian_root = os.environ.get("OBSIDIAN_VAULT")
    filename = os.path.join(obsidian_root, 'Media', 'Images', target_date.strftime('%Y-%m-%d-timeular.png'))
    plt.savefig(filename, facecolor=facecolor)
    plt.show()


def insert_image_into_obsidian_note(date: str) -> None:
    """
    Insert an image into an Obsidian note. This function is idempotent.

    :raises:
        ValueError: If OBSIDIAN_VAULT environment variable is not set or # Timeular header is not found in the note.
        FileNotFoundError: If the note file does not exist.
    """
    # Get the OBSIDIAN_VAULT from the environment variable
    obsidian_root = os.environ.get("OBSIDIAN_VAULT")
    if not obsidian_root:
        raise ValueError("OBSIDIAN_VAULT environment variable not set!")

    # Calculate the filename for "date"
    note_filename = os.path.join(obsidian_root, f'{date}.md')
    image_filename = f'{date}-timeular.png'
    image_link = f'![[{image_filename}]]\n'

    # Check if the note file exists
    if not os.path.exists(note_filename):
        # Check to see if the archived version is available
        archived = os.path.join(obsidian_root, 'Daily Notes', f'{date}.md')
        logger.warning(f"Note file {note_filename} does not exist! Checking for archived: {archived} version...")
        if not os.path.exists(archived):
            raise FileNotFoundError(f"neither {archived} or {note_filename} exist!")
        else:
            note_filename = archived

    # Read the contents of the file
    with open(note_filename, 'r') as file:
        content = file.readlines()

    # Check if the image link is already present
    if image_link in content:
        logger.info(f"Image link {image_link} already present in the note. Nothing to do...")
        return

    # Locate the line with "# Timeular" and insert the image link on the next line
    for index, line in enumerate(content):
        if line.strip() == "# Timeular":
            content.insert(index + 1, image_link)
            break
    else:
        raise ValueError("# Timeular header not found in the note!")

    # Write the modified content back to the file
    with open(note_filename, 'w') as file:
        file.writelines(content)


def main() -> int:
    """
    Main function to execute the entire workflow.

    :return: 0 if successful
    :raises: requests.RequestException if the API request fails
    """
    args = parse_args()

    # Set up logging
    setup_logging(args.log_level)

    try:
        token = get_token(API_KEY, API_SECRET)
        activities = fetch_activities(token, args.date)
        create_visualization_of_daily_activities(token, activities, args.date, args.facecolor)
        insert_image_into_obsidian_note(args.date)
    except requests.RequestException as e:
        logger.error(f'API Request failed: {e}')
        raise e
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        raise e

    return 0


if __name__ == "__main__":
    sys.exit(main())
