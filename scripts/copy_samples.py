import os
import machine

os.mount(machine.SDCard(1), '/sd')

for d in ('/flash/samples', '/flash/samples/160'):
    try:
        os.mkdir(d)
    except OSError:
        pass  # already exists

src_dir = '/sd/samples/160'
dst_dir = '/flash/samples'
files = sorted(f for f in os.listdir(src_dir) if f.endswith('.wav'))
print(f'copying {len(files)} files to internal flash...')

CHUNK = 4096
for f in files:
    print(f'  {f}')
    with open(f'{src_dir}/{f}', 'rb') as src, open(f'{dst_dir}/{f}', 'wb') as dst:
        while buf := src.read(CHUNK):
            dst.write(buf)

print('done')
