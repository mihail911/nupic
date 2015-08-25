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



class JobInfo(object):
  """
    Defines all the information about a particular job.
  """
  def __init__(self,
               jobID,
               status,
               startTime,
               minNumWorkers,
               maxNumWorkers):
    self.jobID = jobID
    self.status = status
    # Why this job completed (e.g. success, killed, cancelled, error)
    self.completionReason = None
    self.startTime = startTime
    self.endTime = None
    self.results = None
    # Timestamp of last update
    self.lastUpdate = None
    self.minNumWorkers = minNumWorkers
    self.maxNumWorkers = maxNumWorkers
