import shutil
import sys
import subprocess

print("Copying binaries")
try:
    shutil.copyfile(f"{sys.argv[1]}/elktail.py", '/usr/bin/elktail')
    subprocess.call(['chmod', 'a+x', '/usr/bin/elktail'])
except IOError:
    print ("Run this as root")
