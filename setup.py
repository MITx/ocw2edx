import glob
from setuptools import setup

def findfiles(pat):
    return [x for x in glob.glob('share/' + pat)]

data_files = [
#    ('share/render', findfiles('render/*')),
    ]

# print "data_files = %s" % data_files

setup(
    name='ocw2edx',
    version='0.1',
    author='I. Chuang',
    author_email='ichuang@mit.edu',
    packages=['ocw2edx'],
    scripts=[],
    url='https://github.com/MITx/ocw2edx',
    license='LICENSE',
    description='Convert MIT OpenCourseWare content download file to OLX format for import into edX-platform instance',
    long_description=open('README.md').read(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'ocw2edx = ocw2edx.main:CommandLine',
            ],
        },
    install_requires=['path.py',
                      'argparse',
		      'BeautifulSoup',
                      'lxml',
                      'pyaml',
                      'requests',
                      'jinja2',
                      ],
    dependency_links = [
        ],
    package_dir={'ocw2edx': 'ocw2edx'},
    package_data={'ocw2edx': ['lib/*', 'bin/*'] },
    # package_data={ 'ocw2edx': ['python_lib/*.py'] },
    # data_files = data_files,
    test_suite = "ocw2edx.test",
)
