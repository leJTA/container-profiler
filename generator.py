import random

N = 20

dates = []
prog_ids = []

name_choices = ["blur", "effect", "speech_recognition", "resize"]
cmds = [
	"python3 /home/ubuntu/python/blur.py {} 30",
	"python3 /home/ubuntu/python/effects.py {}",
	"python3 /home/ubuntu/python/speech_rec.py {}",
	"python3 /home/ubuntu/python/resize.py {}"
]
filenames = [
	"/home/ubuntu/files/image.jpg",
	"/home/ubuntu/files/audio.wav",
	"/home/ubuntu/files/podcast_1-2.wav",
	"/home/ubuntu/files/video.mp4"
]

weights = [0.4, 0.2, 0.1, 0.3]
#weights = [0.2, 0.2, 0.2, 0.4] # 40% noisy 40% Cache Sensitive 10% Other
#weights = [0.1, 0.1, 0.1, 0.7] # 70% noisy 20% Cache Sensitive 10% Other

d = 0
for i in range(N):
	d += random.expovariate(2)
	dates.append(d)
	
prog_ids = random.choices([0, 1, 2, 3], weights, k=N)

for i in range(N):
	id = prog_ids[i]
	print(f"ubuntu{i+1};{round(dates[i], 2)};{name_choices[id]};{cmds[id]};{filenames[id]}")
