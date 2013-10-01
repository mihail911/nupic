#! /usr/bin/env python
# ----------------------------------------------------------------------
#  Copyright (C) 2011 Numenta Inc, All rights reserved,
#
#  The information and source code contained herein is the
#  exclusive property of Numenta Inc, No part of this software
#  may be used, reproduced, stored or distributed in any form,
#  without explicit written authorization from Numenta Inc,
# ----------------------------------------------------------------------

# This file invokes predictionmetricsmanager.py tests
#

#############################################################################
if __name__=="__main__":

  from nupic.frameworks.opf.predictionmetricsmanager import (
    test as predictionMetricsManagerTest)

  predictionMetricsManagerTest()