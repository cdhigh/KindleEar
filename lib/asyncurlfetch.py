# Copyright (C) 2010 David Underhill dgu@cs.stanford.edu
# This module is released under the MIT license:
# http://www.opensource.org/licenses/mit-license.php
"""
This module provides a wrapper around the urlfetch API which maximizes the
concurrency of asynchronous urlfetch requests (within app engine limits).
 
To start asynchronous fetch(es), first create an AsyncURLFetchManager and then
call call fetch_async() as many times as needed.  For optimal
performance, start the fetches which are fastest first.
 
When you're ready to wait for the fetches to complete, call the wait() method.
"""
 
from google.appengine.api import urlfetch
 
MAX_SIMULTANEOUS_ASYNC_URLFETCH_REQUESTS = 10
 
class AsyncURLFetchManager(object):
    def __init__(self):
        self.active_fetches = []
        self.pending_fetches = []
 
    def fetch_async(self, url, deadline=10,
                     callback=None, cb_args=[], cb_kwargs={},
                     **kwargs):
        """
        Asynchronously fetches the requested url.  Ensures that the maximum
        number of simultaneous asynchronous fetches is not exceeded.
 
        url      - the url to fetch
        deadline - maximum number of seconds to wait for a response
        callback - if given, called upon completion.  The first argument will be
                   the rpc object (which contains the response).  If cb_args
                   or cb_kwargs were provided then these will be passed to
                   callback as additional positional and keyword arguments.
 
        All other keyword arguments are passed to urlfetch.make_fetch_call().
 
        Returns the RPC which will be used to fetch the URL.
        """
        rpc = urlfetch.create_rpc(deadline=deadline)
        rpc.callback = lambda : self.__fetch_completed(rpc, callback,
                                                       cb_args, cb_kwargs)
 
        f = lambda : urlfetch.make_fetch_call(rpc, url, **kwargs)
        if len(self.active_fetches) < MAX_SIMULTANEOUS_ASYNC_URLFETCH_REQUESTS:
            self.__fetch(rpc, f)
        else:
            self.pending_fetches.append( (rpc,f) )
        return rpc
 
    def __fetch(self, rpc, f):
        self.active_fetches.append(rpc)
        f()
 
    def __fetch_completed(self, rpc, callback, cb_args, cb_kwargs):
        self.active_fetches.remove(rpc)
        if self.pending_fetches:
            # we just finished a fetch, so start the next one
            self.__fetch(*self.pending_fetches.pop(0))
 
        if callback:
            callback(rpc, *cb_args, **cb_kwargs)
 
    def wait(self):
        """Blocks until all asynchronous fetches have been completed."""
        while self.active_fetches:
            # Wait until this RPC finishes.  This will automatically call our
            # callback, which will start the next pending fetch (if any) and
            # remove the finished RPC from active_fetches.
            # This is *sub-optimal* - it would be better if we could poll the
            # RPCS and do a non-blocking check to see if they were ready.  By
            # arbitrarily waiting on the first RPC, we may miss out on another
            # RPC which may finish sooner.
            self.active_fetches[0].wait()