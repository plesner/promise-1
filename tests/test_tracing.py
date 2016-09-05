import promise
from promise import Promise, TracingPromise, Trace
from functools import partial
import logging

class MyError(Exception):
    pass


def error_raiser(message):
    def raise_error(resolve, reject):
        raise MyError(message)
    return raise_error

def add(a, b):
    return a + b

def count_occurrences(traceback, message):
    count = 0
    for line in traceback.format():
        if message in line:
            count += 1
    return count


def check_no_framework_frames(traceback):
    assert 0 == count_occurrences(traceback, "promise/tracing.py")
    assert 0 == count_occurrences(traceback, "_mark_rejected")
    assert 0 == count_occurrences(traceback, "self.__class__")
    assert 0 == count_occurrences(traceback, "cls()")


def test_fulfilled_no_traceback():
    p = TracingPromise.fulfilled(None)
    assert p.rejection_trace is None

def test_rejected_no_raise_no_traceback():
    p = TracingPromise.rejected(MyError('A'))
    assert 1 == count_occurrences(p.rejection_trace, "MyError: A")
    assert 1 == count_occurrences(p.rejection_trace, "p = TracingPromise.rejected(MyError('A'))")
    assert 1 == count_occurrences(p.rejection_trace, "in test_rejected_no_raise_no_traceback")
    assert 0 == count_occurrences(p.rejection_trace, "direct cause of rejecting the following")
    check_no_framework_frames(p.rejection_trace)

def test_raiser_raise_traceback():
    p = TracingPromise(error_raiser('B'))
    assert 1 == count_occurrences(p.rejection_trace, "p = TracingPromise(error_raiser('B'))")
    assert 1 == count_occurrences(p.rejection_trace, "raise MyError(message)")
    assert 2 == count_occurrences(p.rejection_trace, "MyError: B")
    assert 1 == count_occurrences(p.rejection_trace, "in raise_error")
    assert 1 == count_occurrences(p.rejection_trace, "in test_raiser_raise_traceback")
    assert 1 == count_occurrences(p.rejection_trace, "direct cause of rejecting the following")
    check_no_framework_frames(p.rejection_trace)

def test_rejected_raise_traceback():
    p = TracingPromise()
    p.reject(MyError('C'))
    assert 1 == count_occurrences(p.rejection_trace, "p = TracingPromise()")
    assert 1 == count_occurrences(p.rejection_trace, "p.reject(MyError('C'))")
    assert 2 == count_occurrences(p.rejection_trace, "MyError: C")
    assert 1 == count_occurrences(p.rejection_trace, "direct cause of rejecting the following")
    assert 1 == count_occurrences(p.rejection_trace, "same as the above")
    check_no_framework_frames(p.rejection_trace)

def test_chained_rejection():
    run_test_chained_rejection(100)


def run_test_chained_rejection(remaining_calls):
    if remaining_calls > 0:
        return run_test_chained_rejection(remaining_calls - 1)
    p0 = TracingPromise()
    p1 = p0.then(partial(add, 1))
    p2 = p1.then(partial(add, 2))
    p3 = p2.then(partial(add, 3))
    p0.reject(MyError('D'))

    # p3
    print("".join(p3.rejection_trace.format()))
    assert 1 == count_occurrences(p3.rejection_trace, "p3 = p2.then(partial(add, 3))")
    assert 1 == count_occurrences(p3.rejection_trace, "p2 = p1.then(partial(add, 2))")
    assert 1 == count_occurrences(p3.rejection_trace, "p1 = p0.then(partial(add, 1))")
    assert 1 == count_occurrences(p3.rejection_trace, "p0 = TracingPromise()")
    assert 1 == count_occurrences(p3.rejection_trace, "p0.reject(MyError('D'))")
    assert 5 == count_occurrences(p3.rejection_trace, "MyError: D")
    # If we show the full stack for all trace segments we'll get 100 frames for
    # every promise. This checks that we only get it for one of them.
    assert 104 == count_occurrences(p3.rejection_trace,
        "return run_test_chained_rejection(remaining_calls - 1)")
    check_no_framework_frames(p3.rejection_trace)

    # p2
    assert 0 == count_occurrences(p2.rejection_trace, "p3 = p2.then(partial(add, 3))")
    assert 1 == count_occurrences(p2.rejection_trace, "p2 = p1.then(partial(add, 2))")
    assert 1 == count_occurrences(p2.rejection_trace, "p1 = p0.then(partial(add, 1))")
    assert 1 == count_occurrences(p2.rejection_trace, "p0 = TracingPromise()")
    assert 4 == count_occurrences(p2.rejection_trace, "MyError: D")
    # If we show the full stack for all trace segments we'll get 100 frames for
    # every promise. This checks that we only get it for one of them.
    assert 103 == count_occurrences(p2.rejection_trace,
        "return run_test_chained_rejection(remaining_calls - 1)")
    check_no_framework_frames(p2.rejection_trace)

    # p1
    assert 0 == count_occurrences(p1.rejection_trace, "p3 = p2.then(partial(add, 3))")
    assert 0 == count_occurrences(p1.rejection_trace, "p2 = p1.then(partial(add, 2))")
    assert 1 == count_occurrences(p1.rejection_trace, "p1 = p0.then(partial(add, 1))")
    assert 1 == count_occurrences(p1.rejection_trace, "p0 = TracingPromise()")
    assert 3 == count_occurrences(p1.rejection_trace, "MyError: D")
    # If we show the full stack for all trace segments we'll get 100 frames for
    # every promise. This checks that we only get it for one of them.
    assert 102 == count_occurrences(p1.rejection_trace,
        "return run_test_chained_rejection(remaining_calls - 1)")
    check_no_framework_frames(p1.rejection_trace)

    # p0
    assert 0 == count_occurrences(p0.rejection_trace, "p3 = p2.then(partial(add, 3))")
    assert 0 == count_occurrences(p0.rejection_trace, "p2 = p1.then(partial(add, 2))")
    assert 0 == count_occurrences(p0.rejection_trace, "p1 = p0.then(partial(add, 1))")
    assert 1 == count_occurrences(p0.rejection_trace, "p0 = TracingPromise()")
    assert 2 == count_occurrences(p0.rejection_trace, "MyError: D")
    # If we show the full stack for all trace segments we'll get 100 frames for
    # every promise. This checks that we only get it for one of them.
    assert 101 == count_occurrences(p0.rejection_trace,
        "return run_test_chained_rejection(remaining_calls - 1)")
    check_no_framework_frames(p0.rejection_trace)


def test_common_prefix():
    assert (False, ["a", "b", "c", "d", "e"]) == Trace._trim_common_prefix(
        [],
        ["a", "b", "c", "d", "e"])
    assert (True, ["c", "d", "e"]) == Trace._trim_common_prefix(
        ["a", "b", "c"],
        ["a", "b", "c", "d", "e"])
    assert (False, ["x", "y", "z"]) == Trace._trim_common_prefix(
        ["a", "b", "c"],
        ["x", "y", "z"])
    assert (False, ["x", "b"]) == Trace._trim_common_prefix(
        ["x", "a"],
        ["x", "b"])


def test_flag():
    assert not Promise._force_tracing
    p0 = Promise()
    assert p0._origin is None
    promise.Promise.set_force_tracing(True)
    p1 = promise.Promise()
    assert not p1._origin is None
    promise.Promise.set_force_tracing(False)
