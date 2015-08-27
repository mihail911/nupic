
#!/bin/bash
export NUPIC="/Users/numenta/Documents/nupic"
ARCHFLAGS="-arch x86_64" python setup.py develop --nupic-core-dir="~/Documents/nupic.core/build/release" --user 
#scripts/run_nupic_tests --all --coverage
