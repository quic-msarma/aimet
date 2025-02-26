# -*- mode: python -*-
# =============================================================================
#  @@-COPYRIGHT-START-@@
#
#  Copyright (c) 2022, Qualcomm Innovation Center, Inc. All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  1. Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#
#  2. Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
#  3. Neither the name of the copyright holder nor the names of its contributors
#     may be used to endorse or promote products derived from this software
#     without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#  POSSIBILITY OF SUCH DAMAGE.
#
#  SPDX-License-Identifier: BSD-3-Clause
#
#  @@-COPYRIGHT-END-@@
# =============================================================================

import tempfile
from typing import Callable

import numpy as np
import tensorflow as tf

from aimet_common.cache import Cache, SerializationProtocolBase
from aimet_tensorflow.cache import TfSessionSerializationProtocol
from aimet_tensorflow.examples.test_models import keras_model

tf.compat.v1.disable_eager_execution()


SEED = 18452
tf.compat.v1.random.set_random_seed(SEED)


def _assert_equal_default(output, expected):
    assert type(output) == type(expected)
    assert output == expected


def _assert_equal_tf_session(sess: tf.compat.v1.Session,
                             expected: tf.compat.v1.Session):
    assert type(sess) == type(expected)
    ops = sorted(sess.graph.get_operations(), key=lambda op: op.name)
    _ops = sorted(expected.graph.get_operations(), key=lambda op: op.name)

    assert len(ops) == len(_ops)

    for op, _op in zip(ops, _ops):
        assert op.type == _op.type
        assert op.name == _op.name

    with sess.graph.as_default():
        variables = [
            v.eval(session=sess)
            for v
            in tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.GLOBAL_VARIABLES)
        ]

    with expected.graph.as_default():
        _variables = [
            v.eval(session=expected)
            for v
            in tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.GLOBAL_VARIABLES)
        ]

    assert len(variables) == len(_variables)
    for v, _v in zip(variables, _variables):
        assert np.array_equal(v, _v)


def _test_cache(fn,
                protocol: SerializationProtocolBase = None,
                assert_equal_fn: Callable = None):
    if not assert_equal_fn:
        assert_equal_fn = _assert_equal_default

    with tempfile.TemporaryDirectory() as cache_dir:
        cache = Cache()

        call_count = 0

        @cache.mark("test", protocol)
        def _fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fn(*args, **kwargs)

        with cache.enable(cache_dir):
            ret = _fn()

        with cache.enable(cache_dir):
            _ret = _fn()

        assert_equal_fn(ret, _ret)
        assert call_count == 1


def test_cache_tf_session():
    def f():
        graph = tf.Graph()
        with graph.as_default():
            tf.compat.v1.set_random_seed(1)
            _ = keras_model()
            init = tf.compat.v1.global_variables_initializer()

        session = tf.compat.v1.Session(graph=graph)
        session.run(init)
        return session

    protocol = TfSessionSerializationProtocol()
    _test_cache(f, protocol, _assert_equal_tf_session)
