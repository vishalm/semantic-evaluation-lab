with open('Makefile', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines[225:235], 226):
    print(f'{i}: {repr(line)}') 