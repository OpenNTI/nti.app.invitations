import codecs
from setuptools import setup
from setuptools import find_packages

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.app',
    ],
    'console_scripts': [
    ],
}

TESTS_REQUIRE = [
    'fudge',
    'nti.app.testing',
    'nti.testing',
    'zope.testrunner',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.invitations',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="NTI app invitations",
    long_description=(
        _read('README.rst') 
        + '\n\n' 
        + _read("CHANGES.rst")
    ),
    license='Apache',
    keywords='pyramid invitations',
    classifiers=[
        'Framework :: Zope3',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.app.invitations",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'nti.externalization',
        'nti.invitations',
        'nti.links',
        'nti.property',
        'requests',
        'pyramid',
        'six',
        'zc.intid',
        'zope.cachedescriptors',
        'zope.component',
        'zope.event',
        'zope.generations',
        'zope.i18nmessageid',
        'zope.intid',
        'zope.interface',
        'zope.location',
        'zope.security',
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ],
    },
    entry_points=entry_points,
)
