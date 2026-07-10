with open('generate_audio.py', 'r') as f:
    c = f.read()
c = c.replace('\\\'', "'")
c = c.replace('\\"', '"')
with open('generate_audio.py', 'w') as f:
    f.write(c)
