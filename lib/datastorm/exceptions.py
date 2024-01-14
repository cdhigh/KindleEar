#!/usr/bin/env python3
# -*- coding:utf-8 -*-

class DatastormException(Exception):
    pass

LIMITS_URL = "https://cloud.google.com/datastore/docs/concepts/limits"

class BatchSizeLimitExceeded(DatastormException):
    def __init__(self, attempted_batch_size: int):
        super(BatchSizeLimitExceeded, self).__init__(f"Batch size limit per Commit exceeded:"
                                                     f"Attempted batch size: {attempted_batch_size}"
                                                     f"Read more about Datastore's limit here: {LIMITS_URL}")
