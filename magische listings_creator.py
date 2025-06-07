import json, subprocess, random
from datetime import date, datetime, timedelta
from math import trunc
from collections import defaultdict

# 🎲 Zorg voor consistente shuffle per dag
random.seed(date.today().isoformat())

def meta_lookup(uri):
	try:
		result = subprocess.run([
			'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', uri
		], capture_output=True, text=True, check=True)
		data = json.loads(result.stdout)
		duration = float(data['format']['duration'])
		return {"duration_seconds": duration}
	except Exception as e:
		print("Error loading '" + uri + "': " + str(e))
		return False

def json_load(uri):
	try:
		with open(uri) as f:
			return json.load(f)
	except Exception as e:
		print(f"Error loading '{uri}': {e}")
		return False

data = json_load("nmptv.json")

# 🔐 Backup
with open("nmptv.json.bak", "w") as f:
	f.write(json.dumps(data, indent=2))

print("Kanaal:", data["channel_name"])

filled_slots = []
shuffled_episode_lists = defaultdict(list)

for slot in data["template"]:
	list_name = slot["list"][0]

	# Shuffle als dit de eerste keer is
	if not shuffled_episode_lists[list_name]:
		programme_list = json_load(f"programme lists/{list_name}.json")
		if not programme_list or "episodes" not in programme_list:
			print(f"⚠️ Geen afleveringen in {list_name}")
			continue

		episodes = programme_list["episodes"][:]
		random.shuffle(episodes)
		shuffled_episode_lists[list_name] = {
			"info": programme_list,
			"episodes": episodes,
			"cursor": 0
		}

	entry = shuffled_episode_lists[list_name]

	if entry["cursor"] >= len(entry["episodes"]):
		random.shuffle(entry["episodes"])
		entry["cursor"] = 0

	episode = entry["episodes"][entry["cursor"]]
	entry["cursor"] += 1

	metadata = meta_lookup(data["base_url"] + episode["url"])
	if not metadata:
		print(f"❌ Fout bij metadata: {episode['url']}")
		continue

	programme_start_time = datetime.combine(datetime.now().date(), datetime.strptime(slot["start"], "%H:%M").time())

	selected_programme = {
		"start": slot["start"],
		"uri": data["base_url"] + episode["url"],
		"duration": metadata["duration_seconds"],
		"description": episode.get("description", entry["info"].get("description", "")),
		"title": entry["info"]["title"],
		"start_seconds": datetime.timestamp(programme_start_time)
	}

	filled_slots.append(selected_programme)

	# 📌 Bijwerken van index voor compatibiliteit
	slot["index"] = [0, entry["cursor"] - 1]

# 💾 Schrijf nieuwe indexen weg
with open("nmptv.json", "w") as f:
	f.write(json.dumps(data, indent=2))

# 🎬 Programma-opbouw
previous_end_time = None
command_output = []

command_output.append({"time": 0, "command": "PREVIEW", "scene": "Media 1"})
command_output.append({"time": 0, "command": "LOAD", "url": filled_slots[0]["uri"]})

for slot_index, slot_info in enumerate(filled_slots):
	programme_start_time = datetime.combine(datetime.now().date(), datetime.strptime(slot_info["start"], "%H:%M").time())
	programme_end_time = programme_start_time + timedelta(seconds=slot_info["duration"])

	# ⚠️ Waarschuwing bij overlap
	if previous_end_time and programme_start_time < previous_end_time:
		print(f"⚠️ Overlap: '{slot_info['title']}' begint om {programme_start_time}, vorige eindigt pas om {previous_end_time}")

	print(slot_info["uri"])
	print("Starts at", programme_start_time, "Ends at", programme_end_time)

	command_output.append({"time": datetime.timestamp(programme_start_time), "command": "PROGRAM", "scene": "Media 1"})

	if slot_index + 1 < len(filled_slots):
		next_slot_time = datetime.combine(datetime.now().date(), datetime.strptime(filled_slots[slot_index + 1]["start"], "%H:%M").time())
		fill_time = next_slot_time - programme_end_time
		print("Time to fill:", fill_time)

		if fill_time > timedelta(seconds=400):
			print("→ Fill: Ceefax")
			previous_end_time = next_slot_time
			command_output += [
				{"time": 0, "command": "PREVIEW", "scene": "Clock"},
				{"time": datetime.timestamp(programme_end_time), "command": "PROGRAM", "scene": "Clock"},
				{"time": 0, "command": "PREVIEW", "scene": "OS 1"},
				{"time": datetime.timestamp(programme_end_time) + 10, "command": "PROGRAM", "scene": "OS 1"},
				{"time": 0, "command": "PREVIEW", "scene": "Ident"},
				{"time": datetime.timestamp(previous_end_time) - 20, "command": "PROGRAM", "scene": "Ident"}
			]
		elif fill_time > timedelta(seconds=50):
			print("→ Fill: Breakfiller")
			bf_time = trunc((fill_time.total_seconds() - 20) / 30) * 30
			previous_end_time = programme_end_time + timedelta(seconds=bf_time + 20)
			command_output += [
				{"time": 0, "command": "PREVIEW", "scene": "Breakfiller"},
				{"time": datetime.timestamp(programme_end_time), "command": "PROGRAM", "scene": "Breakfiller"},
				{"time": 0, "command": "PREVIEW", "scene": "Ident"},
				{"time": datetime.timestamp(previous_end_time) - 15, "command": "PROGRAM", "scene": "Ident"}
			]
		elif fill_time > timedelta(seconds=15):
			print("→ Fill: Ident")
			previous_end_time = programme_end_time + timedelta(seconds=20)
			command_output += [
				{"time": 0, "command": "PREVIEW", "scene": "Ident"},
				{"time": datetime.timestamp(programme_end_time), "command": "PROGRAM", "scene": "Ident"}
			]
		else:
			print("→ Fill: Clock")
			previous_end_time = programme_end_time + timedelta(seconds=5)
			command_output += [
				{"time": 0, "command": "PREVIEW", "scene": "Clock"},
				{"time": datetime.timestamp(programme_end_time), "command": "PROGRAM", "scene": "Clock"}
			]

		command_output += [
			{"time": 0, "command": "PREVIEW", "scene": "Media 1"},
			{"time": 0, "command": "LOAD", "url": filled_slots[slot_index + 1]["uri"]}
		]
	else:
		previous_end_time = programme_end_time

	print("")

# 🔚 Eindeprogramma
command_output.append({"time": datetime.timestamp(programme_end_time), "command": "PROGRAM", "scene": "Ident"})
command_output.append({"time": datetime.timestamp(programme_end_time) + 20, "command": "PROGRAM", "scene": "OS 1"})

with open("command_output.json", "w") as f:
	f.write(json.dumps(command_output, indent=2))

# Optionele fallback
filled_slots.append({
	"duration": 43200,
	"start_seconds": 999999999999,
	"title": "Pages From Ceefax",
	"description": "Items of news and information from Ceefax, with music."
})
