# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Estimates use work completed in this run, excluding cached/resumed files."""
import math,time
from collections import deque

class Progress:
    def __init__(self,total=0,completed=0,total_bytes=0,completed_bytes=0,clock=time.monotonic):
        self.clock=clock;self.start=clock();self.total=total;self.done=completed
        self.total_bytes=total_bytes;self.done_bytes=completed_bytes
        self.base_done=completed;self.base_bytes=completed_bytes;self.samples=deque([(self.start,completed,completed_bytes)])
        self.updated=self.start
    def update(self,completed,completed_bytes=0):
        now=self.clock()
        if completed<self.done:return
        if completed>self.done or completed_bytes>self.done_bytes:
            self.samples.append((now,completed,completed_bytes));self.updated=now
            while len(self.samples)>2 and now-self.samples[1][0]>60:self.samples.popleft()
        self.done=completed;self.done_bytes=completed_bytes
    def snapshot(self):
        now=self.clock();elapsed=max(0,now-self.start);eta=None;rate=None;bps=None
        if len(self.samples)>1:
            first=self.samples[0];last=self.samples[-1];duration=last[0]-first[0]
            if duration>0:
                rate=(last[1]-first[1])/duration
                if last[2]>first[2]:bps=(last[2]-first[2])/duration
            # Allow variable render and connection times to settle before estimating.
            if self.done-self.base_done>=3 and duration>=4 and rate and now-self.updated<max(60,3/rate):
                eta=(self.total_bytes-self.done_bytes)/bps if bps and self.total_bytes else (self.total-self.done)/rate
                eta=max(0,round(eta))
        if self.total and self.done>=self.total:eta=0
        return {'done':self.done,'total':self.total,'percent':round(min(100,100*self.done/self.total),1) if self.total else 0,
                'elapsed':round(elapsed),'eta':eta,'perMinute':round(rate*60,1) if rate else None,
                'bytesPerSecond':round(bps) if bps else None,'doneBytes':self.done_bytes,'totalBytes':self.total_bytes}
