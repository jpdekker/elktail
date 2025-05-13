import os
import sys
from setuptools import setup
from distutils.command.install import install as _install


def _post_install(dir):
    from subprocess import call
    print(os.path.join(dir, 'elktail'))
    call([sys.executable, 'create_bin.py', os.path.join(dir, 'elktail')],
         cwd=os.path.join(dir, 'elktail'))
    call([f"pip install -r etc/requirements.txt --no-clean"], shell=True)


class install(_install):
    def run(self):
        _install.run(self)
        self.execute(_post_install, (self.install_lib,),
                     msg="Running post install task. Generating exec")


setup(
    name="elktail",
    version="1.1",
    author="Jan Paul Dekker",
    author_email="jpdekker@decco.net",
    license='GPLv2',
    classifiers=[
        'Development Status :: 5 - Beta',
        'Intended Audience :: DevOps & Developers',
        'Topic :: DevOps administrative tools',
        'Programming Language :: Python :: 3.8'
    ],
    keywords='elk elasticsearch filebeat tail-like',
    description="simple tailf to filebeat indexes in elasticsearch",
    cmdclass={'install': install},
    packages=["elktail"]
)
