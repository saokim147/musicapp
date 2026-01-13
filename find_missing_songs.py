#!/usr/bin/env python3
"""
Find songs in group_to_title.csv that are not in preprocessed/train/song/ folder.
Outputs results to test.csv
"""
import csv
import os
from pathlib import Path


def main():
    # Paths
    csv_path = Path("/home/thinv/musicapp/preprocessed/group_to_title.csv")
    song_folder = Path("/home/thinv/musicapp/preprocessed/train/song")
    output_path = Path("/home/thinv/musicapp/test.csv")

    # Read all group_ids from the CSV
    csv_group_ids = set()
    csv_rows = {}  # group_id -> title mapping

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            group_id = row['group_id']
            title = row['title']
            csv_group_ids.add(group_id)
            csv_rows[group_id] = title

    # Get unique group_ids from .npy files in song folder
    # Files are named: {group_id}_{fragment_id}_{id}.npy
    folder_group_ids = set()

    if song_folder.exists():
        for file in song_folder.glob("*.npy"):
            # Extract group_id (part before first underscore)
            group_id = file.name.split('_')[0]
            folder_group_ids.add(group_id)
    else:
        print(f"Warning: {song_folder} does not exist!")

    # Find group_ids in CSV but not in folder
    missing_group_ids = csv_group_ids - folder_group_ids

    # Write missing songs to test.csv
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['group_id', 'title'])
        writer.writeheader()

        for group_id in sorted(missing_group_ids):
            writer.writerow({
                'group_id': group_id,
                'title': csv_rows[group_id]
            })

    print(f"Total songs in CSV: {len(csv_group_ids)}")
    print(f"Unique group_ids in song folder: {len(folder_group_ids)}")
    print(f"Missing songs (written to test.csv): {len(missing_group_ids)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
