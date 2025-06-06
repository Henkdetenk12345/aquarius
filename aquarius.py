import sched, time, json, socket

from datetime import datetime

from obswebsocket import obsws, requests

def json_load(uri):
	try:
		f = open(uri)
	except:
		print("Error opening '" + uri + "'")
		return False
	
	try:
		data = json.load(f)
	except:
		print("Error loading '" + uri + "'")
		return False
	
	f.close()
	
	return data

def prepare_VT(client,source_name,file_uri):
	# Load File Into VT
	client.call(requests.SetInputSettings(inputName=source_name, inputSettings={"local_file":file_uri}))
	client.call(requests.TriggerMediaInputAction(inputName=source_name, mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP"))	# Hit Stop

	time.sleep(1)	# Wait for file to load

	client.call(requests.TriggerMediaInputAction(inputName=source_name, mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"))	# Force load

	time.sleep(1)	# Wait for file to play

	client.call(requests.SetMediaInputCursor(inputName=source_name, mediaCursor=5000))	# Jump to T+05
	client.call(requests.TriggerMediaInputAction(inputName=source_name, mediaAction="OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE"))	# Hold at T+05

	media_state = client.call(requests.GetMediaInputStatus(inputName=source_name)).getMediaState()	# Check there's no error state here in future

def execute(command,client):
	print(command)
	
	if command["command"] == "PROGRAM":
		client.call(requests.SetCurrentProgramScene(sceneName=command["scene"]))
	elif command["command"] == "PREVIEW":
		client.call(requests.SetCurrentPreviewScene(sceneName=command["scene"]))
	elif command["command"] == "LOAD":
		prepare_VT(client,"VT 1",command["url"])

client = obsws("localhost", 4455, "ot47W7Di9SU72Vvl")
client.connect()

print(client.call(requests.GetVersion()).getObsVersion())

command_sched = sched.scheduler(time.time, time.sleep)

command_list = json_load("command_output.json")

caught_up = False
last_exp = 0
prev_time = 0

for index,command in enumerate(command_list):
	if command["time"] != 0 and command["time"] <= time.time():
		last_exp = index

for index,command in enumerate(command_list):
	if index > last_exp:
		if command["time"] == 0:
			print(command)
			print(prev_time)
			print()
			command_sched.enterabs(prev_time,10,execute,argument=(command,client))
		else:
			print(command)
			print(command["time"])
			print()
			command_sched.enterabs(command["time"],1,execute,argument=(command,client))
			prev_time = command["time"]

print(time.time())

while True:
	command_sched.run(blocking=False)
	time.sleep(1)
	
	print(time.time())
	print(command_sched.queue[0].time)
	print(command_sched.queue[0].time - time.time())
	print(command_sched.queue[0].argument[0]["command"])
	print("")