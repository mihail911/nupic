# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------

"""
Template file used by ExpGenerator to generate the actual
permutations.py file by replacing $XXXXXXXX tokens with desired values.

This permutations.py file was generated by:
'/Users/ronmarianetti/nta/eng/lib/python2.6/site-packages/nupic/frameworks/opf/expGenerator/ExpGenerator.py'
"""

import os

from nupic.swarming.permutationhelpers import *

# The name of the field being predicted.  Any allowed permutation MUST contain
# the prediction field.
# (generated from PREDICTION_FIELD)
predictedField = 'consumption'

permutations = {
  
  'modelParams': {
    'sensorParams': {
      'encoders': {
        'gym': PermuteEncoder(fieldName='gym', encoderClass='SDRCategoryEncoder', w=7, n=100),
        'timestamp_dayOfWeek': PermuteEncoder(fieldName='timestamp', encoderClass='DateEncoder.dayOfWeek', radius=PermuteChoices([1, 3]), w=7),
        'timestamp_timeOfDay': PermuteEncoder(fieldName='timestamp', encoderClass='DateEncoder.timeOfDay', radius=PermuteChoices([1, 8]), w=7),
        'consumption': PermuteEncoder(fieldName='consumption', encoderClass='ScalarEncoder', maxval=PermuteInt(100, 300, 25), n=PermuteInt(13, 500, 20), w=7, minval=0),
        'address': PermuteEncoder(fieldName='address', encoderClass='SDRCategoryEncoder', w=7, n=100),
      },
    },
  
  
    'tpParams': {
      'minThreshold': PermuteInt(9, 12),
      'activationThreshold': PermuteInt(12, 16),
    },
  
  
    }
}


# Fields selected for final hypersearch report;
# NOTE: These values are used as regular expressions by RunPermutations.py's
#       report generator
# (fieldname values generated from PERM_PREDICTED_FIELD_NAME)
report = [
          '.*consumption.*',
         ]

# Permutation optimization setting: either minimize or maximize metric
# used by RunPermutations.
# NOTE: The value is used as a regular expressions by RunPermutations.py's
#       report generator
# (generated from minimize = 'prediction:rmse:field=consumption')
minimize = 'prediction:rmse:field=consumption'


#############################################################################
def dummyModelParams(perm):
  """ This function can be used for Hypersearch algorithm development. When
  present, Hypersearch doesn't actually run the CLA model in the OPF, but instead run
  a dummy model. This function returns the dummy model params that will be
  used. See the OPFDummyModelRunner class source code (in
  nupic.swarming.ModelRunner) for a description of the schema for
  the dummy model params.
  """

  errScore = 100


  if perm['modelParams']['sensorParams']['encoders']['address'] is not None:
    errScore -= 0
  if perm['modelParams']['sensorParams']['encoders']['gym'] is not None:
    errScore -= 10
  if perm['modelParams']['sensorParams']['encoders']['timestamp_timeOfDay'] \
        is not None:
    errScore -= 20
  if perm['modelParams']['sensorParams']['encoders']['timestamp_dayOfWeek'] \
        is not None:
    errScore -= 50

  dummyModelParams = dict(
                metricValue = errScore,
                metricFunctions = None,
                )
  return dummyModelParams



#############################################################################
def permutationFilter(perm):
  """ This function can be used to selectively filter out specific permutation
  combinations. It is called by RunPermutations for every possible permutation
  of the variables in the permutations dict. It should return True for valid a
  combination of permutation values and False for an invalid one.

  Parameters:
  ---------------------------------------------------------
  perm: dict of one possible combination of name:value
        pairs chosen from permutations.
  """

  # An example of how to use this
  limit = int(os.environ.get('NTA_TEST_maxvalFilter', 300))
  if perm['modelParams']['sensorParams']['encoders']['consumption']['maxval'] > limit:
    return False;

  return True
