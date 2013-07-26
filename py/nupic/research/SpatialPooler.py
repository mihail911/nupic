#!/usr/bin/env python
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

import sys
import os
import numpy
import numpy.random
import random
import itertools
import time
import math
import copy
import cPickle
import struct

from nupic.bindings.math import SM32 as SparseMatrix, \
                                SM_01_32_32 as SparseBinaryMatrix, \
                                count_gte, GetNTAReal
from nupic.bindings.algorithms import Inhibition2 as Inhibition, \
                                      cpp_overlap, cpp_overlap_sbm
from nupic.bindings.algorithms import adjustMasterValidPermanence
from nupic.bindings.math import Random as NupicRandom
from nupic.math.cross import cross
from operator import itemgetter
import nupic.research.fdrutilities as fdru

realDType = GetNTAReal()


class SpatialPooler(object):
  """"
  This class implements a cortical region. It provides an object oriented
  public interface to the spatial pooler
  """
  def __init__(self,
               numInputs,
               numColumns,
               receptiveFieldRadius = 16,
               receptiveFieldPctPotential = 0.5,
               globalInhibition = False,
               localAreaDensity = -1.0,
               numActiveColumnsPerInhArea = 10.0,
               stimulusThreshold=0,
               synPermInactiveDec=0.01,
               synPermActiveInc = 0.1,
               synPermActiveSharedDec = 0.0,
               synPermOrphanDec = 0.0,
               synPermConnected = 0.10,
               minPctOverlapDutyCycle = 0.001,
               minPctActiveDutyCycle = 0.001,
               dutyCyclePeriod = 1000,
               maxBoost = 10.0,
               seed = -1,
               verbosityLevel = 0
               ):

    #verify input is valid
    assert (numActiveColumnsPerInhArea > 0 or localAreaDensity > 0)
    assert (localAreaDensity == -1 or 
            (localAreaDensity >0 and localAreaDensity < 1))


    # save arguments
    self._numInputs = numInputs
    self._numColumns = numColumns
    self._receptiveFieldRadius = min(receptiveFieldRadius, numInputs)    
    self._receptiveFieldPctPotential = receptiveFieldPctPotential
    self._globalInhibition = globalInhibition
    self._numActiveColumnsPerInhArea = numActiveColumnsPerInhArea
    self._localAreaDensity = localAreaDensity
    self._stimulusThreshold = stimulusThreshold
    self._synPermInactiveDec = synPermInactiveDec
    self._synPermActiveInc = synPermActiveInc
    self._synPermActiveSharedDec = synPermActiveSharedDec
    self._synPermBelowStimulusInc = synPermConnected / 10.0
    self._synPermOrphanDec = synPermOrphanDec
    self._synPermConnected = synPermConnected
    self._minPctOverlapDutyCycles = minPctOverlapDutyCycle
    self._minPctActiveDutyCycles = minPctActiveDutyCycle
    self._dutyCyclePeriod = dutyCyclePeriod
    self._maxBoost = maxBoost

    #extra parameter settings
    self._synPermMin = 0.0
    self._synPermMax = 1.0
    self._updatePeriod = 50

    # internal state
    self._version = 1.0
    self._columnDimensions = numpy.array([numColumns])
    self._inputDimensions = numpy.array([numInputs])
    self._inhibitionRadius = 5  #TODO: Update this
    self._iterationNum = 0
    self._learningIterationNum = 0

    receptiveFields = [self._mapRF(i) for i in xrange(numColumns)]
    self._receptiveFields = SparseBinaryMatrix(receptiveFields)
    initialPermanences = [self._initPermanence(i) for i in xrange(numColumns)]
    self._permanences = SparseMatrix(initialPermanences)
    self._connectedSynapses = SparseBinaryMatrix(numInputs)
    self._connectedSynapses.resize(numColumns,numInputs)
    self._connectedCounts = numpy.zeros(numColumns)
    self._updateConnectedSynapses()

    self._overlapDutyCycles = numpy.zeros(numColumns)
    self._activeDutyCycles = numpy.zeros(numColumns)
    self._minOverlapDutyCycles = numpy.zeros(numColumns)
    self._minActiveDutyCycles = numpy.zeros(numColumns)
    self._boostFactors = numpy.zeros(numColumns)

    self._seed(seed)
  

  def _adaptSynapses(self,inputVector,sharedInputs,orphanColumns):
    inputIndices = numpy.where(inputVector > 0)[0]
    orphanSet = set(orphanColumns)
    permChanges = numpy.zeros(self._numInputs)
    permChanges.fill(-1 * self._synPermInactiveDec)
    permChanges[inputIndices] = self._synPermActiveInc
    permChanges[sharedInputs] -= self._synPermActiveSharedDec
    for i in xrange(self._numColumns):
      perm = self._permanences.getRow(i)
      numpy.clip(perm,self._synPermMin,self._synPermMax,out=perm)
      maskRF = numpy.where(self._receptiveFields.getRow(i) > 0)[0]
      perm[maskRF] += permChanges[maskRF]
      if i in orphanSet:
        perm[maskRF] -= self._synPermOrphanDec
      self._permanences.setRowFromDense(i,perm)
    self._updateConnectedSynapses()
      

  def _raisePermanenceToThreshold(self):
    trimThreshold = self._synPermActiveInc / 2.0
    belowThreshold = numpy.where(
      self._connectedCounts < self._stimulusThreshold)[0]
    for i in belowThreshold:
      perm = self._permanences.getRow(i).astype(realDType)
      permChange = self._receptiveFields.getRow(i).astype(realDType)
      while True:
        perm += self._synPermBelowStimulusInc
        numConnected = count_gte(perm, self._synPermConnected)
        if numConnected >= self._stimulusThreshold:
          break
      self._permanences.setRowFromDense(i,perm)
      self._permanences.thresholdRow(i,trimThreshold)
    self._updateConnectedSynapses()


  def _updateConnectedSynapses(self):
    for i in xrange(self._numColumns):
      newConnected = \
        numpy.where(self._permanences.getRow(i) > self._synPermConnected)[0]
      self._connectedSynapses.replaceSparseRow(i, newConnected)
      self._connectedCounts[i] = newConnected.size


  def _initPermanence(self,index):
    """
    Initializes the permanences of a column. The method
    returns a 1-D array the size of the input, where each entry in the
    array represents the initial permanence value between the input bit
    at the particular index in the array, and the column represented by
    the 'index' parameter.
    """
    # Determine which inputs bits will start out as connected
    # to the inputs. Initially a subset of the input bits in a 
    # column's receptive field will be connected. This number is
    # given by the parameter "receptiveFieldPctPotential"
    rand = numpy.random.random(2*self._receptiveFieldRadius+1)
    threshold = 1-self._receptiveFieldPctPotential
    connectedSynapses = numpy.where(rand > threshold)[0]
    unconnectedSynpases = list(set(range(self._receptiveFieldRadius)) - \
      set(connectedSynapses))
    maxPermValue = min(1.0, self._synPermConnected + \
                self._synPermInactiveDec)

    # All connected synapses are to have a permanence value between
    # synPermConnected and synPermActiveInc/4
    connectedPermRange = self._synPermActiveInc / 4
    connectedPermOffset = self._synPermConnected

    # All unconnected synapses are to have a permanence value 
    # between 0 and synPermConnected
    unconnectedPermRange = self._synPermConnected
    unconnectedPermOffset = 0

    # Create a vector to contain only the permanence values inside
    # a column's local receptive field, and fill it with random values
    # from the aforementioned distributions
    permRF = numpy.zeros(2*self._receptiveFieldRadius+1)
    permRF[connectedSynapses] = numpy.random.random(len(connectedSynapses)) \
      * connectedPermRange + connectedPermOffset
    permRF[unconnectedSynpases] = numpy.random.random(len(unconnectedSynpases)) \
      * unconnectedPermRange + unconnectedPermOffset

    # Clip off low values. Since we use a sparse representation
    # to store the permanence values this helps reduce memory
    # requirements.
    permRF[permRF < (self._synPermActiveInc / 2.0)] = 0

    # Create a full vector the size of the entire input and fill in
    # the permanence values we just computed at the correct indices
    maskRF = numpy.where(self._mapRF(index) > 0)[0]
    permanences = numpy.zeros(self._numInputs)
    permanences[maskRF] = permRF

    return permanences


  def _mapRF(self,index):
    """
    Maps a column to its inputs. This method encapsultes the topology of the
    region. It takes the index of the column as an argument and determines 
    what are the indices of the input vector that are located within the column's
    receptive field. The return value is a list containing the indices of the input bits.
    The current implementation of the base class only supports a 
    1-D topology. To extend this class to support 2-D topology you will need to 
    override this method. Examples of the expected output of this method:
    * If the receptiveFieldRadius is greater than or equal to the entire input space,
      (global visibility), then this method returns an array filled with all the
      indices
    * If the topology is one dimensional, and the receptiveFieldRadius is 5, this method
      will return an array containing 5 consecutive values centered on the index of
      the column (wrapping around if necessary).
    * If the topology is two dimensional (not implemented), and the receptiveFieldRadius 
      is 5, the method should return an array containing 25 '1's, where the exact 
      indices are to be determined by the mapping from 1-D index to 2-D position.
    """
    indices = numpy.array(range(2*self._receptiveFieldRadius+1))
    indices += index
    indices -= self._receptiveFieldRadius
    indices %= self._numInputs
    indices = list(set(indices))
    mask = numpy.zeros(self._numInputs)
    mask[indices] = 1
    return mask


  def compute(self,inputVector, learn=True, infer=True):

    assert (learn or infer)
    assert (numpy.size(inputVector) == self._numInputs)

    # (vip selection here....)
    overlaps, overlapsPct = self._calculateOverlap(inputVector)

    #v boosting here... only if still learning!
    if learn:
      boostedOverlaps = self._boostFactors * overlaps
    else:
      boostedOverlaps = overlaps

    #v inhibition
    activeColumns = self._inhibitColumns(boostedOverlaps)

    #v find orphans
    orphanColumns = self._calculateOrphanColumns(activeColumns,overlapsPct)

    #v find shared inputs
    sharedInputs = self._calculateSharedInputs(inputVector,activeColumns)
    
    #v compute anomaly scores 
    anomalyScore = _calculateAnomalyScore(overlaps,activeColumns)

    #v adapt synapses per column
    self._adaptSynapses(inputVector,sharedInputs,orphanColumns)

    #v raise permanences to stimulus threshold connections
    self._raisePermanenceToThreshold()

    # bump up weak columns / boosting?
    self._bumpUpWeak() # raisePermanence only once!!

    #v update boost factors per column
    self._updateBoostFactors()

    #v update duty cycles per column
    self._updateDutyCycles(overlaps,activeColumns)

    #v update the min duty cycles
    self._updateMinDutyCycles()

    # update inhibition radius
    self._updateInhibitionRadius()

    #v update bookeeping
    self._updateBookeeping(learn,infer)


  def _calculateAnomalyScore(self, overlaps, activeColumns):
    if activeColumns.size == 0:
      return 1.0

    anomalyScores = overlaps[activeColumns]
    anomalyScores *= self._activeDutyCycles[activeColumns]
    return 1.0 / (numpy.sum(anomalyScores) + 1)


  def _updateMinDutyCycles(self):
    if self._isUpdateRound():
      if self._globalInhibition or self._inhibitionRadius > self._numInputs:
        self._updateMinDutyCyclesGlobal()
      else:
        self._updateMinDutyCyclesLocal()


  def _updateMinDutyCyclesGlobal(self):
    self._minOverlapDutyCycles.fill(
        self._minPctOverlapDutyCycles * self._overlapDutyCycles.max()
      )
    self._minActiveDutyCycles.fill(
        self._minPctActiveDutyCycles * self._activeDutyCycles.max()
      )


  def _updateMinDutyCyclesLocal(self):
    for i in xrange(self._numColumns):
      maskNeighbors = self._getNeighbors(i,self._columnDimensions,
        self._inhibitionRadius)
      self._minOverlapDutyCycles[i] = \
        self._overlapDutyCycles[maskNeighbors].max() * self._minPctOverlapDutyCycles
      self._minActiveDutyCycles[i] = \
        self._activeDutyCycles[maskNeighbors].max() * self._minPctActiveDutyCycles


  def _updateDutyCycles(overlaps,activeColumns):
    activeArray = numpy.zeros()
    if activeColumns.size > 0:
      activeArray[activeColumns] = 1
    period = self._dutyCyclePeriod
    if (period < self._iterationNum):
      period = self._iterationNum

    self._overlapDutyCycles = \
    self._updateDutyCyclesHelper(self._overlapDutyCycles, 
                                overlaps, 
                                period)

    self._activeDutyCycles = \
    self._updateDutyCyclesHelper(self._activeDutyCycles, 
                                activeArray,
                                period)


  @staticmethod
  def _updateDutyCyclesHelper(dutyCycles,newInput,period):
    """
    Updates a duty cycle estimate with a new value. This is a helper
    function that is used to update several duty cycle variables in 
    the Column class, such as: overlapDutyCucle, activeDutyCycle,
    minPctDutyCycleBeforeInh, minPctDutyCycleAfterInh, etc. returns
    the updated duty cycle.
    """
    assert(period >= 1)
    return (dutyCycles * (period -1.0) + newInput) / period


  def _updateBoostFactors(self):
    """
    Update the boost factors. The boost factors is linearly interpolated
    between the points (dutyCycle:0, boost:maxFiringBoost) and
    (dutyCycle:minDuty, boost:1.0). This is a line defined as: y = mx + b
    boost = (1-maxBoost)/minDuty * dutyCycle + maxFiringBoost

            boostFactor
                ^
    maxBoost _  |
                |\
                | \
          1  _  |  \ _ _ _ _ _ _ _
                |   
                +--------------------> dutyCycle
                   |
                 minDuty
    """
    
    self._boostFactors = (1 - self._maxBoost) \
     / self._minActiveDutyCycles * self._activeDutyCycles \
      + self.maxFiringBoost

    self._boostFactors[self._activeDutyCycles > self._minActiveDutyCycles] = 1.0


  def _updateBookeeping(self,learn,infer):
    self._iterationNum += 1
    if learn:
      self._iterationLearnNum += 1
    if infer:
      self._iterationInferNum += 1


  def _calculateOverlap(self,inputVector):
    overlaps = numpy.zeros(self._numColumns).astype(realDType)
    self._connectedSynapses.rightVecSumAtNZ_fast(inputVector, overlaps)
    overlapsPct = overlaps.astype(realDType) / self._connectedCounts
    return overlaps, overlapsPct


  def _calculateOrphanColumns(self,activeColumns, overlapsPct):
    perfectOverlaps = set(numpy.where(overlapsPct >= 1)[0])
    return list(perfectOverlaps.intersection(set(activeColumns)))


  def _calculateSharedInputs(self,inputVector,activeColumns):
    connectedSynapses = SparseMatrix(self._connectedSynapses)
    inputCoverage = connectedSynapses.addListOfRows(activeColumns)
    sharedInputs = numpy.where(numpy.logical_and(inputCoverage > 1,inputVector > 0))[0]
    return sharedInputs


  def _inhibitColumns(self,overlaps):
    # determine how many columns should be selected
    # in the inhibition phase given the number of values
    overlaps = overlaps.copy()
    if (numActiveColumnsPerInhArea > 0):
      numActive = numActiveColumnsPerInhArea
    else:
      numActive = localAreaDensity * self._inhibitionRadius

    # Add a little bit of random noise to the scores to help break
    # ties.
    tieBreaker = 0.1*numpy.random.rand(self._numColumns)
    overlaps += tieBreaker

    if self._globalInhibition or self._inhibitionRadius > self._numInputs:
      return self._inhibitColumnsGlobal(overlaps)
    else:
      return self._inhibitColumns1D(overlaps)
    pass

  
  def _inhibitColumnsGlobal(self,overlaps, numActive):
    #calculate num active per inhibition area
    activeColumns = numpy.zeros(self._numColumns)
    winners = sorted(range(overlaps.size), 
                     key=lambda k: overlaps[k], 
                     reverse=True)[0:numActive]
    activeColumns[winners] = 1
    return activeColumns


  def _inhibitColumnsLocal(self,overlaps,numActive):
    activeColumns = numpy.zeros(self._numColumns)
    addToWinners = max(overlaps)/1000.0   
    overlaps = numpy.array(overlaps,dtype=realDType).reshape(self._columnDimensions)
    for i in xrange(self._numColumns):
      maskNeighbors = self._getNeighbors(i,self._columnDimensions,
        self._inhibitionRadius)
      overlapSlice = overlaps[maskNeighbors]
      kthLargestValue = sorted(overlapSlice,
                               reverse=True)[numActive-1]
      if overlaps[i] >= kthLargestValue:
        activeColumns[i] = 1
        overlaps[i] += addToWinners
    return numpy.where(activeColumns > 0)[0]


  @staticmethod
  def _getNeighbors(columnIndex, dimensions, radius):
    """
    This is for 1D
    """
    assert(dimensions.size == 1)
    ncols = dimensions[0]
    neighbors = numpy.array(
      range(columnIndex-radius,columnIndex+radius+1)) % ncols
    neighbors = list(set(neighbors) - set([columnIndex])) 
    assert(neighbors)
    return neighbors


  @staticmethod
  def _getNeighbors2D(columnIndex, dimensions, radius):
    """
    This is for 2D
    """
    assert(dimensions.size == 2)
    nrows = dimensions[0]
    ncols = dimensions[1]

    toRow = lambda index: index / ncols
    toCol = lambda index: index % ncols
    toIndex = lambda row,col: row * ncols + col

    row = toRow(columnIndex)
    col = toCol(columnIndex)

    colRange = numpy.array(range(row-radius,row+radius+1)) % nrows
    rowRange = numpy.array(range(col-radius,col+radius+1)) % ncols

    neighbors = [toIndex(r,c) for (r,c) in itertools.product(colRange,rowRange)]
    neighbors = list(set(neighbors) - set([columnIndex]))
    assert(neighbors)
    return neighbors
     

  @staticmethod
  def _getNeighborsND(columnIndex, dimensions, radius):
    """
    This is for arbitrary dimensions (N-dimension).
    """
    assert(dimensions.size > 0)
    bounds = numpy.cumprod(numpy.append([1],dimensions[::-1][:-1]))[::-1]

    def toCoords(index):
      return (index / bounds) % dimensions

    def toIndex(coords):
      return numpy.dot(bounds,coords)

    columnCoords = toCoords(columnIndex)
    rangeND = []
    for i in xrange(dimensions.size):
      curRange = numpy.array(range(columnCoords[i]-radius, \
                                   columnCoords[i]+radius+1)) % dimensions[i]
      rangeND.append(curRange)

    neighbors = [toIndex(numpy.array(coord)) for coord in itertools.product(*rangeND)]
    neighbors = list(set(neighbors) - set([columnIndex]))
    assert(neighbors)
    return neighbors


  def _isUpdateRound(self):
    return ((self._iterationNum + 1) % self._updatePeriod) == 0


  def _averageConnectedReceptiveField(self):
    avgConnectedRF = self._averageConnectedSpan() * \
                     self._averageColumnsPerInput()
    avgConnectedRF = (avgTotalDim - 1) / len(connectedSynapseIndices)
    avgConnectedRF = max(1.0,avgConnectedRF)
    maxDimension = max(self._columnShape)
    avgConnectedRF = min(maxDimension,avgConnectedRF)
    return int(round(avgConnectedRF))


  def _seed(self, seed=-1):
    """
    Initialize the random seed
    """

    if seed != -1:
      self.random = NupicRandom(seed)
      random.seed(seed)
      numpy.random.seed(seed)
    else:
      self.random = NupicRandom()
    
  # def _averageConnectedSpan(self):
  #   totalAvgSpan = 0
  #   for column in self._numColumns:
  #     connectedSynapseIndices = \
  #       numpy.nonzero(self._connectedSynapses.getRow(). \
  #         reshape(self._inputShape))
  #     avgSpan = 0
  #     for dim in range(len(connectedSynapseIndices)):
  #       span = max(connectedSynapseIndices[dim]) - \
  #                  min(connectedSynapseIndices[dim])
  #       avgSpan += max(span,1)
  #       avgSpan /= len(connectedSynapseIndices)
  #     totalAvgSpan += avgSpan
  #   return totalAvgSpan / self._numColumns

  # def _averageColumnsPerInput(self):
  #   columnsPerInput = 0
  #   for dim in range(len(self._columnShape)):
  #     columnsPerInput += float(self._columShape[dim] \
  #                               / self._inputShape[dim] - 2*self._inputBorder)
  #   return columnsPerInput / self._numColumns


  # def _calculateLocalAreaDensity(self,inhibitionRadius):
  #   if (self._localAreaDensity > 0):
  #     return self._localAreaDensity
    
  #   numColumnsPerInhArea = (inhibitionRadius * 2.0 + 1) ** 2
  #   numColumnsPerInhArea = min(numColumnsPerInhArea, self._numColumns)
  #   return min(float(self.numActiveColumnsPerInhArea) / numColumnsPerInhArea, 
  #              0.5)


  def __get_state__(self):
    pass

  def __set_state__(self):
    pass





