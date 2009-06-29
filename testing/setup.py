from setuptools import setup, find_packages

setup(name="debmarshal",
      version="0.0.0",
      description="Virtualization-based testing framework",
      author="Evan Broder",
      author_email="ebroder@google.com",
      url="http://code.google.com/p/debmarshal/",
      packages=find_packages(),
      long_description="""
The Debmarshal testing framework is designed to make it easy to test
entire systems and interactions between multiple systems. It uses
libvirt and other virtualization techniques to build entire platforms
for running automated tests in an environment isolated from the
outside world.
"""
)
