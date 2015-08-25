#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013, Numenta, Inc.  Unless you have an agreement
# with Numenta, Inc., for a separate license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------



class ModelInfo(object):
  """
    Defines information about a particular model.
  """
  def __init__(self,
               jobID,
               params,
               modelID,
               status,
               startTime,
               lastUpdate):
    self.jobID = jobID
    self.modelID = modelID
    # Dict of params for particular model
    self.params = params
    self.status = status
    # Why this job completed (e.g. success, killed, cancelled, error)
    self.completionReason = None
    self.startTime = startTime
    self.endTime = None
    # Timestamp of last update
    self.lastUpdate = lastUpdate


