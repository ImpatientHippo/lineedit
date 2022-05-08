from setuptools import setup

with open("README.md","r") as f:
  long_desc = f.read()

setup( name = "lineedit",
  version = "0.1",
  description = "A simple editor for a single line",
  url = "https://github.com/ImpatientHippo/lineedit",
  author = "ImpatentHippo",
  author_email = "info@klawitter.de",
  license = "GPL",
  packages = [ "lineedit" ],
  long_description = long_desc
)
