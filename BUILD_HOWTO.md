This is a package to talk to duotecno ip interfaces

How to deploy a new version:

bumpver update
python -m build .
twine check dist/_
twine upload dist/_
